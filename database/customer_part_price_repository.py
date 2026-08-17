"""
database/customer_part_price_repository.py

Consulta precios por Part_No en plex_data.customer_part_price.
Usa las mismas credenciales que plex_template; solo cambia el schema.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


@dataclass
class PartPrice:
    part_no:        str
    price:          Decimal
    effective_date: Optional[date]


class CustomerPartPriceRepository:
    """
    Accede a plex_data.customer_part_price.

    Reutiliza las credenciales DB_* del .env; solo sobreescribe
    el nombre de BD con PLEX_DATA_DB_NAME (default: plex_data).
    """

    def __init__(self) -> None:
        host     = os.getenv("DB_HOST", "localhost")
        port     = os.getenv("DB_PORT", "3306")
        user     = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        db_name  = os.getenv("PLEX_DATA_DB_NAME", "plex_data")

        url = (
            f"mysql+pymysql://{user}:{password}"
            f"@{host}:{port}/{db_name}?charset=utf8mb4"
        )
        engine = create_engine(url, pool_pre_ping=True, echo=False)
        self._Session = sessionmaker(bind=engine)

    # ── Consultas ─────────────────────────────────────────────────────────────

    def get_by_part_no(self, part_no: str) -> Optional[PartPrice]:
        """
        Devuelve Price y Effective_Date para un Part_No dado.
        Si hay varios Customer_No para la misma parte, toma el de menor Customer_No.
        """
        sql = text("""
            SELECT Part_No, Price, Effective_Date
            FROM   customer_part_price
            WHERE  Part_No = :part_no
            ORDER BY Customer_No ASC
            LIMIT  1
        """)
        with self._Session() as session:
            row = session.execute(sql, {"part_no": part_no}).fetchone()

        if row is None:
            logger.warning(
                "CustomerPartPriceRepository: Part_No=%r no encontrado.", part_no
            )
            return None

        return PartPrice(
            part_no        = row.Part_No,
            price          = row.Price,
            effective_date = row.Effective_Date,
        )

    def get_bulk(self, part_nos: list[str]) -> dict[str, PartPrice]:
        """
        Consulta varios Part_No en una sola query compatible con only_full_group_by.
        Usa ROW_NUMBER() para tomar un registro por Part_No (el de menor Customer_No).
        Devuelve dict keyed by Part_No.
        """
        if not part_nos:
            return {}

        sql = text("""
            SELECT Part_No, Price, Effective_Date
            FROM (
                SELECT
                    Part_No,
                    Price,
                    Effective_Date,
                    ROW_NUMBER() OVER (
                        PARTITION BY Part_No
                        ORDER BY Customer_No ASC
                    ) AS rn
                FROM customer_part_price
                WHERE Part_No IN :parts
            ) ranked
            WHERE rn = 1
        """)
        with self._Session() as session:
            rows = session.execute(sql, {"parts": tuple(part_nos)}).fetchall()

        result: dict[str, PartPrice] = {}
        for row in rows:
            result[row.Part_No] = PartPrice(
                part_no        = row.Part_No,
                price          = row.Price,
                effective_date = row.Effective_Date,
            )

        missing = set(part_nos) - set(result)
        if missing:
            logger.warning(
                "CustomerPartPriceRepository: sin precio para: %s",
                ", ".join(sorted(missing)),
            )

        return result