"""
api/pipeline.py — Orquestador del pipeline completo.

Flujo:
  PDF (bytes) → MosTableParser + MosHeaderParser
              → ValidationEngine
              → PoLineGenerator + ReleaseGenerator
              → ZIP con los 2 XMLs

Etapa 10: instrumentado con StructuredLogger (log estructurado + auditoría MySQL).
"""
from __future__ import annotations

import io
import logging
import tempfile
import traceback
import zipfile
from pathlib import Path
from typing import Optional

import pdfplumber

from database.customer_repository import CustomerRepository
from generators.po_line_generator import PoLineGenerator
from generators.release_generator import ReleaseGenerator
from logging_.structured_logger import StructuredLogger
from pdf.mos_header_parser import MosHeaderParser
from pdf.mos_table_parser import MosTableParser
from validation import ValidationEngine

logger = logging.getLogger(__name__)

_customer_repo = CustomerRepository()


# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    pdf_bytes: bytes,
    pdf_filename: Optional[str] = None,
    out_base: str = "output",
) -> tuple[bytes, dict]:
    """
    Ejecuta el pipeline completo sobre los bytes de un PDF.

    Returns
    -------
    zip_bytes : bytes
        ZIP con los archivos XML generados.
    meta : dict
        Metadatos: customer, po_number, records, errors, warnings, files.

    Raises
    ------
    ValueError
        Si la validación bloquea la generación (has_errors=True).
    RuntimeError
        Para cualquier otro fallo interno.
    """
    sl = StructuredLogger(pdf_filename=pdf_filename)
    sl.pipeline_started()

    generated_files: list[str] = []

    try:
        # ── 1. Leer PDF ───────────────────────────────────────────────────────
        raw_text, raw_tables = _read_pdf(pdf_bytes)
        sl.pdf_read(
            pages=raw_text.count("\n\n"),   # aproximación; PdfReader no accesible aquí
            tables=len(raw_tables),
        )

        # ── 2. Parsear tabla calendario ───────────────────────────────────────
        table_parser = MosTableParser()
        mos_records  = table_parser.parse(raw_tables)
        sl.records_extracted(len(mos_records))

        # ── 3. Parsear header ─────────────────────────────────────────────────
        header_parser = MosHeaderParser()
        mos_header    = header_parser.parse(raw_text)
        logger.info(
            "Header → Customer=%r  PO No=%r",
            mos_header.customer,
            mos_header.po_number,
        )

        # ── 4. Validar ────────────────────────────────────────────────────────
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

        # ── 5. Resolver Ship To (una sola consulta) ───────────────────────────
        ship_to = _resolve_ship_to(mos_header.customer)

        # ── 6. Generar XMLs ───────────────────────────────────────────────────
        po_number   = mos_header.po_number or "UNKNOWN"
        out_dir     = Path(out_base) / po_number
        out_dir.mkdir(parents=True, exist_ok=True)

        po_gen      = PoLineGenerator()
        po_path     = po_gen.generate(mos_header, mos_records, out_dir=str(out_dir))
        generated_files.append(str(po_path))

        rel_gen     = ReleaseGenerator()
        rel_path    = rel_gen.generate(
            mos_header, mos_records,
            ship_to=ship_to,
            out_dir=str(out_dir),
        )
        generated_files.append(str(rel_path))

        # ── 7. Empaquetar ZIP ─────────────────────────────────────────────────
        zip_bytes = _build_zip([po_path, rel_path])

        # ── 8. Auditoría final ────────────────────────────────────────────────
        sl.pipeline_finished(
            customer=mos_header.customer,
            po_number=mos_header.po_number,
            records=len(mos_records),
            errors=len(report.errors()),
            warnings=len(report.warnings()),
            status="success",
            generated_files=generated_files,
        )

        meta = {
            "customer":        mos_header.customer,
            "po_number":       mos_header.po_number,
            "records":         len(mos_records),
            "errors":          len(report.errors()),
            "warnings":        len(report.warnings()),
            "generated_files": generated_files,
        }
        return zip_bytes, meta

    except ValueError:
        raise   # blocked → re-raise sin envolver

    except Exception as exc:
        sl.pipeline_failed(exc)
        raise RuntimeError(f"Pipeline falló: {exc}") from exc


# ── Helpers privados ──────────────────────────────────────────────────────────

def _read_pdf(pdf_bytes: bytes) -> tuple[str, list]:
    """Extrae texto y tablas crudas del PDF en memoria."""
    text_parts: list[str] = []
    raw_tables: list      = []

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t:
                    text_parts.append(t)
                for tbl in page.extract_tables() or []:
                    raw_tables.append(tbl)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return "\n\n".join(text_parts), raw_tables


def _resolve_ship_to(customer: Optional[str]) -> str:
    """Consulta la ubicación del cliente en BD; devuelve cadena vacía si no hay."""
    if not customer:
        return ""
    try:
        rec = _customer_repo.get_by_customer_code(customer)
        return rec.ubication if rec else ""
    except Exception:
        logger.warning(
            "No se pudo resolver Ship To para customer=%r:\n%s",
            customer,
            traceback.format_exc(),
        )
        return ""


def _build_zip(paths: list[Path]) -> bytes:
    """Empaqueta los archivos generados en un ZIP en memoria."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, arcname=p.name)
    return buf.getvalue()