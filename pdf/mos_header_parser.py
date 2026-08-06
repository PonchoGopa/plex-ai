"""
Extractor de campos de encabezado para Material Order Sheets (MOS).

MosHeader se define en pdf.mos_table_parser para que tanto el parser
de tabla como el de header compartan el mismo dataclass sin duplicarlo.
"""

from __future__ import annotations
import re
from pdf.pdf_reader import PdfContent
from pdf.mos_table_parser import MosHeader   # fuente única de verdad


# ── Patrones ──────────────────────────────────────────────────────────────────

# "Material Order Sheet POT260166"
_RE_PO = re.compile(
    r"Material\s+Order\s+Sheet\s+([A-Z0-9\-]+)",
    re.IGNORECASE,
)

# Nombre del cliente antes de "issues Material Order Sheet"
_RE_CUSTOMER_ISSUES = re.compile(
    r"(?:(?:\(cid:\d+\)[A-Z]?)\s*)*([A-Za-z0-9][A-Za-z0-9&\-\s,\.]*?)\s+issues\s+Material\s+Order\s+Sheet",
    re.IGNORECASE,
)

# Fecha de emisión tipo "Rev.02 19/03/2024"
_RE_ISSUE_DATE = re.compile(
    r"Rev\.\d+\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)


# ── Clase principal (nueva) ───────────────────────────────────────────────────

class MosHeaderParser:
    """
    Wrapper OO sobre parse_mos_header().
    Interfaz consistente con MosTableParser.
    """

    def parse(self, text: str) -> MosHeader:
        """
        Recibe el texto plano del PDF (ya extraído por PdfReader)
        y devuelve un MosHeader con customer y po_number.
        """
        return parse_mos_header_from_text(text)


# ── Función original adaptada ─────────────────────────────────────────────────

def parse_mos_header(pdf_content: PdfContent) -> MosHeader:
    """Conservada para compatibilidad con código existente."""
    full_text  = _get_full_text(pdf_content)
    clean_text = _remove_cid_artifacts(full_text)
    return _extract(clean_text)


def parse_mos_header_from_text(raw_text: str) -> MosHeader:
    """Extrae header a partir de texto plano (usado por MosHeaderParser.parse)."""
    clean_text = _remove_cid_artifacts(raw_text)
    return _extract(clean_text)


# ── Lógica interna ────────────────────────────────────────────────────────────

def _extract(clean_text: str) -> MosHeader:
    header = MosHeader()

    m = _RE_PO.search(clean_text)
    header.po_number = m.group(1).strip() if m else None

    m = _RE_CUSTOMER_ISSUES.search(clean_text)
    header.customer = m.group(1).strip() if m else None

    return header


def _get_full_text(pdf_content: PdfContent) -> str:
    return "\n".join(p.text for p in pdf_content.pages if p.text)


def _remove_cid_artifacts(text: str) -> str:
    return re.sub(r"\(cid:\d+\)[A-Z]?", "", text)