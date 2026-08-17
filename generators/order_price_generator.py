"""
generators/order_price_generator.py

Genera Order_Price_Upload_YYYYMMDD.xml con una fila por part number único.
Consulta precios en plex_data.customer_part_price (una sola query bulk).

Columnas (18):
  Customer, Customer PO No, Customer Part No, Customer Part Revision,
  Price, Effective Date, Expiration Date, Account No, Amount,
  Part No, Revision, Breakpoint Quantity, Note, Master Price,
  Active, Unit, Primary Price, Currency
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

from database.customer_part_price_repository import CustomerPartPriceRepository
from pdf.mos_table_parser import MosHeader, MosRecord

logger = logging.getLogger(__name__)

_NS_MAP = {
    "":      "urn:schemas-microsoft-com:office:spreadsheet",
    "o":     "urn:schemas-microsoft-com:office:office",
    "x":     "urn:schemas-microsoft-com:office:excel",
    "ss":    "urn:schemas-microsoft-com:office:spreadsheet",
    "html":  "http://www.w3.org/TR/REC-html40",
}

_HEADERS = [
    "Customer",
    "Customer PO No",
    "Customer Part No",
    "Customer Part Revision",
    "Price",
    "Effective Date",
    "Expiration Date",
    "Account No",
    "Amount",
    "Part No",
    "Revision",
    "Breakpoint Quantity",
    "Note",
    "Master Price",
    "Active",
    "Unit",
    "Primary Price",
    "Currency",
]


class OrderPriceGenerator:
    """Genera el XML Order_Price_Upload para Plex ERP."""

    def __init__(self) -> None:
        self._price_repo = CustomerPartPriceRepository()

    def generate(
        self,
        header:  MosHeader,
        records: list[MosRecord],
        out_dir: str | Path = "output",
    ) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Una fila por part number único
        unique_parts: list[str] = []
        seen: set[str] = set()
        for rec in records:
            if rec.part_number and rec.part_number not in seen:
                unique_parts.append(rec.part_number)
                seen.add(rec.part_number)

        # Consulta bulk (una sola query)
        prices = self._price_repo.get_bulk(unique_parts)

        # Construir y escribir XML
        workbook = self._build_xml(header, unique_parts, prices)

        filename = f"Order_Price_Upload_{datetime.now().strftime('%Y%m%d')}.xml"
        out_path = out_dir / filename

        self._write(workbook, out_path)

        logger.info("Order Price XML → %s  (%d filas)", out_path, len(unique_parts))
        return out_path

    # ── Escritura (idéntica a PoLineGenerator) ────────────────────────────────

    @staticmethod
    def _write(workbook: ET.Element, path: Path) -> None:
        """
        Escribe el XML con BOM (utf-8-sig) y la processing instruction
        <?mso-application progid="Excel.Sheet"?> que Plex requiere.
        Mismo método que PoLineGenerator y ReleaseGenerator.
        """
        ET.indent(ET.ElementTree(workbook), space="  ")
        header_lines = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<?mso-application progid="Excel.Sheet"?>\n'
        )
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(header_lines)
            f.write(ET.tostring(workbook, encoding="unicode"))

    # ── Construcción del XML ──────────────────────────────────────────────────

    def _build_xml(
        self,
        header:       MosHeader,
        unique_parts: list[str],
        prices:       dict,
    ) -> ET.Element:
        for prefix, uri in _NS_MAP.items():
            ET.register_namespace(prefix, uri)

        ns = "urn:schemas-microsoft-com:office:spreadsheet"

        workbook = ET.Element(
            "Workbook",
            attrib={
                "xmlns":      ns,
                "xmlns:o":    "urn:schemas-microsoft-com:office:office",
                "xmlns:x":    "urn:schemas-microsoft-com:office:excel",
                "xmlns:ss":   ns,
                "xmlns:html": "http://www.w3.org/TR/REC-html40",
            },
        )

        # Styles
        styles = ET.SubElement(workbook, "Styles")
        self._add_style(styles, "Default", alignment=True)
        self._add_style(styles, "Header",  bold=True)
        self._add_style(styles, "String",  fmt="@")
        self._add_style(styles, "DateFormat", fmt="General Date")

        # Worksheet → Table
        ws    = ET.SubElement(workbook, "Worksheet", attrib={"ss:Name": "Worksheet1"})
        table = ET.SubElement(ws, "Table")

        # Columnas
        for i in range(1, len(_HEADERS) + 1):
            ET.SubElement(table, "Column", attrib={
                "ss:AutoFitWidth": "1",
                "ss:Index":        str(i),
                "ss:StyleID":      "String",
            })

        # Fila de encabezados
        hrow = ET.SubElement(table, "Row")
        for h in _HEADERS:
            cell = ET.SubElement(hrow, "Cell", attrib={"ss:StyleID": "Header"})
            data = ET.SubElement(cell, "Data", attrib={"ss:Type": "String"})
            data.text = h

        # Filas de datos
        for part_no in unique_parts:
            self._add_data_row(table, header, part_no, prices.get(part_no))

        return workbook

    def _add_data_row(
        self,
        table:     ET.Element,
        header:    MosHeader,
        part_no:   str,
        price_rec,
    ) -> None:
        price_str    = str(price_rec.price)          if price_rec else ""
        eff_date_str = (
            price_rec.effective_date.strftime("%m/%d/%Y")
            if price_rec and price_rec.effective_date else ""
        )

        values = [
            header.customer  or "",  # Customer
            header.po_number or "",  # Customer PO No
            part_no,                 # Customer Part No
            part_no,                 # Customer Part Revision
            price_str,               # Price
            eff_date_str,            # Effective Date
            "",                      # Expiration Date
            "",                      # Account No
            "",                      # Amount
            part_no,                 # Part No
            "",                      # Revision
            "",                      # Breakpoint Quantity
            "",                      # Note
            "1",                     # Master Price
            "1",                     # Active
            "Ea",                    # Unit
            "1",                     # Primary Price
            "USD",                   # Currency
        ]

        row = ET.SubElement(table, "Row")
        for val in values:
            cell = ET.SubElement(row, "Cell", attrib={"ss:StyleID": "String"})
            data = ET.SubElement(cell, "Data", attrib={"ss:Type": "String"})
            data.text = val

    @staticmethod
    def _add_style(
        styles:   ET.Element,
        style_id: str,
        bold:     bool = False,
        alignment:bool = False,
        fmt:      Optional[str] = None,
    ) -> None:
        style = ET.SubElement(styles, "Style", attrib={"ss:ID": style_id})
        if alignment:
            ET.SubElement(style, "Alignment", attrib={"ss:Vertical": "Bottom"})
        if bold:
            ET.SubElement(style, "Font", attrib={"ss:Bold": "1"})
        if fmt:
            ET.SubElement(style, "NumberFormat", attrib={"ss:Format": fmt})