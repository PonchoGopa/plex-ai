from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config.config import get_database_config

config = get_database_config()

engine = create_engine(config.connection_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


@contextmanager
def get_session():
    """
    Context manager de sesión: hace commit si todo sale bien,
    rollback si hay excepción, y siempre cierra la sesión.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    Crea las tablas registradas en Base.metadata si no existen.
    Importa orm_models internamente para que las tablas queden
    registradas en Base.metadata antes de crear el esquema.
    """
    from database import orm_models  # noqa: F401

    Base.metadata.create_all(bind=engine)