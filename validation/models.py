"""
Modelos de datos para el motor de validaciones.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    ERROR   = "ERROR"    # Bloquea la generación del archivo
    WARNING = "WARNING"  # Genera el archivo pero lo notifica
    INFO    = "INFO"     # Informativo


@dataclass
class ValidationResult:
    severity:    Severity
    rule:        str          # Nombre de la regla que disparó el resultado
    message:     str          # Descripción legible del problema
    part_number: Optional[str] = None
    date:        Optional[str] = None  # "DD/MM/YYYY"
    field:       Optional[str] = None  # Campo involucrado


@dataclass
class ValidationReport:
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(r.severity == Severity.ERROR for r in self.results)

    @property
    def has_warnings(self) -> bool:
        return any(r.severity == Severity.WARNING for r in self.results)

    def errors(self) -> list[ValidationResult]:
        return [r for r in self.results if r.severity == Severity.ERROR]

    def warnings(self) -> list[ValidationResult]:
        return [r for r in self.results if r.severity == Severity.WARNING]

    def summary(self) -> str:
        e = len(self.errors())
        w = len(self.warnings())
        i = len([r for r in self.results if r.severity == Severity.INFO])
        return f"Validación: {e} error(es), {w} advertencia(s), {i} info(s)"