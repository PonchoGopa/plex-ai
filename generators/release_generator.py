"""
Generador del archivo Release_Upload para Plex ERP.

Produce un XML SpreadsheetML con una fila por part number + fecha.
Campos obligatorios: Customer Code, PO No, Customer Part No,
Part No, Quantity, Due Date.
Todos los demás campos van vacíos.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

from pdf.mos_table_parser import MosHeader, MosRecord


_NS = {
    "ss":   "urn:schemas-microsoft-com:office:spreadsheet",
    "o":    "urn:schemas-microsoft-com:office:office",
    "x":    "urn:schemas-microsoft-com:office:excel",
    "html": "http://www.w3.org/TR/REC-html40",
}

# 40 columnas en orden exacto de la plantilla
_HEADERS = [
    "Customer Code", "Ship To", "PO No", "Customer Part No",
    "Customer Part Revision", "Part No", "Part Revision", "Release No",
    "Quantity", "Due Date", "Ship From", "EDI Kanban No",
    "EDI Dock Code", "EDI Line Code", "EDI Line 11", "EDI Line 12",
    "EDI Line 13", "EDI Line 14", "EDI Line 15", "EDI Line 16",
    "EDI Line 17", "EDI Material Handling Code", "EDI Reference No",
    "EDI Document", "EDI R Code", "EDI Intermediate Consignee",
    "EDI Load Sequence No", "EDI Lot No", "EDI Batch", "EDI Order No",
    "EDI Dealer No", "Release Type", "Vehicle ID", "Rotation",
    "Usepoint", "Auto Create PO", "Supplier Code", "Drop Ship PO No",
    "Production Start Date", "Schedule Type",
]


class ReleaseGenerator:
    """
    Genera Release_Upload_<YYYYMMDD>.xml en el directorio de salida indicado.
    """

    def generate(
        self,
        header:  MosHeader,
        records: list[MosRecord],
        out_dir: str | Path = "output",
    ) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        today     = date.today()
        file_name = f"Release_Upload_{today.strftime('%Y%m%d')}.xml"
        out_path  = out_dir / file_name

        workbook = self._build_workbook(header, records)
        self._write(workbook, out_path)
        return out_path

    # ── Construcción XML ──────────────────────────────────────────────────────

    def _build_workbook(
        self,
        header:  MosHeader,
        records: list[MosRecord],
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

        for rec in records:
            table.append(self._data_row(header, rec))

        return wb

    def _header_row(self) -> ET.Element:
        row = ET.Element("Row")
        for h in _HEADERS:
            cell = ET.SubElement(row, "Cell", {"ss:StyleID": "Header"})
            data = ET.SubElement(cell, "Data", {"ss:Type": "String"})
            data.text = h
        return row

    def _data_row(self, header: MosHeader, rec: MosRecord) -> ET.Element:
        values = [""] * len(_HEADERS)

        values[0]  = header.customer  or ""          # Customer Code
        values[2]  = header.po_number or ""          # PO No
        values[3]  = rec.part_number  or ""          # Customer Part No
        values[5]  = rec.part_number  or ""          # Part No
        values[8]  = str(rec.quantity_qty or "")     # Quantity
        values[9]  = self._convert_date(rec.date)    # Due Date MM/DD/YYYY

        row = ET.Element("Row")
        for val in values:
            cell = ET.SubElement(row, "Cell", {"ss:StyleID": "String"})
            data = ET.SubElement(cell, "Data", {"ss:Type": "String"})
            data.text = val
        return row

    @staticmethod
    def _convert_date(date_str: str | None) -> str:
        """Convierte DD/MM/YYYY → MM/DD/YYYY (formato Plex)."""
        if not date_str:
            return ""
        try:
            d = datetime.strptime(date_str, "%d/%m/%Y")
            return d.strftime("%m/%d/%Y")
        except ValueError:
            return date_str   # devolver tal cual si el formato es inesperado

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
        tree = ET.ElementTree(workbook)
        ET.indent(tree, space="  ")

        header_lines = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<?mso-application progid="Excel.Sheet"?>\n'
        )
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(header_lines)
            f.write(ET.tostring(workbook, encoding="unicode"))