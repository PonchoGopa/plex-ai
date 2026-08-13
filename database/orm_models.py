"""
database/orm_models.py — Modelos ORM SQLAlchemy.
"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, DateTime,
    Float, JSON
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ── Plantillas Plex ───────────────────────────────────────────────────────────

class PlexTemplate(Base):
    __tablename__ = "plex_templates"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(255), unique=True, nullable=False)
    content     = Column(Text,        nullable=False)
    file_type   = Column(String(10),  nullable=False, default="xml")
    created_at  = Column(DateTime,    default=datetime.utcnow)
    updated_at  = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Auditoría de ejecuciones ──────────────────────────────────────────────────

class PipelineRun(Base):
    """
    Registra cada ejecución completa del pipeline.

    Campos clave
    ------------
    status        : 'success' | 'error' | 'blocked'
                      blocked = validación rechazó la generación
    generated_files: lista JSON de rutas relativas de archivos creados
    error_detail  : traza completa si status == 'error'
    """
    __tablename__ = "pipeline_runs"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    started_at       = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at      = Column(DateTime, nullable=True)
    duration_seconds = Column(Float,    nullable=True)

    customer         = Column(String(255), nullable=True)
    po_number        = Column(String(100), nullable=True)
    pdf_filename     = Column(String(500), nullable=True)

    records_extracted = Column(Integer, nullable=True)
    errors_count      = Column(Integer, nullable=True, default=0)
    warnings_count    = Column(Integer, nullable=True, default=0)

    status            = Column(String(20), nullable=False, default="success")
    error_detail      = Column(Text,       nullable=True)

    # Lista JSON: ["output/POT260166/po_line.xml", "output/POT260166/release.xml"]
    generated_files   = Column(JSON, nullable=True)