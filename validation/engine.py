"""
Motor de validaciones para documentos MOS.

Orquesta la ejecución de todas las reglas registradas y devuelve
un ValidationReport consolidado. No lanza excepciones — cualquier
error inesperado dentro de una regla se captura y se convierte en
un ValidationResult de severidad ERROR.
"""
import logging
from pdf.mos_table_parser import MosHeader, MosRecord
from validation.models import ValidationResult, ValidationReport, Severity
from validation.rules import (
    ValidationRule,
    RequiredHeaderFieldsRule,
    NullPartNumberRule,
    BoxSnpQtyRule,
    BusinessDayRule,
    DuplicateRecordRule,
)

logger = logging.getLogger(__name__)


class ValidationEngine:
    """
    Ejecuta una lista ordenada de ValidationRule sobre (header, records).

    Uso básico:
        engine = ValidationEngine()
        report = engine.run(header, records)
        if report.has_errors:
            ...
    """

    def __init__(self, rules: list[ValidationRule] | None = None):
        """
        Si no se pasan reglas, usa el conjunto predeterminado.
        Pasar reglas explícitas permite tests unitarios con reglas aisladas.
        """
        self._rules: list[ValidationRule] = rules if rules is not None else self._default_rules()

    # ── API pública ───────────────────────────────────────────────────────────

    def run(self, header: MosHeader, records: list[MosRecord]) -> ValidationReport:
        """Ejecuta todas las reglas y devuelve el reporte consolidado."""
        report = ValidationReport()

        for rule in self._rules:
            try:
                findings = rule.validate(header, records)
                report.results.extend(findings)
                if findings:
                    logger.debug(
                        "[%s] %d hallazgo(s)", rule.name, len(findings)
                    )
            except Exception as exc:                        # pragma: no cover
                # Una regla no debe romper las demás
                logger.exception("Error inesperado en regla %s: %s", rule.name, exc)
                report.results.append(ValidationResult(
                    severity = Severity.ERROR,
                    rule     = rule.name,
                    message  = f"Error interno ejecutando la regla: {exc}",
                ))

        self._log_summary(report)
        return report

    def add_rule(self, rule: ValidationRule) -> None:
        """Agrega una regla en tiempo de ejecución (extensibilidad)."""
        self._rules.append(rule)

    # ── Privados ──────────────────────────────────────────────────────────────

    @staticmethod
    def _default_rules() -> list[ValidationRule]:
        """
        Orden deliberado:
        1. Header primero (si Customer/PO faltan, el resto pierde contexto).
        2. Part Number nulo (todas las demás reglas lo necesitan).
        3. Duplicados (detectar antes de validar integridad).
        4. Integridad numérica.
        5. Día hábil (menos crítica, al final).
        """
        return [
            RequiredHeaderFieldsRule(),
            NullPartNumberRule(),
            DuplicateRecordRule(),
            BoxSnpQtyRule(),
            BusinessDayRule(),
        ]

    @staticmethod
    def _log_summary(report: ValidationReport) -> None:
        if report.has_errors:
            logger.warning(report.summary())
            for r in report.errors():
                logger.warning("  [%s] %s", r.rule, r.message)
        elif report.has_warnings:
            logger.info(report.summary())
        else:
            logger.info("Validación OK — sin errores ni advertencias.")