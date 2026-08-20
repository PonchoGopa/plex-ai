"""
generators/part_resolver.py

Resuelve Customer_Part_No para una lista de part numbers.
Encapsula la consulta a PartComparisonRepository y aplica el fallback.

Uso:
    resolver = PartResolver()
    mapping  = resolver.resolve(["62123-3W0-A100-H1", "762A4-7LG0A"])
    customer_part = mapping["62123-3W0-A100-H1"]  # Customer_Part_No o mismo valor
"""
from __future__ import annotations

import logging
from database.part_comparison_repository import PartComparisonRepository

logger = logging.getLogger(__name__)


class PartResolver:
    """
    Resuelve Kimex_Part_No → Customer_Part_No en una sola query bulk.
    Si no hay mapeo para una parte, devuelve el mismo Kimex_Part_No.
    """

    def __init__(self) -> None:
        self._repo = PartComparisonRepository()

    def resolve(self, kimex_part_nos: list[str]) -> dict[str, str]:
        """
        Devuelve dict { kimex_part_no → customer_part_no }.
        Garantiza que TODAS las partes de entrada tienen una clave en el dict.
        """
        unique = list(dict.fromkeys(p for p in kimex_part_nos if p))
        if not unique:
            return {}

        mapping = self._repo.get_bulk(unique)

        # Aplicar fallback: si no hay mapeo, usar el mismo part number
        result: dict[str, str] = {}
        for part in unique:
            resolved = mapping.get(part, part)   # fallback = mismo valor
            result[part] = resolved
            if resolved != part:
                logger.debug(
                    "PartResolver: %r → %r", part, resolved
                )

        return result