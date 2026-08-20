"""
Reglas de validación para documentos MOS.

Cada regla implementa la ABC ValidationRule con un único método validate().
Para agregar una nueva regla: crear clase, heredar ValidationRule, registrarla
en ValidationEngine.default_rules().
"""
from abc import ABC, abstractmethod
from datetime import date

from pdf.mos_table_parser import MosHeader, MosRecord
from validation.models import ValidationResult, Severity


# ── Contrato ──────────────────────────────────────────────────────────────────

class ValidationRule(ABC):

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def validate(
        self,
        header:  MosHeader,
        records: list[MosRecord],
    ) -> list[ValidationResult]: ...


# ── Regla 1: Part Number nulo ─────────────────────────────────────────────────

class NullPartNumberRule(ValidationRule):

    @property
    def name(self) -> str:
        return "NULL_PART_NUMBER"

    def validate(self, header: MosHeader, records: list[MosRecord]) -> list[ValidationResult]:
        results = []
        for i, rec in enumerate(records):
            if not rec.part_number or not rec.part_number.strip():
                results.append(ValidationResult(
                    severity    = Severity.ERROR,
                    rule        = self.name,
                    message     = f"Registro #{i+1}: part_number está vacío o nulo.",
                    part_number = None,
                    date        = rec.date,
                ))
        return results


# ── Regla 2: Integridad BOX × SNP ≈ QTY ─────────────────────────────────────

class BoxSnpQtyRule(ValidationRule):

    TOLERANCE = 1

    @property
    def name(self) -> str:
        return "BOX_SNP_QTY_INTEGRITY"

    def validate(self, header: MosHeader, records: list[MosRecord]) -> list[ValidationResult]:
        results = []
        for rec in records:
            box = rec.quantity_box
            qty = rec.quantity_qty
            try:
                snp = int(str(rec.snp).replace(",", "").strip())
            except (ValueError, AttributeError):
                continue

            if not box or not snp or not qty:
                continue

            expected = box * snp
            diff = abs(expected - qty)
            if diff > self.TOLERANCE:
                results.append(ValidationResult(
                    severity    = Severity.ERROR,
                    rule        = self.name,
                    message     = (
                        f"Integridad BOX×SNP≠QTY: "
                        f"{box} × {snp} = {expected} ≠ {qty} "
                        f"(diferencia {diff}) — Part: {rec.part_number}, Fecha: {rec.date}"
                    ),
                    part_number = rec.part_number,
                    date        = rec.date,
                    field       = "qty",
                ))
        return results


# ── Regla 3: Fechas en días hábiles ──────────────────────────────────────────

class BusinessDayRule(ValidationRule):

    WEEKDAY_NAMES = {5: "sábado", 6: "domingo"}

    @property
    def name(self) -> str:
        return "BUSINESS_DAY"

    def validate(self, header: MosHeader, records: list[MosRecord]) -> list[ValidationResult]:
        results = []
        seen: set[str] = set()

        for rec in records:
            if not rec.date or rec.date in seen:
                continue
            try:
                day, month, year = map(int, rec.date.split("/"))
                d = date(year, month, day)
                if d.weekday() in self.WEEKDAY_NAMES:
                    seen.add(rec.date)
                    results.append(ValidationResult(
                        severity = Severity.WARNING,
                        rule     = self.name,
                        message  = (
                            f"Fecha {rec.date} cae en "
                            f"{self.WEEKDAY_NAMES[d.weekday()]}. "
                            "Las entregas MOS deben ser días hábiles."
                        ),
                        date  = rec.date,
                        field = "date",
                    ))
            except (ValueError, AttributeError):
                pass
        return results


# ── Regla 4: Duplicados ───────────────────────────────────────────────────────

class DuplicateRecordRule(ValidationRule):

    @property
    def name(self) -> str:
        return "DUPLICATE_RECORD"

    def validate(self, header: MosHeader, records: list[MosRecord]) -> list[ValidationResult]:
        results   = []
        seen: dict[tuple[str, str], int] = {}

        for i, rec in enumerate(records):
            key = (rec.part_number or "", rec.date or "")
            if key in seen:
                results.append(ValidationResult(
                    severity    = Severity.ERROR,
                    rule        = self.name,
                    message     = (
                        f"Registro duplicado: Part={rec.part_number!r} "
                        f"Fecha={rec.date!r} aparece en índices "
                        f"{seen[key]+1} y {i+1}."
                    ),
                    part_number = rec.part_number,
                    date        = rec.date,
                ))
            else:
                seen[key] = i
        return results


# ── Regla 5: Header obligatorio ───────────────────────────────────────────────

class RequiredHeaderFieldsRule(ValidationRule):
    """
    Valida que customer y po_number estén presentes.

    Excepción para po_number: si el header no tiene PO pero TODOS los
    registros tienen su propio po_number (caso Y-tec), la regla pasa.
    Esto permite documentos donde el PO va por entrega, no por documento.
    """

    REQUIRED = ("customer", "po_number")
    LABELS   = {"customer": "Customer", "po_number": "PO No"}

    @property
    def name(self) -> str:
        return "REQUIRED_HEADER_FIELDS"

    def validate(self, header: MosHeader, records: list[MosRecord]) -> list[ValidationResult]:
        results = []
        for attr in self.REQUIRED:
            value = getattr(header, attr, None)
            if not value or not str(value).strip():

                # Excepción: po_number vacío en header es válido si cada
                # registro trae su propio po_number (documentos tipo Y-tec)
                if attr == "po_number" and self._all_records_have_po(records):
                    continue

                results.append(ValidationResult(
                    severity = Severity.ERROR,
                    rule     = self.name,
                    message  = f"Campo obligatorio del header está vacío: {self.LABELS[attr]}.",
                    field    = attr,
                ))
        return results

    @staticmethod
    def _all_records_have_po(records: list[MosRecord]) -> bool:
        """True si hay al menos un registro y todos tienen po_number no vacío."""
        if not records:
            return False
        return all(
            bool(rec.po_number and str(rec.po_number).strip())
            for rec in records
        )