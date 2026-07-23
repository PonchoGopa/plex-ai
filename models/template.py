from dataclasses import dataclass, field

@dataclass
class TemplateField:
    order: int
    name: str
    data_type: str = "String"
    required: bool = False


@dataclass
class Template:

    name: str

    description: str = ""

    file_type: str = "XML"

    plex_module: str = ""

    fields: list[TemplateField] = field(default_factory=list)