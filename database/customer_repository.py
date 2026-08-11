"""
CustomerRepository — consulta la tabla customers en kimexproduction.

Responsabilidad única: dado un Customer_Code, devolver
el Ship To (campo ubication) correspondiente.

Usa SQLAlchemy Core (sin ORM) para una consulta simple de lectura.
No lanza excepciones hacia afuera — devuelve None si no encuentra.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config.config import get_kimex_db_config

logger = logging.getLogger(__name__)


class CustomerRepository:
    """
    Repositorio de solo lectura sobre kimexproduction.customers.

    Uso:
        repo = CustomerRepository()
        ship_to = repo.get_ship_to("Topre")   # → "TPRA" o None
    """

    def __init__(self) -> None:
        config  = get_kimex_db_config()
        self._engine = create_engine(
            config.url,
            pool_pre_ping=True,   # reconecta si la conexión fue cerrada
            echo=False,
        )
        self._Session = sessionmaker(bind=self._engine)

    # ── API pública ───────────────────────────────────────────────────────────

    def get_ship_to(self, customer_code: str) -> str | None:
        """
        Busca el Ship To (ubication) para el customer_code dado.

        La búsqueda es case-insensitive para tolerar variaciones
        de mayúsculas entre el PDF y la base de datos.

        Devuelve None si no se encuentra el cliente.
        """
        if not customer_code or not customer_code.strip():
            logger.warning("get_ship_to: customer_code vacío.")
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
                    logger.debug("Ship To para %r → %r", customer_code, row[0])
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