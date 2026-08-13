"""
database/audit_repository.py — Persistencia de auditoría de pipeline.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from database.db import get_session
from database.orm_models import PipelineRun

logger = logging.getLogger(__name__)


class AuditRepository:
    """Guarda y consulta registros de ejecución del pipeline."""

    # ── Escritura ─────────────────────────────────────────────────────────────

    def start_run(
        self,
        pdf_filename: Optional[str] = None,
    ) -> int:
        """
        Crea un PipelineRun con status='running' y devuelve su id.
        Se llama al inicio del pipeline para obtener un ID rastreable.
        """
        with get_session() as session:
            run = PipelineRun(
                started_at=datetime.utcnow(),
                pdf_filename=pdf_filename,
                status="running",
            )
            session.add(run)
            session.flush()        # genera el id sin cerrar la transacción
            run_id = run.id
        return run_id

    def finish_run(
        self,
        run_id: int,
        *,
        customer: Optional[str]        = None,
        po_number: Optional[str]       = None,
        records_extracted: int         = 0,
        errors_count: int              = 0,
        warnings_count: int            = 0,
        status: str                    = "success",
        error_detail: Optional[str]    = None,
        generated_files: List[str]     = None,
        started_at: Optional[datetime] = None,
    ) -> None:
        """
        Actualiza el registro con los resultados finales.
        Calcula duration_seconds automáticamente.
        """
        finished_at = datetime.utcnow()
        duration: Optional[float] = None
        if started_at:
            duration = (finished_at - started_at).total_seconds()

        with get_session() as session:
            run: Optional[PipelineRun] = session.get(PipelineRun, run_id)
            if run is None:
                logger.warning("AuditRepository: run_id=%d no encontrado.", run_id)
                return

            run.finished_at        = finished_at
            run.duration_seconds   = duration
            run.customer           = customer
            run.po_number          = po_number
            run.records_extracted  = records_extracted
            run.errors_count       = errors_count
            run.warnings_count     = warnings_count
            run.status             = status
            run.error_detail       = error_detail
            run.generated_files    = generated_files or []

    # ── Lectura (útil para dashboard futuro) ──────────────────────────────────

    def get_recent(self, limit: int = 20) -> List[PipelineRun]:
        """Devuelve los últimos N registros ordenados por fecha desc."""
        with get_session() as session:
            return (
                session.query(PipelineRun)
                .order_by(PipelineRun.started_at.desc())
                .limit(limit)
                .all()
            )