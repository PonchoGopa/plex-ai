"""
Extractor de campos de encabezado para Material Order Sheets (MOS).

MosHeader se define en pdf.mos_table_parser para que tanto el parser
de tabla como el de header compartan el mismo dataclass sin duplicarlo.
"""

from __future__ import annotations
import re
from pdf.pdf_reader import PdfContent
from pdf.mos_table_parser import MosHeader


# ── Patrones ──────────────────────────────────────────────────────────────────

# "Material Order Sheet POT260166"
_RE_PO = re.compile(
    r"Material\s+Order\s+Sheet\s+([A-Z0-9\-]+)",
    re.IGNORECASE,
)

# Nombre del cliente antes de "issues Material Order Sheet"
# Captura solo la última línea no vacía antes de "issues"
_RE_CUSTOMER_ISSUES = re.compile(
    r"(?:(?:\(cid:\d+\)[A-Z]?)\s*)*([A-Za-z0-9][A-Za-z0-9&\-\s,\.]*?)\s+issues\s+Material\s+Order\s+Sheet",
    re.IGNORECASE,
)


class MosHeaderParser:
    def parse(self, text: str) -> MosHeader:
        return parse_mos_header_from_text(text)


def parse_mos_header(pdf_content: PdfContent) -> MosHeader:
    """Conservada para compatibilidad con código existente."""
    full_text  = _get_full_text(pdf_content)
    clean_text = _remove_cid_artifacts(full_text)
    return _extract(clean_text)


def parse_mos_header_from_text(raw_text: str) -> MosHeader:
    clean_text = _remove_cid_artifacts(raw_text)
    return _extract(clean_text)


def _extract(clean_text: str) -> MosHeader:
    header = MosHeader()

    # PO Number
    m = _RE_PO.search(clean_text)
    header.po_number = m.group(1).strip() if m else ""

    # Customer: el regex puede capturar varias líneas si hay texto
    # de empresa antes del nombre del cliente (ej: "KI USA MEX...\nTopre").
    # Tomamos solo la última línea no vacía del match.
    m = _RE_CUSTOMER_ISSUES.search(clean_text)
    if m:
        raw_customer = m.group(1).strip()
        # Tomar la última línea no vacía — descarta encabezados de empresa
        lines = [l.strip() for l in raw_customer.splitlines() if l.strip()]
        header.customer = lines[-1] if lines else raw_customer
    else:
        header.customer = ""

    return header


def _get_full_text(pdf_content: PdfContent) -> str:
    return "\n".join(p.text for p in pdf_content.pages if p.text)


def _remove_cid_artifacts(text: str) -> str:
    return re.sub(r"\(cid:\d+\)[A-Z]?", "", text)