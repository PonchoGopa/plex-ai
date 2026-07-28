from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractedField:
    name: str
    value: Optional[str]
    confidence: Optional[float]


@dataclass
class ExtractionResult:
    template_name: str
    fields: list[ExtractedField]