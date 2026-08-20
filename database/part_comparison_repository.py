"""
database/part_comparison_repository.py

Resuelve Customer_Part_No a partir de Kimex_Part_No
en kimexproduction.customer_part_comparison.

Diseño:
  - get_bulk(): una sola query para todos los part numbers del documento
  - Si no existe mapeo, devuelve el mismo Kimex_Part_No (fallback transparente)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class PartComparisonRepository:
    """
    Accede a kimexproduction.customer_part_comparison.
    Mismas credenciales DB_* del .env; usa KIMEX_DB_NAME (default: kimexproduction).
    """

    def __init__(self) -> None:
        host     = os.getenv("DB_HOST", "localhost")
        port     = os.getenv("DB_PORT", "3306")
        user     = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        db_name  = os.getenv("KIMEX_DB_NAME", "kimexproduction")

        url = (
            f"mysql+pymysql://{user}:{password}"
            f"@{host}:{port}/{db_name}?charset=utf8mb4"
        )
        engine = create_engine(url, pool_pre_ping=True, echo=False)
        self._Session = sessionmaker(bind=engine)

    def get_bulk(self, kimex_part_nos: list[str]) -> dict[str, str]:
        """
        Recibe lista de Kimex_Part_No y devuelve dict:
            { kimex_part_no → customer_part_no }

        Si una parte no tiene mapeo, NO aparece en el dict.
        El caller decide el fallback (normalmente usar el mismo kimex_part_no).

        Si hay varios Customer_No para el mismo Kimex_Part_No,
        toma el de menor Customer_No (ROW_NUMBER determinista).
        """
        if not kimex_part_nos:
            return {}

        sql = text("""
            SELECT Kimex_Part_No, Customer_Part_No
            FROM (
                SELECT
                    Kimex_Part_No,
                    Customer_Part_No,
                    ROW_NUMBER() OVER (
                        PARTITION BY Kimex_Part_No
                        ORDER BY Customer_No ASC
                    ) AS rn
                FROM customer_part_comparison
                WHERE Kimex_Part_No IN :parts
                  AND Customer_Part_No IS NOT NULL
                  AND Customer_Part_No != ''
            ) ranked
            WHERE rn = 1
        """)

        with self._Session() as session:
            rows = session.execute(
                sql, {"parts": tuple(kimex_part_nos)}
            ).fetchall()

        result: dict[str, str] = {}
        for row in rows:
            result[row.Kimex_Part_No] = row.Customer_Part_No

        mapped   = len(result)
        unmapped = len(kimex_part_nos) - mapped
        logger.info(
            "PartComparisonRepository: %d partes → %d con mapeo, %d sin mapeo (fallback=kimex_part_no)",
            len(kimex_part_nos), mapped, unmapped,
        )

        return result