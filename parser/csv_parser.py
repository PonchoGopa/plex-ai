import csv
import os

from parser.base_parser import BaseTemplateParser
from models.template import Template, TemplateField


class CSVParser(BaseTemplateParser):
    """
    Parser para plantillas Plex en formato CSV.

    A diferencia del XML (SpreadsheetML), el CSV de Plex no trae
    metadata de tipo de dato por columna: solo una fila de
    encabezados. Por eso todos los campos se descubren con
    data_type="String" por defecto. Si en el futuro Plex expone
    CSVs con una fila adicional de tipos (poco común, pero posible
    en otras plantillas), este parser es el único lugar que
    necesitaría cambiar.
    """

    def parse(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

        # utf-8-sig: Plex exporta estos CSV con BOM al inicio del archivo;
        # sin "-sig" el BOM quedaría pegado al primer nombre de campo
        # (ej. "\ufeffCustomer" en vez de "Customer").
        with open(file_path, newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.reader(csv_file)
            try:
                header_row = next(reader)
            except StopIteration:
                raise Exception("El archivo CSV está vacío.")

        fields = self._parse_header_fields(header_row)

        if not fields:
            raise Exception("No se pudieron extraer campos desde el encabezado del CSV.")

        template_name = os.path.splitext(os.path.basename(file_path))[0]

        return Template(
            name=template_name,
            description="",
            file_type="CSV",
            plex_module="",
            fields=fields,
        )

    def _parse_header_fields(self, header_row):
        fields = []

        for position, raw_name in enumerate(header_row, start=1):
            field_name = raw_name.strip()
            if not field_name:
                continue

            fields.append(
                TemplateField(
                    order=position,
                    name=field_name,
                    data_type="String",
                    required=False,
                )
            )

        return fields