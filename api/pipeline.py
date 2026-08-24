"""
api/pipeline.py — Orquestador del pipeline completo.

Etapa 12.1: Customer_Code y ubication resueltos desde BD una sola vez
            y propagados al header antes de los generadores.
"""
from __future__ import annotations

import io
import logging
import traceback
import zipfile
from pathlib import Path
from typing import Optional

from database.customer_repository import CustomerRepository
from generators.order_price_generator import OrderPriceGenerator
from generators.po_line_generator import PoLineGenerator
from generators.release_generator import ReleaseGenerator
from ingestion.document_detector import DocumentDetector
from logging_.structured_logger import StructuredLogger
from validation import ValidationEngine

logger = logging.getLogger(__name__)

_customer_repo = CustomerRepository()


def run_pipeline(
    pdf_bytes:    bytes,
    pdf_filename: Optional[str] = None,
    out_base:     str = "output",
) -> tuple[bytes, dict]:

    sl = StructuredLogger(pdf_filename=pdf_filename)
    sl.pipeline_started()
    generated_files: list[str] = []

    try:
        # ── 1. Detección y parseo ─────────────────────────────────────────────
        detector = DocumentDetector()
        mos_header, mos_records = detector.detect_and_parse(
            file_bytes=pdf_bytes,
            filename=pdf_filename or "upload",
        )
        sl.records_extracted(len(mos_records))

        # ── 2. Resolver Customer_Code y ubication desde BD ────────────────────
        mos_header = _resolve_customer(mos_header)
        logger.info(
            "Header → Customer=%r  PO No=%r  Ship To=%r",
            mos_header.customer,
            mos_header.po_number,
            mos_header.ubication,
        )

        # ── 3. Validación ─────────────────────────────────────────────────────
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

        # ── 4. Generadores XML ────────────────────────────────────────────────
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

        # ── 5. ZIP ────────────────────────────────────────────────────────────
        zip_bytes = _build_zip([po_path, rel_path, price_path])

        # ── 6. Auditoría ──────────────────────────────────────────────────────
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


def _resolve_customer(header):
    """
    Busca el cliente en BD por name (lo que viene del PDF).
    Sobreescribe header.customer con Customer_Code y agrega ubication.
    Si no encuentra, conserva el nombre original y ubication vacío.
    """
    from pdf.mos_table_parser import MosHeader
    rec = _customer_repo.get_by_name(header.customer)
    if rec:
        return MosHeader(
            customer   = rec.customer_code,
            po_number  = header.po_number,
            ubication  = rec.ubication,
        )
    logger.warning(
        "Cliente %r no encontrado en BD — se usa nombre del PDF como Customer Code.",
        header.customer,
    )
    return MosHeader(
        customer  = header.customer,
        po_number = header.po_number,
        ubication = "",
    )


def _build_zip(paths: list[Path]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, arcname=p.name)
    return buf.getvalue()