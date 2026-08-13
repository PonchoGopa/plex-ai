"""
logging_/structured_logger.py

StructuredLogger: escribe a Python logging estándar + MySQL en cada evento
relevante del pipeline. No lanza excepciones hacia el caller — los fallos de
auditoría solo se loggean como WARNING para no interrumpir el pipeline.

Uso típico
----------
    sl = StructuredLogger(pdf_filename="PO_Topre.pdf")
    sl.pipeline_started()
    ...
    sl.pipeline_finished(
        customer="Topre",
        po_number="POT260166",
        records=36,
        errors=0,
        warnings=0,
        generated_files=["output/POT260166/po_line.xml"],
        status="success",
    )
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime
from typing import List, Optional

from database.audit_repository import AuditRepository

_logger = logging.getLogger(__name__)


class StructuredLogger:
    """
    Instrumenta una única ejecución del pipeline.

    Patrón: instanciar al inicio, llamar pipeline_started(),
    y pipeline_finished() (o pipeline_failed()) al final.
    """

    def __init__(self, pdf_filename: Optional[str] = None) -> None:
        self._pdf_filename  = pdf_filename
        self._run_id: Optional[int] = None
        self._started_at: Optional[datetime] = None
        self._repo = AuditRepository()

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def pipeline_started(self) -> None:
        """Registra el inicio. Persiste un run en BD y guarda el timestamp."""
        self._started_at = datetime.utcnow()
        _logger.info(
            "Pipeline iniciado | pdf=%s",
            self._pdf_filename or "—",
        )
        try:
            self._run_id = self._repo.start_run(pdf_filename=self._pdf_filename)
            _logger.debug("Audit run_id=%d creado.", self._run_id)
        except Exception:
            _logger.warning(
                "AuditRepository.start_run falló (pipeline continúa):\n%s",
                traceback.format_exc(),
            )

    def pipeline_finished(
        self,
        *,
        customer: Optional[str]    = None,
        po_number: Optional[str]   = None,
        records: int               = 0,
        errors: int                = 0,
        warnings: int              = 0,
        status: str                = "success",   # success | blocked | error
        error_detail: Optional[str]= None,
        generated_files: List[str] = None,
    ) -> None:
        """Registra el resultado final en log y BD."""
        elapsed = self._elapsed_str()
        _logger.info(
            "Pipeline finalizado | status=%s | customer=%s | po=%s | "
            "records=%d | errors=%d | warnings=%d | duration=%s",
            status,
            customer or "—",
            po_number or "—",
            records,
            errors,
            warnings,
            elapsed,
        )
        if generated_files:
            for f in generated_files:
                _logger.info("  Archivo generado: %s", f)

        if not self._run_id:
            return

        try:
            self._repo.finish_run(
                self._run_id,
                customer=customer,
                po_number=po_number,
                records_extracted=records,
                errors_count=errors,
                warnings_count=warnings,
                status=status,
                error_detail=error_detail,
                generated_files=generated_files or [],
                started_at=self._started_at,
            )
        except Exception:
            _logger.warning(
                "AuditRepository.finish_run falló (pipeline ya terminó):\n%s",
                traceback.format_exc(),
            )

    def pipeline_failed(self, exc: Exception) -> None:
        """Atajo para errores no controlados."""
        detail = traceback.format_exc()
        _logger.error("Pipeline falló con excepción: %s", exc)
        self.pipeline_finished(
            status="error",
            error_detail=detail,
        )

    # ── Eventos intermedios (solo log, no BD) ─────────────────────────────────

    def pdf_read(self, pages: int, tables: int) -> None:
        _logger.info("PDF leído | páginas=%d | tablas=%d", pages, tables)

    def records_extracted(self, count: int) -> None:
        _logger.info("Registros extraídos: %d", count)

    def validation_done(self, errors: int, warnings: int) -> None:
        level = logging.WARNING if errors or warnings else logging.INFO
        _logger.log(
            level,
            "Validación completada | errors=%d | warnings=%d",
            errors,
            warnings,
        )

    def generation_blocked(self, reason: str) -> None:
        _logger.warning("Generación bloqueada: %s", reason)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _elapsed_str(self) -> str:
        if not self._started_at:
            return "—"
        secs = (datetime.utcnow() - self._started_at).total_seconds()
        return f"{secs:.2f}s"