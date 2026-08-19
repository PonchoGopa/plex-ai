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
        records = self._parse_records(raw_tables)
        logger.info(
            "YtecParser → customer=%r | %d registros con Order No",
            header.customer,
            len(records),
        )
        return header, records

    def _parse_header(self, text: str) -> MosHeader:
        customer = "Y-tec"
        m = _CUSTOMER_PATTERN.search(text)
        if m:
            customer = m.group(1).strip()
        return MosHeader(customer=customer, po_number="")

    def _parse_records(self, raw_tables: list) -> list[MosRecord]:
        records: list[MosRecord] = []

        for table in raw_tables:
            if not table or len(table) < 2:
                continue

            header_row = [str(c or "").strip() for c in table[0]]
            if "Parts No" not in " ".join(header_row) and "Order No" not in " ".join(header_row):
                continue

            current_part_no: str = ""
            current_snp: str     = ""

            for row in table[1:]:
                if len(row) < 6:
                    continue

                part_no  = self._cell(row, _COL_PART_NO)
                snp      = self._cell(row, _COL_SNP)
                order_no = self._cell(row, _COL_ORDER_NO)
                date_str = self._cell(row, _COL_DATE)
                qty_str  = self._cell(row, _COL_QUANTITY)

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

        return records

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