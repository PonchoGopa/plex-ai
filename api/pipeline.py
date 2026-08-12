"""
api/pipeline.py — Orquesta el pipeline completo para un PDF dado.
"""
import logging
import tempfile
from pathlib import Path

from pdf.pdf_reader import PdfReader
from pdf.mos_table_parser import MosTableParser
from pdf.mos_header_parser import MosHeaderParser
from validation import ValidationEngine
from generators.po_line_generator import PoLineGenerator
from generators.release_generator import ReleaseGenerator

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Error controlado del pipeline (validación bloqueante, parse fallido, etc.)."""


def _extract_text_and_tables(pdf_result) -> tuple[str, list]:
    """
    Extrae texto narrativo y tablas desde un PdfContent.

    PdfContent.pages es una lista de PageContent, cada uno con:
      - .text        → texto combinado (narrativo + tablas serializadas como pipe)
      - .image_base64 → imagen (cuando no hay capa de texto)

    MosTableParser necesita las tablas como listas de listas (estructura raw),
    no el texto serializado. Por eso re-extraemos las tablas directamente
    desde el archivo temporal usando pdfplumber, igual que hace PdfReader
    internamente — pero aquí necesitamos la estructura, no el texto.
    """
    # Texto narrativo: concatenar .text de todas las páginas
    text_parts = []
    for page in pdf_result.pages:
        if page.text:
            text_parts.append(page.text)
    raw_text = "\n\n".join(text_parts)

    # Tablas: PdfContent no expone la estructura raw de tablas como atributo
    # separado; el texto pipe-delimitado es para el LLM. MosTableParser
    # necesita list[list[str]], así que las re-extraemos del PDF directamente.
    # Esto se hace en run_pipeline donde tenemos el path del archivo temporal.
    return raw_text, []


def run_pipeline(pdf_bytes: bytes, output_dir: Path) -> dict:
    """
    Ejecuta el pipeline completo sobre los bytes de un PDF.

    Returns:
        dict con claves: customer, po_number, records_total,
                         errors, warnings, files_generated (list[Path])

    Raises:
        PipelineError: si la validación bloquea la generación o el parse falla.
    """
    import pdfplumber

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Escribir PDF a archivo temporal ───────────────────────────────────
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)

    try:
        # ── 2. Texto narrativo via PdfReader ─────────────────────────────────
        reader = PdfReader()
        pdf_result = reader.read(str(tmp_path))

        raw_text = ""
        for page in pdf_result.pages:
            if page.text:
                raw_text += page.text + "\n\n"
        raw_text = raw_text.strip()

        # ── 3. Tablas raw via pdfplumber (estructura list[list[str]]) ─────────
        raw_tables = []
        with pdfplumber.open(str(tmp_path)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    raw_tables.extend(tables)

        logger.info(
            "PDF leído: %d página(s), %d tabla(s)",
            len(pdf_result.pages),
            len(raw_tables),
        )

        # ── 4. Parse tabla calendario ─────────────────────────────────────────
        table_parser = MosTableParser()
        mos_records = table_parser.parse(raw_tables)

        if not mos_records:
            raise PipelineError("No se encontraron registros en la tabla calendario del PDF.")

        logger.info("Registros extraídos: %d", len(mos_records))

        # ── 5. Parse header ───────────────────────────────────────────────────
        header_parser = MosHeaderParser()
        mos_header = header_parser.parse(raw_text)

        logger.info(
            "Header → Customer=%r  PO No=%r",
            mos_header.customer,
            mos_header.po_number,
        )

        # ── 6. Validación ─────────────────────────────────────────────────────
        engine = ValidationEngine()
        report = engine.run(mos_header, mos_records)

        if report.has_errors:
            error_msgs = [r.message for r in report.errors()]
            raise PipelineError(
                f"Validación bloqueante ({len(error_msgs)} error(es)): "
                + " | ".join(error_msgs)
            )

        # ── 7. Generación XML ─────────────────────────────────────────────────
        files_generated: list[Path] = []

        po_path = PoLineGenerator().generate(mos_header, mos_records, out_dir=output_dir)
        files_generated.append(po_path)
        logger.info("PO Line XML → %s", po_path)

        rel_path = ReleaseGenerator().generate(mos_header, mos_records, out_dir=output_dir)
        files_generated.append(rel_path)
        logger.info("Release XML → %s", rel_path)

        return {
            "customer": mos_header.customer or "",
            "po_number": mos_header.po_number or "",
            "records_total": len(mos_records),
            "errors": len(report.errors()),
            "warnings": len(report.warnings()),
            "files_generated": files_generated,
        }

    finally:
        tmp_path.unlink(missing_ok=True)