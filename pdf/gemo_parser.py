"""
pdf/gemo_parser.py

Parser determinístico para documentos de entrega del cliente GEMO
("Planning deliveries without pick up" generado por Crystal Reports).

Reglas de negocio y características:
  - Cliente: GEMO
  - El número de PO precede al número de parte en cada línea de detalle.
  - Formato de fecha: dd.mm.yyyy (se normaliza a DD/MM/YYYY para MosRecord).
  - Formato de cantidad: europeo (ej. 16.500,00 -> 16500).
  - Este cliente maneja sus números de parte específicos (ej. 759033-00, 759034-00).
"""
from __future__ import annotations

import logging
import re

from pdf.mos_table_parser import MosHeader, MosRecord

logger = logging.getLogger(__name__)

# Expresión regular para capturar filas de detalle:
# Ejemplo:
# 26400817 759033-00 metal sheet sheet insert 16.500,00 PC 3.684,99 USD 02.10.2026
_LINE_PATTERN = re.compile(
    r"^\s*(\d+)\s+([\w\-]+)\s+(.+?)\s+([\d\.,]+)\s+([A-Za-z]+)\s+([\d\.,]+(?:\s+[A-Za-z]+)?)\s+(\d{2}\.\d{2}\.\d{4})\s*$",
    re.MULTILINE,
)


class GemoParser:
    """Parser para documentos de entrega del cliente GEMO."""

    def parse(self, raw_text: str) -> tuple[MosHeader, list[MosRecord]]:
        records: list[MosRecord] = []
        po_numbers_found: list[str] = []

        for match in _LINE_PATTERN.finditer(raw_text):
            po_str    = match.group(1).strip()
            part_no   = match.group(2).strip()
            desc      = match.group(3).strip()
            qty_str   = match.group(4).strip()
            # unit   = match.group(5).strip() # ej. PC
            # val    = match.group(6).strip() # ej. 3.684,99 USD
            date_str  = match.group(7).strip()

            date_normalized = self._normalize_date(date_str)
            if not date_normalized:
                continue

            quantity = self._parse_qty(qty_str)
            if quantity == 0:
                continue

            if po_str:
                po_numbers_found.append(po_str)

            records.append(
                MosRecord(
                    part_number  = part_no,
                    part_name    = desc,
                    model        = "",
                    snp          = "",
                    date         = date_normalized,
                    quantity_box = 0,
                    quantity_qty = quantity,
                    po_number    = po_str,
                )
            )

        header_po = po_numbers_found[0] if po_numbers_found else ""
        header = MosHeader(customer="GEMO", po_number=header_po)

        logger.info(
            "GemoParser → customer=%r | po_number=%r | %d registros extraídos",
            header.customer,
            header.po_number,
            len(records),
        )

        return header, records

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """Convierte dd.mm.yyyy a DD/MM/YYYY."""
        m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})$", date_str.strip())
        if not m:
            return ""
        day, month, year = m.group(1), m.group(2), m.group(3)
        return f"{day}/{month}/{year}"

    @staticmethod
    def _parse_qty(qty_str: str) -> int:
        """
        Convierte cantidades en formato europeo (ej. 16.500,00) a entero.
        Elimina separadores de miles (.) y convierte coma decimal a punto.
        """
        cleaned = qty_str.strip().replace(".", "").replace(",", ".")
        try:
            return int(float(cleaned))
        except (ValueError, AttributeError):
            return 0
