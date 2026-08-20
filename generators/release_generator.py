"""
Generador del archivo Release_Upload para Plex ERP.

Produce un XML SpreadsheetML con una fila por part number + fecha.

Etapa 12.1: Customer Part No resuelto via PartResolver
            (kimexproduction.customer_part_comparison).
            Part No mantiene el Kimex_Part_No original.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

from pdf.mos_table_parser import MosHeader, MosRecord
from database.customer_repository import CustomerRepository
from generators.part_resolver import PartResolver

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

_SHIP_FROM = "KeiMx"


class ReleaseGenerator:

    def __init__(self) -> None:
        self._customer_repo = CustomerRepository()
        self._resolver      = PartResolver()

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

        # Ship To — una sola consulta por documento
        ship_to = self._resolve_ship_to(header.customer)

        # Customer Part No — una sola query bulk para todas las partes
        unique_part_nos = list(dict.fromkeys(
            r.part_number for r in records if r.part_number
        ))
        part_map = self._resolver.resolve(unique_part_nos)

        workbook = self._build_workbook(header, records, ship_to, part_map)
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
        header:   MosHeader,
        records:  list[MosRecord],
        ship_to:  str,
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

        for rec in records:
            customer_part_no = part_map.get(rec.part_number, rec.part_number)
            # Y-tec: PO No por registro; Topre/S-Riko: PO No del header
            po_no = rec.po_number if rec.po_number else (header.po_number or "")
            table.append(self._data_row(header, rec, ship_to, customer_part_no, po_no))

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
        rec:              MosRecord,
        ship_to:          str,
        customer_part_no: str,
        po_no:            str,
    ) -> ET.Element:
        values = [""] * len(_HEADERS)

        values[0]  = header.customer              or ""  # Customer Code
        values[1]  = ship_to                             # Ship To ← BD
        values[2]  = po_no                               # PO No (header o rec)
        values[3]  = customer_part_no                    # Customer Part No ← BD
        values[5]  = rec.part_number              or ""  # Part No ← Kimex original
        values[8]  = str(rec.quantity_qty or "")         # Quantity
        values[9]  = self._convert_date(rec.date)        # Due Date MM/DD/YYYY
        values[10] = _SHIP_FROM                          # Ship From ← fijo

        row = ET.Element("Row")
        for val in values:
            cell = ET.SubElement(row, "Cell", {"ss:StyleID": "String"})
            data = ET.SubElement(cell, "Data", {"ss:Type": "String"})
            data.text = val
        return row

    @staticmethod
    def _convert_date(date_str: str | None) -> str:
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