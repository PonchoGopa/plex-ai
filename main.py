"""
main.py — Orquestador principal de plex-ai (CLI).

Etapa 12: detección automática de cliente.
Acepta cualquier archivo soportado (PDF Topre, PDF Y-tec, Excel S-Riko).
"""
import logging
import sys
from pathlib import Path

from ingestion.document_detector import DocumentDetector
from validation import ValidationEngine
from generators.po_line_generator import PoLineGenerator
from generators.release_generator import ReleaseGenerator
from generators.order_price_generator import OrderPriceGenerator
from logging_.structured_logger import StructuredLogger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main(file_path: str | None = None) -> None:
    # Acepta ruta como argumento o usa el PDF de Topre por defecto
    if file_path is None:
        file_path = sys.argv[1] if len(sys.argv) > 1 else "documents/PO_Topre.pdf"

    path = Path(file_path)
    if not path.exists():
        logger.error("Archivo no encontrado: %s", path)
        return

    sl = StructuredLogger(pdf_filename=path.name)
    sl.pipeline_started()

    try:
        # ── Detección y parseo ────────────────────────────────────────────────
        file_bytes = path.read_bytes()
        detector   = DocumentDetector()
        mos_header, mos_records = detector.detect_and_parse(
            file_bytes=file_bytes,
            filename=path.name,
        )

        sl.records_extracted(len(mos_records))
        logger.info(
            "Header → Customer=%r  PO No=%r",
            mos_header.customer,
            mos_header.po_number,
        )

        # ── Validación ────────────────────────────────────────────────────────
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
            marker = "❌" if r.severity.value == "ERROR" else (
                     "⚠️ " if r.severity.value == "WARNING" else "ℹ️ ")
            detail = ""
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

        # ── Generadores XML ───────────────────────────────────────────────────
        po_number = mos_header.po_number or "UNKNOWN"
        out_dir   = Path("output") / po_number
        out_dir.mkdir(parents=True, exist_ok=True)

        generated: list[str] = []

        po_path = PoLineGenerator().generate(
            mos_header, mos_records, out_dir=str(out_dir)
        )
        generated.append(str(po_path))
        logger.info("PO Line XML     → %s", po_path)

        rel_path = ReleaseGenerator().generate(
            mos_header, mos_records, out_dir=str(out_dir)
        )
        generated.append(str(rel_path))
        logger.info("Release XML     → %s", rel_path)

        price_path = OrderPriceGenerator().generate(
            mos_header, mos_records, out_dir=str(out_dir)
        )
        generated.append(str(price_path))
        logger.info("Order Price XML → %s", price_path)

        # ── Auditoría ─────────────────────────────────────────────────────────
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