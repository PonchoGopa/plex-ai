import os

from parser.base_parser import BaseTemplateParser
from parser.csv_parser import CSVParser
from parser.xml_parser import XMLParser


class ParserFactory:
    """
    Factory que selecciona el parser correcto según la extensión
    del archivo de plantilla.

    Esto es el punto único de extensión del "motor de plantillas":
    para soportar un nuevo formato de plantilla Plex (por ejemplo,
    JSON o Excel .xlsx nativo en el futuro), solo hay que crear la
    clase parser correspondiente y registrarla aquí — nada más en
    el sistema necesita cambiar.
    """

    _parsers_by_extension = {
        ".xml": XMLParser,
        ".csv": CSVParser,
    }

    @classmethod
    def get_parser(cls, file_path: str) -> BaseTemplateParser:
        extension = os.path.splitext(file_path)[1].lower()

        parser_class = cls._parsers_by_extension.get(extension)
        if parser_class is None:
            supported = ", ".join(cls._parsers_by_extension.keys())
            raise ValueError(
                f"No hay parser registrado para la extensión '{extension}'. "
                f"Extensiones soportadas: {supported}"
            )

        return parser_class()