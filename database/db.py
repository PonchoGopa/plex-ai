from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config.config import DatabaseConfig


class Base(DeclarativeBase):
    pass


def _build_engine():
    config = DatabaseConfig()
    return create_engine(config.url, echo=False)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Crea todas las tablas si no existen."""
    from database.orm_models import TemplateORM, TemplateFieldORM  # noqa: F401
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """Context manager de sesión con commit/rollback automático."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()