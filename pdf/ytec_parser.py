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
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Reutilizamos las mismas dataclasses que el resto del pipeline
from pdf.mos_table_parser import MosHeader, MosRecord


# Índices de columna en la tabla pdfplumber (0-based)
_COL_PART_NO      = 0
_COL_SNP          = 1
_COL_ORDER_NO     = 2
_COL_DATE         = 3
_COL_QUANTITY     = 5

_CUSTOMER_PATTERN = re.compile(
    r"(Y-?tec\s+Keylex\s+Mexico[^\n]*)",
    re.IGNORECASE,
)
_SUPPLIER_NO_PATTERN = re.compile(r"Supplier\s+(\d+)", re.IGNORECASE)


class YtecParser:
    """
    Parser para PDF de Y-tec Keylex.

    Entrada : raw_tables (list[list[list[str]]]) + raw_text (str)
    Salida  : (MosHeader, list[MosRecord])
    """

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

    # ── Header ────────────────────────────────────────────────────────────────

    def _parse_header(self, text: str) -> MosHeader:
        customer = "Y-tec"
        m = _CUSTOMER_PATTERN.search(text)
        if m:
            customer = m.group(1).strip()

        # El PO No a nivel documento no existe en Y-tec;
        # se deja vacío aquí — cada record lleva su propio po_number.
        return MosHeader(customer=customer, po_number="")

    # ── Records ───────────────────────────────────────────────────────────────

    def _parse_records(self, raw_tables: list) -> list[MosRecord]:
        records: list[MosRecord] = []

        for table in raw_tables:
            if not table or len(table) < 2:
                continue

            # Verificar que la tabla tiene la estructura esperada
            header_row = [str(c or "").strip() for c in table[0]]
            if "Parts No" not in " ".join(header_row) and "Order No" not in " ".join(header_row):
                continue

            current_part_no: str = ""

            for row in table[1:]:
                if len(row) < 6:
                    continue

                part_no  = self._cell(row, _COL_PART_NO)
                order_no = self._cell(row, _COL_ORDER_NO)
                date_str = self._cell(row, _COL_DATE)
                qty_str  = self._cell(row, _COL_QUANTITY)

                # Propagar Part No hacia abajo
                if part_no:
                    current_part_no = part_no

                # Sin Order No = forecast → ignorar
                if not order_no:
                    continue

                # Sin Part No propagado → fila inválida
                if not current_part_no:
                    continue

                # Sin fecha válida → ignorar
                date_normalized = self._normalize_date(date_str)
                if not date_normalized:
                    continue

                # Cantidad
                quantity = self._parse_qty(qty_str)
                if quantity == 0:
                    continue

                records.append(MosRecord(
                    part_number  = current_part_no,
                    date         = date_normalized,
                    quantity_box = 0,           # Y-tec no usa box qty en Plex
                    quantity_qty = quantity,
                    po_number    = order_no,    # PO No específico por entrega
                ))

        return records

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _cell(row: list, idx: int) -> str:
        try:
            return str(row[idx] or "").strip()
        except IndexError:
            return ""

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """
        Convierte DD/MM/YY → DD/MM/YYYY.
        Devuelve cadena vacía si no puede parsear.
        """
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