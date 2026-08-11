"""
Generador del archivo Release_Upload para Plex ERP.

Produce un XML SpreadsheetML con una fila por part number + fecha.

Campos obligatorios: Customer Code, PO No, Customer Part No,
Part No, Quantity, Due Date.

Ship From: fijo "KeiMx".
Ship To:   consultado en kimexproduction.customers por Customer_Code.
           Si no se encuentra, se deja vacío y se emite WARNING en log.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

from pdf.mos_table_parser import MosHeader, MosRecord
from database.customer_repository import CustomerRepository

logger = logging.getLogger(__name__)

_NS = {
    "ss":   "urn:schemas-microsoft-com:office:spreadsheet",
    "o":    "urn:schemas-microsoft-com:office:office",
    "x":    "urn:schemas-microsoft-com:office:excel",
    "html": "http://www.w3.org/TR/REC-html40",
}

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

_SHIP_FROM = "KeiMx"   # valor fijo de negocio


class ReleaseGenerator:
    """
    Genera Release_Upload_<YYYYMMDD>.xml en el directorio de salida indicado.
    """

    def __init__(self) -> None:
        self._customer_repo = CustomerRepository()

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

        # Resolver Ship To UNA sola vez por documento (mismo cliente en todas las filas)
        ship_to = self._resolve_ship_to(header.customer)

        workbook = self._build_workbook(header, records, ship_to)
        self._write(workbook, out_path)
        return out_path

    # ── Ship To ───────────────────────────────────────────────────────────────

    def _resolve_ship_to(self, customer_code: str | None) -> str:
        if not customer_code:
            logger.warning("Ship To: customer_code vacío, se dejará en blanco.")
            return ""
        ship_to = self._customer_repo.get_ship_to(customer_code)
        if not ship_to:
            logger.warning(
                "Ship To: no se encontró ubication para cliente %r. "
                "Verifica la tabla kimexproduction.customers.",
                customer_code,
            )
            return ""
        return ship_to

    # ── Construcción XML ──────────────────────────────────────────────────────

    def _build_workbook(
        self,
        header:  MosHeader,
        records: list[MosRecord],
        ship_to: str,
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
            table.append(self._data_row(header, rec, ship_to))

        return wb

    def _header_row(self) -> ET.Element:
        row = ET.Element("Row")
        for h in _HEADERS:
            cell = ET.SubElement(row, "Cell", {"ss:StyleID": "Header"})
            data = ET.SubElement(cell, "Data", {"ss:Type": "String"})
            data.text = h
        return row

    def _data_row(
        self, header: MosHeader, rec: MosRecord, ship_to: str
    ) -> ET.Element:
        values = [""] * len(_HEADERS)

        values[0]  = header.customer  or ""          # Customer Code
        values[1]  = ship_to                         # Ship To ← BD
        values[2]  = header.po_number or ""          # PO No
        values[3]  = rec.part_number  or ""          # Customer Part No
        values[5]  = rec.part_number  or ""          # Part No
        values[8]  = str(rec.quantity_qty or "")     # Quantity
        values[9]  = self._convert_date(rec.date)    # Due Date MM/DD/YYYY
        values[10] = _SHIP_FROM                      # Ship From ← fijo

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
            return datetime.strptime(date_str, "%d/%m/%Y").strftime("%m/%d/%Y")
        except ValueError:
            return date_str

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
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n')
            f.write('<?mso-application progid="Excel.Sheet"?>\n')
            f.write(ET.tostring(workbook, encoding="unicode"))