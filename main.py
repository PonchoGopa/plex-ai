"""
main.py — Orquestador principal de plex-ai.

Flujo actual (Etapa 7):
  PDF → MOS Table Parser + MOS Header Parser
      → ValidationEngine
      → imprime reporte
"""
import logging
from pathlib import Path

from pdf.pdf_reader import PdfReader
from pdf.mos_table_parser import MosTableParser
from pdf.mos_header_parser import MosHeaderParser
from validation import ValidationEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    pdf_path = Path("documents/PO_Topre.pdf")
    if not pdf_path.exists():
        logger.error("PDF no encontrado: %s", pdf_path)
        return

    # ── Lectura del PDF ───────────────────────────────────────────────────────
    reader     = PdfReader()
    pdf_result = reader.read(str(pdf_path))
    raw_text   = pdf_result.text or ""
    raw_tables = pdf_result.tables or []

    logger.info("PDF leído: %d páginas, %d tabla(s)", pdf_result.pages, len(raw_tables))

    # ── Parse de tabla calendario (determinístico) ────────────────────────────
    table_parser = MosTableParser()
    mos_records  = table_parser.parse(raw_tables)
    logger.info("Registros extraídos: %d", len(mos_records))

    # ── Parse de header (Customer + PO No) ───────────────────────────────────
    header_parser = MosHeaderParser()
    mos_header    = header_parser.parse(raw_text)
    logger.info("Header → Customer=%r  PO No=%r", mos_header.customer, mos_header.po_number)

    # ── Validaciones ──────────────────────────────────────────────────────────
    engine = ValidationEngine()
    report = engine.run(mos_header, mos_records)

    print("\n" + "="*60)
    print(report.summary())
    print("="*60)

    if report.results:
        for r in report.results:
            marker = "❌" if r.severity.value == "ERROR" else ("⚠️ " if r.severity.value == "WARNING" else "ℹ️ ")
            detail = ""
            if r.part_number:
                detail += f"  Part: {r.part_number}"
            if r.date:
                detail += f"  Fecha: {r.date}"
            print(f"{marker} [{r.rule}] {r.message}{detail}")
    else:
        print("✅ Todos los registros pasaron la validación sin observaciones.")

    print("="*60 + "\n")

    # Resumen numérico final
    logger.info(
        "Resultado: %d registros, %d error(es), %d advertencia(s)",
        len(mos_records),
        len(report.errors()),
        len(report.warnings()),
    )


if __name__ == "__main__":
    main()