"""
tests/test_gemo_parser.py

Pruebas unitarias para el parser del cliente GEMO y su integración con DocumentDetector.
"""
from pathlib import Path
from pdf.gemo_parser import GemoParser
from ingestion.document_detector import DocumentDetector


def test_gemo_parser_direct():
    pdf_path = Path("documents/Pickup_Gemo.pdf")
    assert pdf_path.exists(), "documents/Pickup_Gemo.pdf debe existir para las pruebas"

    raw_text, _ = DocumentDetector._extract_pdf(pdf_path.read_bytes())
    header, records = GemoParser().parse(raw_text)

    assert header.customer == "GEMO"
    assert header.po_number == "26400817"
    assert len(records) == 8

    # Verificar partes
    part_numbers = {r.part_number for r in records}
    assert part_numbers == {"759033-00", "759034-00"}

    # Verificar PO en registros
    for r in records:
        assert r.po_number == "26400817"
        assert r.quantity_qty == 16500

    # Fechas normalizadas
    dates = {r.date for r in records}
    assert dates == {"02/10/2026", "12/11/2026", "17/12/2026", "28/01/2027"}


def test_document_detector_gemo():
    pdf_path = Path("documents/Pickup_Gemo.pdf")
    detector = DocumentDetector()
    header, records = detector.detect_and_parse(pdf_path.read_bytes(), pdf_path.name)

    assert header.customer == "GEMO"
    assert header.po_number == "26400817"
    assert len(records) == 8


if __name__ == "__main__":
    test_gemo_parser_direct()
    test_document_detector_gemo()
    print("Todos los tests de GEMO pasaron exitosamente.")
