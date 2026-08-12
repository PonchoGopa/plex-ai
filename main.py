"""
main.py — Orquestador principal de plex-ai.

Modos de uso:
  python main.py              → pipeline CLI sobre PO_Topre.pdf
  python main.py --serve      → levanta la API FastAPI con Uvicorn
"""
import argparse
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Modo CLI (pipeline directo) ───────────────────────────────────────────────

def run_cli() -> None:
    from pdf.pdf_reader import PdfReader
    from pdf.mos_table_parser import MosTableParser
    from pdf.mos_header_parser import MosHeaderParser
    from validation import ValidationEngine
    from generators.po_line_generator import PoLineGenerator
    from generators.release_generator import ReleaseGenerator

    pdf_path = Path("documents/PO_Topre.pdf")
    if not pdf_path.exists():
        logger.error("PDF no encontrado: %s", pdf_path)
        return

    reader = PdfReader()
    pdf_result = reader.read(str(pdf_path))
    raw_text = pdf_result.text or ""
    raw_tables = pdf_result.tables or []

    logger.info("PDF leído: %d páginas, %d tabla(s)", pdf_result.pages, len(raw_tables))

    table_parser = MosTableParser()
    mos_records = table_parser.parse(raw_tables)
    logger.info("Registros extraídos: %d", len(mos_records))

    header_parser = MosHeaderParser()
    mos_header = header_parser.parse(raw_text)
    logger.info("Header → Customer=%r  PO No=%r", mos_header.customer, mos_header.po_number)

    engine = ValidationEngine()
    report = engine.run(mos_header, mos_records)

    print("\n" + "=" * 60)
    print(report.summary())
    print("=" * 60)

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

    print("=" * 60 + "\n")

    if report.has_errors:
        logger.error("Generación bloqueada por errores de validación.")
        return

    output_dir = Path("output") / (mos_header.po_number or "unknown")
    output_dir.mkdir(parents=True, exist_ok=True)

    po_gen = PoLineGenerator(output_dir=output_dir)
    po_path = po_gen.generate(mos_header, mos_records)
    logger.info("PO Line XML → %s", po_path)

    rel_gen = ReleaseGenerator(output_dir=output_dir)
    rel_path = rel_gen.generate(mos_header, mos_records)
    logger.info("Release XML → %s", rel_path)

    logger.info(
        "Resultado: %d registros, %d error(es), %d advertencia(s)",
        len(mos_records),
        len(report.errors()),
        len(report.warnings()),
    )


# ── Modo API ──────────────────────────────────────────────────────────────────

def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn
    from fastapi import FastAPI
    from api.router import router

    app = FastAPI(
        title="plex-ai",
        description="Automatización de importaciones Plex ERP desde PDFs con IA",
        version="0.9.0",
    )
    app.include_router(router, prefix="/api/v1")

    logger.info("Iniciando servidor en http://%s:%d", host, port)
    logger.info("Documentación: http://%s:%d/docs", host, port)

    uvicorn.run(app, host=host, port=port, log_level="info")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="plex-ai pipeline")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Levanta la API FastAPI con Uvicorn",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Puerto (default: 8000)")
    args = parser.parse_args()

    if args.serve:
        run_server(host=args.host, port=args.port)
    else:
        run_cli()