"""
Generador del archivo Po_Line_Upload para Plex ERP.

Produce un XML SpreadsheetML con una fila por part number único.
Campos obligatorios confirmados: Customer Code, PO No, PO Status,
PO Type, PO Date, Terms, Freight Terms, Customer Part No, Part No.

Etapa 12.1: Customer Part No resuelto via PartResolver
            (kimexproduction.customer_part_comparison).
            Part No mantiene el Kimex_Part_No original.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from pdf.mos_table_parser import MosHeader, MosRecord
from generators.part_resolver import PartResolver


_NS = {
    "ss":   "urn:schemas-microsoft-com:office:spreadsheet",
    "o":    "urn:schemas-microsoft-com:office:office",
    "x":    "urn:schemas-microsoft-com:office:excel",
    "html": "http://www.w3.org/TR/REC-html40",
}

_HEADERS = [
    "Customer Code", "PO No", "PO Status", "PO Type", "PO Date",
    "Terms", "FOB", "Freight Terms", "Approved Ship To",
    "Approved Ship From", "Customer Part No", "Customer Part Revision",
    "New Shipper Per Schedule", "New Shipper Per Release No",
    "Container Type", "Master Unit Type", "Standard Pack Quantity",
    "Transportation Adjustment", "Part No", "Part Revision", "Note",
    "Master Price", "Default Carrier", "PO Category", "INCO Terms",
    "Assign All Ship Tos", "Named Place Type", "Named Place Address",
    "Negotiated Place",
]

_FIXED_VALUES = {
    2: "Open",    # PO Status
    3: "Blanket", # PO Type
    5: "Net 30",  # Terms
    7: "C.O.D",   # Freight Terms
    9: "KeiMx",   # Approved Ship From
}


class PoLineGenerator:

    def __init__(self) -> None:
        self._resolver = PartResolver()

    def generate(
        self,
        header:   MosHeader,
        records:  list[MosRecord],
        out_dir:  str | Path = "output",
    ) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Una fila por part number único (preservar orden)
        seen: dict[str, MosRecord] = {}
        for rec in records:
            if rec.part_number and rec.part_number not in seen:
                seen[rec.part_number] = rec
        unique_parts = list(seen.values())

        # Resolver Customer Part No en bulk (una sola query)
        part_map = self._resolver.resolve(
            [r.part_number for r in unique_parts]
        )

        today     = date.today()
        po_date   = today.strftime("%m/%d/%Y")
        file_name = f"PO_Line_Upload_{today.strftime('%Y%m%d')}.xml"
        out_path  = out_dir / file_name

        workbook = self._build_workbook(header, po_date, unique_parts, part_map)
        self._write(workbook, out_path)
        return out_path

    def _build_workbook(
        self,
        header:   MosHeader,
        po_date:  str,
        parts:    list[MosRecord],
        part_map: dict[str, str],
    ) -> ET.Element:
        ET.register_namespace("",     _NS["ss"])
        ET.register_namespace("o",    _NS["o"])
        ET.register_namespace("x",    _NS["x"])
        ET.register_namespace("html", _NS["html"])

        wb = ET.Element(
            "Workbook",
            {
                "xmlns":      _NS["ss"],
                "xmlns:o":    _NS["o"],
                "xmlns:x":    _NS["x"],
                "xmlns:ss":   _NS["ss"],
                "xmlns:html": _NS["html"],
            },
        )
        wb.append(self._styles())

        ws    = ET.SubElement(wb, "Worksheet", {"ss:Name": "Worksheet1"})
        table = ET.SubElement(ws, "Table")

        for i in range(1, len(_HEADERS) + 1):
            ET.SubElement(table, "Column", {
                "ss:AutoFitWidth": "1",
                "ss:Index":        str(i),
                "ss:StyleID":      "String",
            })

        table.append(self._header_row())

        for rec in parts:
            customer_part_no = part_map.get(rec.part_number, rec.part_number)
            table.append(self._data_row(header, po_date, rec, customer_part_no))

        return wb

    def _header_row(self) -> ET.Element:
        row = ET.Element("Row")
        for h in _HEADERS:
            cell = ET.SubElement(row, "Cell", {"ss:StyleID": "Header"})
            data = ET.SubElement(cell, "Data", {"ss:Type": "String"})
            data.text = h
        return row

    def _data_row(
        self,
        header:           MosHeader,
        po_date:          str,
        rec:              MosRecord,
        customer_part_no: str,
    ) -> ET.Element:
        values = [""] * len(_HEADERS)

        values[0]  = header.customer     or ""   # Customer Code
        values[1]  = header.po_number    or ""   # PO No
        values[4]  = po_date                     # PO Date
        values[8]  = header.ubication    or ""   # Approved Ship To ← BD
        values[10] = customer_part_no            # Customer Part No ← BD
        values[18] = rec.part_number     or ""   # Part No ← Kimex original

        for col_idx, val in _FIXED_VALUES.items():
            values[col_idx] = val

        row = ET.Element("Row")
        for val in values:
            cell = ET.SubElement(row, "Cell", {"ss:StyleID": "String"})
            data = ET.SubElement(cell, "Data", {"ss:Type": "String"})
            data.text = val
        return row

    @staticmethod
    def _styles() -> ET.Element:
        styles = ET.Element("Styles")

        s0 = ET.SubElement(styles, "Style", {"ss:ID": "Default"})
        ET.SubElement(s0, "Alignment", {"ss:Vertical": "Bottom"})

        s1 = ET.SubElement(styles, "Style", {"ss:ID": "Header"})
        ET.SubElement(s1, "Font", {"ss:Bold": "1"})

        s2 = ET.SubElement(styles, "Style", {"ss:ID": "String"})
        ET.SubElement(s2, "NumberFormat", {"ss:Format": "@"})

        s3 = ET.SubElement(styles, "Style", {"ss:ID": "DateFormat"})
        ET.SubElement(s3, "NumberFormat", {"ss:Format": "General Date"})

        return styles

    @staticmethod
    def _write(workbook: ET.Element, path: Path) -> None:
        ET.indent(ET.ElementTree(workbook), space="  ")
        header_lines = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<?mso-application progid="Excel.Sheet"?>\n'
        )
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(header_lines)
            f.write(ET.tostring(workbook, encoding="unicode"))