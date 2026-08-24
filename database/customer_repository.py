"""
CustomerRepository — consulta la tabla customers en kimexproduction.

Responsabilidad única: dado el nombre del cliente (como viene en el PDF),
devolver Customer_Code y ubication.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config.config import get_kimex_db_config

logger = logging.getLogger(__name__)


@dataclass
class CustomerRecord:
    customer_code: str
    ubication:     str


class CustomerRepository:
    """
    Repositorio de solo lectura sobre kimexproduction.customers.

    Uso:
        repo = CustomerRepository()
        rec  = repo.get_by_name("Topre")
        # rec.customer_code → "Topre"  (Customer_Code en Plex)
        # rec.ubication     → "TPRA"   (Ship To)
    """

    def __init__(self) -> None:
        config = get_kimex_db_config()
        self._engine  = create_engine(config.url, pool_pre_ping=True, echo=False)
        self._Session = sessionmaker(bind=self._engine)

    # ── API pública ───────────────────────────────────────────────────────────

    def get_by_name(self, name: str) -> Optional[CustomerRecord]:
        """
        Busca por el campo `name` (nombre completo del cliente en el PDF).
        Búsqueda case-insensitive y tolerante a espacios extra, acentos y abreviaciones.
        Devuelve CustomerRecord con Customer_Code y ubication, o None.
        """
        if not name or not name.strip():
            logger.warning("get_by_name: name vacío.")
            return None

        # 1. Obtener todos los clientes de la base de datos para búsqueda en memoria
        sql = text("""
            SELECT Customer_Code, name, ubication
            FROM   customers
        """)

        try:
            with self._session() as session:
                rows = session.execute(sql).fetchall()
        except Exception as exc:
            logger.error("Error consultando lista de clientes: %s", exc)
            return None

        import unicodedata
        import re

        def clean_string(s: str) -> str:
            if not s:
                return ""
            s = s.strip().lower()
            # Eliminar acentos y diacríticos
            s = "".join(
                c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn'
            )
            # Reemplazar caracteres especiales y puntuación con espacios
            s = re.sub(r'[^a-z0-9\-]', ' ', s)
            return " ".join(s.split())

        target = clean_string(name)
        if not target:
            return None

        # Mapeo manual de palabras clave a Customer_Code para mayor precisión
        keyword_mappings = {
            "topre": "Topre",
            "ytec": "YKM",
            "y-tec": "YKM",
            "ykm": "YKM",
            "keylex": "YKM",
            "sriko": "S-Riko",
            "s-riko": "S-Riko",
            "nissan": "Nissan MX",
            "gemo": "GEMO",
            "gemomex": "GEMO"
        }

        # 2. Intentar buscar por coincidencia de palabras clave manuales primero
        for kw, code in keyword_mappings.items():
            if kw in target:
                for row in rows:
                    if clean_string(row[0]) == clean_string(code):
                        logger.info(
                            "Cliente %r coincidencia por palabra clave %r → Customer_Code=%r ubication=%r",
                            name, kw, row[0], row[2]
                        )
                        return CustomerRecord(
                            customer_code = row[0] or "",
                            ubication     = row[2] or "",
                        )

        # 3. Intentar buscar por coincidencia exacta o substring
        # a) Coincidencia exacta
        for row in rows:
            code_val = row[0] or ""
            name_val = row[1] or ""
            ub_val = row[2] or ""

            clean_code = clean_string(code_val)
            clean_name = clean_string(name_val)

            if target == clean_name or target == clean_code:
                logger.info(
                    "Cliente %r coincidencia exacta → Customer_Code=%r ubication=%r",
                    name, code_val, ub_val
                )
                return CustomerRecord(customer_code=code_val, ubication=ub_val)

        # b) Substring en el nombre o código
        for row in rows:
            code_val = row[0] or ""
            name_val = row[1] or ""
            ub_val = row[2] or ""

            clean_code = clean_string(code_val)
            clean_name = clean_string(name_val)

            if clean_name and (clean_name in target or target in clean_name):
                logger.info(
                    "Cliente %r coincidencia de subcadena en nombre (%r) → Customer_Code=%r ubication=%r",
                    name, name_val, code_val, ub_val
                )
                return CustomerRecord(customer_code=code_val, ubication=ub_val)

            if clean_code and (clean_code in target or target in clean_code):
                logger.info(
                    "Cliente %r coincidencia de subcadena en código (%r) → Customer_Code=%r ubication=%r",
                    name, code_val, code_val, ub_val
                )
                return CustomerRecord(customer_code=code_val, ubication=ub_val)

        logger.warning("Cliente no encontrado en BD por name: %r", name)
        return None

    def get_ship_to(self, customer_code: str) -> str | None:
        """
        Conservado para compatibilidad con código existente.
        Busca por Customer_Code y devuelve ubication.
        """
        if not customer_code or not customer_code.strip():
            return None

        sql = text("""
            SELECT ubication
            FROM   customers
            WHERE  LOWER(Customer_Code) = LOWER(:code)
            LIMIT  1
        """)

        try:
            with self._session() as session:
                row = session.execute(sql, {"code": customer_code.strip()}).fetchone()
                if row:
                    return row[0]
                logger.warning("Cliente no encontrado en BD: %r", customer_code)
                return None
        except Exception as exc:
            logger.error("Error consultando Ship To para %r: %s", customer_code, exc)
            return None

    # ── Privados ──────────────────────────────────────────────────────────────

    @contextmanager
    def _session(self) -> Generator[Session, None, None]:
        session = self._Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()