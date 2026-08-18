"""
api/pipeline.py — Orquestador del pipeline completo.

Etapa 12: detección automática de cliente vía DocumentDetector.
El pipeline downstream (validación, generadores, auditoría) no cambia.
"""
from __future__ import annotations

import io
import logging
import traceback
import zipfile
from pathlib import Path
from typing import Optional

from ingestion.document_detector import DocumentDetector
from generators.po_line_generator import PoLineGenerator
from generators.release_generator import ReleaseGenerator
from generators.order_price_generator import OrderPriceGenerator
from logging_.structured_logger import StructuredLogger
from validation import ValidationEngine

logger = logging.getLogger(__name__)


def run_pipeline(
    pdf_bytes: bytes,
    pdf_filename: Optional[str] = None,
    out_base: str = "output",
) -> tuple[bytes, dict]:
    """
    Ejecuta el pipeline completo sobre los bytes de un archivo (PDF o Excel).

    Returns
    -------
    zip_bytes : bytes
    meta      : dict  — customer, po_number, records, errors, warnings, files
    """
    sl = StructuredLogger(pdf_filename=pdf_filename)
    sl.pipeline_started()

    generated_files: list[str] = []

    try:
        # ── 1. Detección y parseo de documento ───────────────────────────────
        detector = DocumentDetector()
        mos_header, mos_records = detector.detect_and_parse(
            file_bytes=pdf_bytes,
            filename=pdf_filename or "upload",
        )

        sl.pdf_read(pages=0, tables=0)          # detector maneja internamente
        sl.records_extracted(len(mos_records))

        logger.info(
            "Header → Customer=%r  PO No=%r",
            mos_header.customer,
            mos_header.po_number,
        )

        # ── 2. Validación ────────────────────────────────────────────────────
        engine = ValidationEngine()
        report = engine.run(mos_header, mos_records)
        sl.validation_done(
            errors=len(report.errors()),
            warnings=len(report.warnings()),
        )

        if report.has_errors:
            reason = f"{len(report.errors())} error(es) de validación"
            sl.generation_blocked(reason)
            sl.pipeline_finished(
                customer=mos_header.customer,
                po_number=mos_header.po_number,
                records=len(mos_records),
                errors=len(report.errors()),
                warnings=len(report.warnings()),
                status="blocked",
                error_detail=report.summary(),
            )
            raise ValueError(f"Generación bloqueada: {reason}\n{report.summary()}")

        # ── 3. Generadores XML ───────────────────────────────────────────────
        po_number = mos_header.po_number or "UNKNOWN"
        out_dir   = Path(out_base) / po_number
        out_dir.mkdir(parents=True, exist_ok=True)

        po_path = PoLineGenerator().generate(
            mos_header, mos_records, out_dir=str(out_dir)
        )
        generated_files.append(str(po_path))

        rel_path = ReleaseGenerator().generate(
            mos_header, mos_records, out_dir=str(out_dir)
        )
        generated_files.append(str(rel_path))

        price_path = OrderPriceGenerator().generate(
            mos_header, mos_records, out_dir=str(out_dir)
        )
        generated_files.append(str(price_path))

        # ── 4. ZIP ───────────────────────────────────────────────────────────
        zip_bytes = _build_zip([po_path, rel_path, price_path])

        # ── 5. Auditoría ─────────────────────────────────────────────────────
        sl.pipeline_finished(
            customer=mos_header.customer,
            po_number=mos_header.po_number,
            records=len(mos_records),
            errors=len(report.errors()),
            warnings=len(report.warnings()),
            status="success",
            generated_files=generated_files,
        )

        return zip_bytes, {
            "customer":        mos_header.customer,
            "po_number":       mos_header.po_number,
            "records":         len(mos_records),
            "errors":          len(report.errors()),
            "warnings":        len(report.warnings()),
            "generated_files": generated_files,
        }

    except ValueError:
        raise

    except Exception as exc:
        sl.pipeline_failed(exc)
        raise RuntimeError(f"Pipeline falló: {exc}") from exc


def _build_zip(paths: list[Path]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, arcname=p.name)
    return buf.getvalue()