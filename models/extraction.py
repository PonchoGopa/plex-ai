from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractedField:
    name: str
    value: Optional[str]
    confidence: Optional[float]


@dataclass
class ExtractedRecord:
    """
    Representa una fila que eventualmente se convertirá en un
    renglón del XML/CSV de importación a Plex. Un documento con
    varias partidas (como un Material Order Sheet) genera varios
    ExtractedRecord; un documento de una sola partida genera uno solo.
    """
    fields: list[ExtractedField] = field(default_factory=list)

    def get_value(self, field_name: str) -> Optional[str]:
        for f in self.fields:
            if f.name == field_name:
                return f.value
        return None


@dataclass
class ExtractionResult:
    template_name: str
    records: list[ExtractedRecord] = field(default_factory=list)