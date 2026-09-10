"""
tests/test_ytec_parser.py

Pruebas unitarias para el parser del cliente Y-tec / YKM y su integración con DocumentDetector.
"""
from pathlib import Path
import pytest
import xml.etree.ElementTree as ET

from pdf.ytec_parser import YtecParser
from ingestion.document_detector import DocumentDetector
from generators.po_line_generator import PoLineGenerator
from generators.order_price_generator import OrderPriceGenerator


def test_ytec_parser_direct():
    pdf_path = Path("documents/ykm.pdf")
    assert pdf_path.exists(), "documents/ykm.pdf debe existir para las pruebas"

    raw_text, raw_tables = DocumentDetector._extract_pdf(pdf_path.read_bytes())
    header, records = YtecParser().parse(raw_text, raw_tables)

    assert "Y-tec" in header.customer
    assert header.po_number == "005549680001"
    assert len(records) == 2  # Filas sin Order No descartadas como forecast

    # Primer registro
    assert records[0].part_number == "VA40-54-314"
    assert records[0].po_number == "005549680001"
    assert records[0].quantity_qty == 2160
    assert records[0].date == "13/08/2026"

    # Segundo registro
    assert records[1].part_number == "VA40-54-314"
    assert records[1].po_number == "005555090001"
    assert records[1].quantity_qty == 1440
    assert records[1].date == "20/08/2026"


def test_document_detector_ytec():
    pdf_path = Path("documents/ykm.pdf")
    detector = DocumentDetector()
    header, records = detector.detect_and_parse(pdf_path.read_bytes(), pdf_path.name)

    assert "Y-tec" in header.customer
    assert header.po_number == "005549680001"
    assert len(records) == 2


def test_ytec_dynamic_columns():
    """Verifica que el parser detecte columnas dinámicamente si el orden cambia."""
    parser = YtecParser()
    raw_text = "Y-tec Keylex Mexico.S.A.de C.V"
    custom_table = [
        ["Order No", "Parts No", "Delivery Date", "SNP", "Quantity", "Box Qty"],
        ["009988770001", "TEST-PART-01", "15/09/26", "50", "500", "10"],
        ["009988770002", "", "22/09/26", "", "1,000", "20"],
        ["", "", "29/09/26", "", "1,000", "20"],  # Forecast (sin Order No)
    ]
    header, records = parser.parse(raw_text, [custom_table])

    assert header.po_number == "009988770001"
    assert len(records) == 2
    assert records[0].part_number == "TEST-PART-01"
    assert records[0].po_number == "009988770001"
    assert records[0].quantity_qty == 500
    assert records[1].part_number == "TEST-PART-01"
    assert records[1].po_number == "009988770002"
    assert records[1].quantity_qty == 1000


def test_po_line_and_order_price_multiple_pos_same_part(tmp_path):
    """Verifica que PO_Line_Upload y Order_Price_Upload incluyan ambas POs aun con el mismo número de parte."""
    from pdf.mos_table_parser import MosHeader, MosRecord

    header = MosHeader(customer="YKM", po_number="005577290001", ubication="YKM")
    records = [
        MosRecord(
            part_number="VA40-54-314",
            part_name="",
            model="",
            snp="10",
            date="13/08/2026",
            quantity_box=0,
            quantity_qty=2160,
            po_number="005577290001",
        ),
        MosRecord(
            part_number="VA40-54-314",
            part_name="",
            model="",
            snp="10",
            date="20/08/2026",
            quantity_box=0,
            quantity_qty=1440,
            po_number="005582930001",
        ),
    ]

    # 1. Probar PO_Line_Upload
    po_file = PoLineGenerator().generate(header, records, out_dir=tmp_path)
    tree_po = ET.parse(po_file)
    rows_po = tree_po.findall(".//{urn:schemas-microsoft-com:office:spreadsheet}Row")
    # Fila 0 es header, filas 1 y 2 son datos
    assert len(rows_po) == 3, f"Esperaba 3 filas en PO_Line_Upload, pero se generaron {len(rows_po)}"

    po_vals = []
    for r in rows_po[1:]:
        cells = r.findall("{urn:schemas-microsoft-com:office:spreadsheet}Cell")
        po_vals.append(cells[1].findtext("{urn:schemas-microsoft-com:office:spreadsheet}Data"))
    assert po_vals == ["005577290001", "005582930001"]

    # 2. Probar Order_Price_Upload
    price_file = OrderPriceGenerator().generate(header, records, out_dir=tmp_path)
    tree_pr = ET.parse(price_file)
    rows_pr = tree_pr.findall(".//{urn:schemas-microsoft-com:office:spreadsheet}Row")
    assert len(rows_pr) == 3, f"Esperaba 3 filas en Order_Price_Upload, pero se generaron {len(rows_pr)}"

    price_pos = []
    primary_prices = []
    for r in rows_pr[1:]:
        cells = r.findall("{urn:schemas-microsoft-com:office:spreadsheet}Cell")
        price_pos.append(cells[1].findtext("{urn:schemas-microsoft-com:office:spreadsheet}Data"))
        primary_prices.append(cells[16].findtext("{urn:schemas-microsoft-com:office:spreadsheet}Data"))
    assert price_pos == ["005577290001", "005582930001"]
    assert primary_prices == ["1", "0"]


if __name__ == "__main__":
    test_ytec_parser_direct()
    test_document_detector_ytec()
    test_ytec_dynamic_columns()
    print("Todos los tests pasaron exitosamente.")
