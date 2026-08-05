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
from dataclasses import dataclass
from pdf.pdf_reader import PdfContent


@dataclass
class MosRecord:
    part_number: str
    part_name: str
    model: str
    snp: str
    date: str          # DD/MM/YYYY
    quantity_box: int | None
    quantity_qty: int | None


# Meses en español → número
_MONTH_MAP = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "sep.": 9, "oct.": 10, "nov.": 11, "dic.": 12,
    "ene.": 1, "feb.": 2,
}

# Columnas fijas antes de los días
_FIXED_COLS = 4   # Part Number | Model | SNP | Item

# Días válidos de un mes (para filtrar columnas de agregado)
_VALID_DAYS = set(range(1, 32))

# Palabras que indican columna de agregado (no fecha puntual)
_AGGREGATE_TOKENS = {"total", "sep.", "oct.", "nov.", "dic.", "ene.", "feb.",
                     "mar.", "abr.", "may.", "jun.", "jul.", "ago."}


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


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _extract_table_text(pdf_content: PdfContent) -> str:
    """Extrae el bloque de texto de la tabla (el que tiene ' | ')."""
    for page in pdf_content.pages:
        if page.text and " | " in page.text:
            # Busca el bloque que empieza con la tabla
            for line in page.text.split("\n"):
                if "Part Number" in line and "|" in line:
                    # Retorna desde esta línea hacia adelante
                    idx = page.text.index(line)
                    return page.text[idx:]
    return ""


def _split_rows(table_text: str) -> list[list[str]]:
    """Convierte texto con ' | ' en lista de listas de celdas."""
    rows = []
    for line in table_text.split("\n"):
        if " | " in line or line.startswith(" |"):
            cells = [c.strip() for c in line.split(" | ")]
            rows.append(cells)
    return rows


def _build_date_column_map(rows: list[list[str]]) -> dict[int, str]:
    """
    Construye un dict {índice_columna: "DD/MM/YYYY"} para cada columna
    que representa un día puntual (no agregado mensual).

    Lógica:
    - Fila con mes/año: determina el mes y año activos para el bloque siguiente
    - Fila con números de día: mapea índice → día
    - Combina día + mes + año → fecha
    """
    # Encontrar la fila de días (contiene "1", "2", ..., "31")
    day_row_idx = None
    month_year_row_idx = None

    for i, row in enumerate(rows[:8]):  # solo buscar en las primeras 8 filas
        nums = [c for c in row if c.isdigit() and 1 <= int(c) <= 31]
        if len(nums) >= 20:  # suficientes días para ser la fila de días
            day_row_idx = i
            break

    if day_row_idx is None:
        return {}

    # La fila de mes/año está justo antes de la de días
    month_year_row_idx = day_row_idx - 1

    # Parsear mes/año de la fila correspondiente
    month_year_row = rows[month_year_row_idx] if month_year_row_idx >= 0 else []
    current_month, current_year = _extract_month_year(month_year_row)

    if current_month is None or current_year is None:
        return {}

    # Mapear columnas
    day_row = rows[day_row_idx]
    date_map: dict[int, str] = {}

    for col_idx, cell in enumerate(day_row):
        if col_idx < _FIXED_COLS:
            continue
        cell_lower = cell.lower().strip()
        # Es un número de día válido y no es un token de agregado
        if cell.isdigit() and int(cell) in _VALID_DAYS and cell_lower not in _AGGREGATE_TOKENS:
            day = int(cell)
            date_str = f"{day:02d}/{current_month:02d}/{current_year}"
            date_map[col_idx] = date_str

    return date_map


def _extract_month_year(row: list[str]) -> tuple[int | None, int | None]:
    """Extrae mes y año de una fila como ['', '', '', '', 'agosto', '', ..., '2026', ...]."""
    month = None
    year = None
    for cell in row:
        cell_lower = cell.lower().strip()
        if cell_lower in _MONTH_MAP and month is None:
            month = _MONTH_MAP[cell_lower]
        if re.fullmatch(r"20\d{2}", cell.strip()):
            year = int(cell.strip())
            break  # toma el primer año (el del bloque de días puntuales)
    return month, year


def _extract_records(
    rows: list[list[str]], date_columns: dict[int, str]
) -> list[MosRecord]:
    """
    Itera las filas de datos (a partir de la fila de weekday + 1).
    Cada partida ocupa DOS filas consecutivas: BOX y QTY.
    """
    records: list[MosRecord] = []

    # Encontrar inicio de datos: primera fila cuya col 0 parece un part number
    data_start = _find_data_start(rows)
    if data_start is None:
        return []

    i = data_start
    while i < len(rows) - 1:
        box_row = rows[i]
        qty_row = rows[i + 1]

        # Validar que la fila BOX tenga un part number en col 0
        part_number = box_row[0].strip() if len(box_row) > 0 else ""
        if not part_number or not _looks_like_part_number(part_number):
            i += 1
            continue

        # La fila QTY tiene la descripción en col 0
        part_name = qty_row[0].strip() if len(qty_row) > 0 else ""
        model = box_row[1].strip() if len(box_row) > 1 else ""
        snp = box_row[2].strip() if len(box_row) > 2 else ""

        # Extraer valores por columna de fecha
        for col_idx, date_str in date_columns.items():
            box_val = _parse_number(box_row[col_idx]) if col_idx < len(box_row) else None
            qty_val = _parse_number(qty_row[col_idx]) if col_idx < len(qty_row) else None

            # Solo generar registro si hay al menos un valor
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

        i += 2  # avanzar al par siguiente

    return records


def _find_data_start(rows: list[list[str]]) -> int | None:
    """Encuentra el índice de la primera fila de datos (post-encabezados)."""
    for i, row in enumerate(rows):
        if len(row) > 0 and _looks_like_part_number(row[0].strip()):
            return i
    return None


def _looks_like_part_number(text: str) -> bool:
    """Heurística: part number tiene guiones, dígitos o letras mayúsculas."""
    if not text:
        return False
    # Excluir textos que claramente son encabezados o pie de página
    if text.lower().startswith(("part", "brkt", "reinf", "mos", "production", "create", "<")):
        # Las descripciones empiezan con BRKT/REINF — esas son filas QTY, no BOX
        if text.lower().startswith(("brkt", "reinf")):
            return False
    # Un part number real tiene al menos un dígito
    return bool(re.search(r'\d', text)) and len(text) >= 3


def _parse_number(cell: str) -> int | None:
    """Convierte '3,060' → 3060, '' → None."""
    cell = cell.strip().replace(",", "")
    if not cell:
        return None
    try:
        return int(float(cell))
    except ValueError:
        return None