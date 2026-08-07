"""
main.py — Orquestador principal de plex-ai.

Flujo actual (Etapa 8):
  PDF → MOS Table Parser + MOS Header Parser
      → ValidationEngine
      → PoLineGenerator + ReleaseGenerator
      → output/
"""
import logging
from pathlib import Path

from pdf.pdf_reader import PdfReader
from pdf.mos_table_parser import MosTableParser
from pdf.mos_header_parser import MosHeaderParser
from validation import ValidationEngine
from generators import PoLineGenerator, ReleaseGenerator

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

    raw_text = "\n".join(
        p.text for p in pdf_result.pages if p.text
    )
    raw_tables = [
        p.text for p in pdf_result.pages if p.text and "--- Tabla" in p.text
    ]

    logger.info("PDF leído: %d página(s)", len(pdf_result.pages))

    # ── Parse ─────────────────────────────────────────────────────────────────
    table_parser = MosTableParser()
    mos_records  = table_parser.parse(raw_tables)
    logger.info("Registros extraídos: %d", len(mos_records))

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

    # ── Generación de archivos — solo si no hay errores ───────────────────────
    if report.has_errors:
        logger.error("Generación cancelada: existen errores de validación.")
        return

    po_path      = PoLineGenerator().generate(mos_header, mos_records)
    release_path = ReleaseGenerator().generate(mos_header, mos_records)

    logger.info("Archivos generados:")
    logger.info("  PO Line  → %s", po_path)
    logger.info("  Releases → %s", release_path)


if __name__ == "__main__":
    main()