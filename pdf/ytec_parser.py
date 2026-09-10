"""
pdf/ytec_parser.py

Parser determinístico para DELIVERY INSTRUCTION de Y-tec Keylex Mexico.

Reglas de negocio:
  - Solo se procesan filas que tengan Order No (sin Order No = forecast, se ignoran)
  - Part No se propaga hacia abajo cuando la celda está vacía
  - Cada fila con Order No genera un MosRecord independiente
  - PO No = Order No de cada fila (no hay PO global en el documento)
  - Customer fijo: extraído del texto por regex, fallback "Y-tec"
"""
from __future__ import annotations

import logging
import re

from pdf.mos_table_parser import MosHeader, MosRecord

logger = logging.getLogger(__name__)

_COL_PART_NO  = 0
_COL_SNP      = 1
_COL_ORDER_NO = 2
_COL_DATE     = 3
_COL_QUANTITY = 5

_CUSTOMER_PATTERN = re.compile(
    r"(Y-?tec\s+Keylex\s+Mexico[^\n]*)",
    re.IGNORECASE,
)


class YtecParser:

    def parse(
        self,
        raw_text: str,
        raw_tables: list,
    ) -> tuple[MosHeader, list[MosRecord]]:
        header  = self._parse_header(raw_text)
        records, po_numbers = self._parse_records(raw_tables)
        if po_numbers and not header.po_number:
            header.po_number = po_numbers[0]

        logger.info(
            "YtecParser → customer=%r | po_number=%r | %d registros con Order No",
            header.customer,
            header.po_number,
            len(records),
        )
        return header, records

    def _parse_header(self, text: str) -> MosHeader:
        customer = "Y-tec"
        m = _CUSTOMER_PATTERN.search(text)
        if m:
            customer = m.group(1).strip()
        return MosHeader(customer=customer, po_number="")

    def _find_column_indices(self, header_row: list[str]) -> dict[str, int]:
        cols = {
            "part_no":  _COL_PART_NO,
            "snp":      _COL_SNP,
            "order_no": _COL_ORDER_NO,
            "date":     _COL_DATE,
            "qty":      _COL_QUANTITY,
        }
        for idx, cell in enumerate(header_row):
            c = cell.lower().replace("\n", " ").strip()
            if "order" in c:
                cols["order_no"] = idx
            elif "part" in c:
                cols["part_no"] = idx
            elif "snp" in c:
                cols["snp"] = idx
            elif "date" in c or "delivery" in c:
                cols["date"] = idx
            elif ("qty" in c or "quantity" in c) and "box" not in c:
                cols["qty"] = idx
        return cols

    def _parse_records(self, raw_tables: list) -> tuple[list[MosRecord], list[str]]:
        records: list[MosRecord] = []
        po_numbers: list[str] = []

        for table in raw_tables:
            if not table or len(table) < 2:
                continue

            header_idx = -1
            for r_idx in range(min(3, len(table))):
                row_str = " ".join(str(c or "").lower() for c in table[r_idx])
                if "order" in row_str or "part" in row_str:
                    header_idx = r_idx
                    break

            if header_idx == -1:
                continue

            header_row = [str(c or "").strip() for c in table[header_idx]]
            cols = self._find_column_indices(header_row)

            current_part_no: str = ""
            current_snp: str     = ""

            for row in table[header_idx + 1:]:
                min_cols = max(cols.values()) + 1 if cols else 6
                if len(row) < min_cols:
                    continue

                part_no  = self._cell(row, cols["part_no"])
                snp      = self._cell(row, cols["snp"])
                order_no = self._cell(row, cols["order_no"])
                date_str = self._cell(row, cols["date"])
                qty_str  = self._cell(row, cols["qty"])

                # Propagar Part No y SNP hacia abajo
                if part_no:
                    current_part_no = part_no
                if snp:
                    current_snp = snp

                # Sin Order No = forecast → ignorar
                if not order_no:
                    continue

                if not current_part_no:
                    continue

                date_normalized = self._normalize_date(date_str)
                if not date_normalized:
                    continue

                quantity = self._parse_qty(qty_str)
                if quantity == 0:
                    continue

                po_numbers.append(order_no)
                records.append(MosRecord(
                    part_number  = current_part_no,
                    part_name    = "",          # Y-tec no tiene part name
                    model        = "",          # Y-tec no tiene model
                    snp          = current_snp,
                    date         = date_normalized,
                    quantity_box = 0,
                    quantity_qty = quantity,
                    po_number    = order_no,
                ))

        return records, po_numbers

    @staticmethod
    def _cell(row: list, idx: int) -> str:
        try:
            return str(row[idx] or "").strip()
        except IndexError:
            return ""

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})$", date_str.strip())
        if not m:
            return ""
        day, month, year = m.group(1), m.group(2), m.group(3)
        if len(year) == 2:
            year = "20" + year
        return f"{day.zfill(2)}/{month.zfill(2)}/{year}"

    @staticmethod
    def _parse_qty(qty_str: str) -> int:
        try:
            return int(qty_str.replace(",", "").strip())
        except (ValueError, AttributeError):
            return 0