"""
main.py — Orquestador principal de plex-ai (CLI).

Flujo (Etapa 10):
  PDF → MOS Table Parser + MOS Header Parser
      → ValidationEngine
      → PoLineGenerator + ReleaseGenerator
      → Auditoría MySQL vía StructuredLogger
"""
import logging
from pathlib import Path

from pdf.pdf_reader import PdfReader
from pdf.mos_table_parser import MosTableParser
from pdf.mos_header_parser import MosHeaderParser
from validation import ValidationEngine
from generators.po_line_generator import PoLineGenerator
from generators.release_generator import ReleaseGenerator
from database.customer_repository import CustomerRepository
from logging_.structured_logger import StructuredLogger

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

    sl = StructuredLogger(pdf_filename=pdf_path.name)
    sl.pipeline_started()

    try:
        # ── Lectura del PDF ───────────────────────────────────────────────────
        reader     = PdfReader()
        pdf_result = reader.read(str(pdf_path))
        raw_text   = pdf_result.text or ""
        raw_tables = pdf_result.tables or []

        sl.pdf_read(pages=pdf_result.pages, tables=len(raw_tables))

        # ── Parse de tabla calendario ─────────────────────────────────────────
        table_parser = MosTableParser()
        mos_records  = table_parser.parse(raw_tables)
        sl.records_extracted(len(mos_records))

        # ── Parse de header ───────────────────────────────────────────────────
        header_parser = MosHeaderParser()
        mos_header    = header_parser.parse(raw_text)
        logger.info(
            "Header → Customer=%r  PO No=%r",
            mos_header.customer,
            mos_header.po_number,
        )

        # ── Validaciones ──────────────────────────────────────────────────────
        engine = ValidationEngine()
        report = engine.run(mos_header, mos_records)
        sl.validation_done(
            errors=len(report.errors()),
            warnings=len(report.warnings()),
        )

        print("\n" + "=" * 60)
        print(report.summary())
        print("=" * 60)

        for r in report.results:
            marker  = "❌" if r.severity.value == "ERROR" else (
                      "⚠️ " if r.severity.value == "WARNING" else "ℹ️ ")
            detail  = ""
            if r.part_number:
                detail += f"  Part: {r.part_number}"
            if r.date:
                detail += f"  Fecha: {r.date}"
            print(f"{marker} [{r.rule}] {r.message}{detail}")

        if not report.results:
            print("✅ Todos los registros pasaron la validación sin observaciones.")
        print("=" * 60 + "\n")

        if report.has_errors:
            sl.generation_blocked(f"{len(report.errors())} error(es)")
            sl.pipeline_finished(
                customer=mos_header.customer,
                po_number=mos_header.po_number,
                records=len(mos_records),
                errors=len(report.errors()),
                warnings=len(report.warnings()),
                status="blocked",
                error_detail=report.summary(),
            )
            return

        # ── Resolver Ship To ──────────────────────────────────────────────────
        ship_to = ""
        try:
            repo   = CustomerRepository()
            record = repo.get_by_customer_code(mos_header.customer)
            ship_to = record.ubication if record else ""
        except Exception as exc:
            logger.warning("No se pudo resolver Ship To: %s", exc)

        # ── Generadores XML ───────────────────────────────────────────────────
        po_number  = mos_header.po_number or "UNKNOWN"
        out_dir    = Path("output") / po_number
        out_dir.mkdir(parents=True, exist_ok=True)

        generated: list[str] = []

        po_gen   = PoLineGenerator()
        po_path  = po_gen.generate(mos_header, mos_records, out_dir=str(out_dir))
        generated.append(str(po_path))
        logger.info("PO Line XML → %s", po_path)

        rel_gen  = ReleaseGenerator()
        rel_path = rel_gen.generate(
            mos_header, mos_records,
            ship_to=ship_to,
            out_dir=str(out_dir),
        )
        generated.append(str(rel_path))
        logger.info("Release XML → %s", rel_path)

        # ── Auditoría final ───────────────────────────────────────────────────
        sl.pipeline_finished(
            customer=mos_header.customer,
            po_number=mos_header.po_number,
            records=len(mos_records),
            errors=len(report.errors()),
            warnings=len(report.warnings()),
            status="success",
            generated_files=generated,
        )

    except Exception as exc:
        sl.pipeline_failed(exc)
        logger.error("Error inesperado: %s", exc)


if __name__ == "__main__":
    main()