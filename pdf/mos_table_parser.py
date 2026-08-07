"""
Pre-procesador de tabla calendario para Material Order Sheets (MOS) de Topre/KI.

Lee la tabla estructurada que genera PdfReader (filas separadas por ' | ')
y mapea columna → fecha usando los encabezados de día y mes/año.
Devuelve registros listos: no necesita que el LLM cuente columnas.

Estructura esperada de la tabla MOS:
  Fila 0: encabezados fijos (Part Number | Model | SNP | Item | Firm Order | ...)
  Fila 1: "agosto | ... | 2026 | ... | 2027"  ← mes y año de cada bloque
  Fila 2: números de día (1 | 2 | ... | 31 | Total | sep. | oct. ...)
  Fila 3: abreviaturas weekday (sá. | do. | lu. ...)
  Fila 4+: datos de partidas (dos filas por partida: BOX y QTY)
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from pdf.pdf_reader import PdfContent


# ── Dataclasses públicos ──────────────────────────────────────────────────────

@dataclass
class MosRecord:
    part_number:  str
    part_name:    str
    model:        str
    snp:          str
    date:         str           # DD/MM/YYYY
    quantity_box: int | None
    quantity_qty: int | None

    # Aliases para que el motor de validaciones use nombres consistentes
    @property
    def box(self) -> int | None:
        return self.quantity_box

    @property
    def qty(self) -> int | None:
        return self.quantity_qty


@dataclass
class MosHeader:
    customer:   str = ""
    po_number:  str = ""


# ── Clase principal (nueva) ───────────────────────────────────────────────────

class MosTableParser:
    """
    Wrapper orientado a objetos sobre la función parse_mos_table.
    Permite instanciarlo y llamar .parse(tables) desde main.py
    de forma consistente con el resto de parsers del proyecto.
    """

    def parse(self, tables: list) -> list[MosRecord]:
        """
        Recibe la lista de tablas devuelta por PdfReader
        y retorna los MosRecord encontrados.
        """
        if not tables:
            return []
        # PdfReader devuelve PdfContent; si ya viene la lista de tablas
        # la envolvemos en un objeto compatible.
        pseudo_content = _PseudoContent(tables)
        return parse_mos_table(pseudo_content)


# ── Adaptador interno ─────────────────────────────────────────────────────────

class _PseudoContent:
    """
    Adapta la lista de strings de páginas (texto serializado por PdfReader)
    a la interfaz que espera parse_mos_table (.pages con .text).
    """

    def __init__(self, tables: list):
        lines = []
        for item in tables:
            if isinstance(item, str):
                lines.append(item)
            elif isinstance(item, list):
                for row in item:
                    if isinstance(row, list):
                        line = " | ".join(
                            (cell if cell is not None else "") for cell in row
                        )
                        lines.append(line)
        self.pages = [_PseudoPage("\n".join(lines))]


class _PseudoPage:
    def __init__(self, text: str):
        self.text = text


# ── Meses en español → número ─────────────────────────────────────────────────

_MONTH_MAP = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "sep.": 9, "oct.": 10, "nov.": 11, "dic.": 12,
    "ene.": 1, "feb.": 2,
}

_FIXED_COLS       = 4
_VALID_DAYS       = set(range(1, 32))
_AGGREGATE_TOKENS = {
    "total", "sep.", "oct.", "nov.", "dic.",
    "ene.", "feb.", "mar.", "abr.", "may.",
    "jun.", "jul.", "ago.",
}


# ── Función original (conservada intacta) ─────────────────────────────────────

def parse_mos_table(pdf_content: PdfContent) -> list[MosRecord]:
    """
    Punto de entrada principal.
    Extrae los registros de la tabla calendario del MOS.
    """
    table_text = _extract_table_text(pdf_content)
    if not table_text:
        return []

    rows = _split_rows(table_text)
    if len(rows) < 5:
        return []

    date_columns = _build_date_column_map(rows)
    if not date_columns:
        return []

    return _extract_records(rows, date_columns)


# ── Helpers privados (sin cambios) ────────────────────────────────────────────

def _extract_table_text(pdf_content) -> str:
    for page in pdf_content.pages:
        if page.text and " | " in page.text:
            for line in page.text.split("\n"):
                if "Part Number" in line and "|" in line:
                    idx = page.text.index(line)
                    return page.text[idx:]
    return ""


def _split_rows(table_text: str) -> list[list[str]]:
    rows = []
    for line in table_text.split("\n"):
        if " | " in line or line.startswith(" |"):
            cells = [c.strip() for c in line.split(" | ")]
            rows.append(cells)
    return rows


def _build_date_column_map(rows: list[list[str]]) -> dict[int, str]:
    day_row_idx = None

    for i, row in enumerate(rows[:8]):
        nums = [c for c in row if c.isdigit() and 1 <= int(c) <= 31]
        if len(nums) >= 20:
            day_row_idx = i
            break

    if day_row_idx is None:
        return {}

    month_year_row_idx = day_row_idx - 1
    month_year_row = rows[month_year_row_idx] if month_year_row_idx >= 0 else []
    current_month, current_year = _extract_month_year(month_year_row)

    if current_month is None or current_year is None:
        return {}

    day_row = rows[day_row_idx]
    date_map: dict[int, str] = {}

    for col_idx, cell in enumerate(day_row):
        if col_idx < _FIXED_COLS:
            continue
        cell_lower = cell.lower().strip()
        if cell.isdigit() and int(cell) in _VALID_DAYS and cell_lower not in _AGGREGATE_TOKENS:
            day = int(cell)
            date_str = f"{day:02d}/{current_month:02d}/{current_year}"
            date_map[col_idx] = date_str

    return date_map


def _extract_month_year(row: list[str]) -> tuple[int | None, int | None]:
    month = None
    year  = None
    for cell in row:
        cell_lower = cell.lower().strip()
        if cell_lower in _MONTH_MAP and month is None:
            month = _MONTH_MAP[cell_lower]
        if re.fullmatch(r"20\d{2}", cell.strip()):
            year = int(cell.strip())
            break
    return month, year


def _extract_records(
    rows: list[list[str]], date_columns: dict[int, str]
) -> list[MosRecord]:
    records: list[MosRecord] = []
    data_start = _find_data_start(rows)
    if data_start is None:
        return []

    i = data_start
    while i < len(rows) - 1:
        box_row = rows[i]
        qty_row = rows[i + 1]

        part_number = box_row[0].strip() if len(box_row) > 0 else ""
        if not part_number or not _looks_like_part_number(part_number):
            i += 1
            continue

        part_name = qty_row[0].strip() if len(qty_row) > 0 else ""
        model     = box_row[1].strip() if len(box_row) > 1 else ""
        snp       = box_row[2].strip() if len(box_row) > 2 else ""

        for col_idx, date_str in date_columns.items():
            box_val = _parse_number(box_row[col_idx]) if col_idx < len(box_row) else None
            qty_val = _parse_number(qty_row[col_idx]) if col_idx < len(qty_row) else None

            if box_val is not None or qty_val is not None:
                records.append(MosRecord(
                    part_number=part_number,
                    part_name=part_name,
                    model=model,
                    snp=snp,
                    date=date_str,
                    quantity_box=box_val,
                    quantity_qty=qty_val,
                ))

        i += 2

    return records


def _find_data_start(rows: list[list[str]]) -> int | None:
    for i, row in enumerate(rows):
        if len(row) > 0 and _looks_like_part_number(row[0].strip()):
            return i
    return None


def _looks_like_part_number(text: str) -> bool:
    if not text:
        return False
    if text.lower().startswith(("brkt", "reinf")):
        return False
    return bool(re.search(r'\d', text)) and len(text) >= 3


def _parse_number(cell: str) -> int | None:
    cell = cell.strip().replace(",", "")
    if not cell:
        return None
    try:
        return int(float(cell))
    except ValueError:
        return None