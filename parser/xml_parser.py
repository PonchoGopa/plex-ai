import os
import xml.etree.ElementTree as ET

from parser.base_parser import BaseTemplateParser
from models.template import Template, TemplateField


class XMLParser(BaseTemplateParser):
    """
    Parser para plantillas Plex en formato SpreadsheetML (Excel 2003 XML).

    Descubre automáticamente:
      - Las columnas definidas en <Table><Column .../></Table>
      - El tipo de dato de cada columna, a partir de los estilos
        definidos en <Styles> (NumberFormat/@ss:Format)
      - Los nombres de campo, a partir de la primera fila (encabezado)

    No asume nada específico de una plantilla en particular: toda
    plantilla Plex exportada como SpreadsheetML con esta estructura
    (Styles + Table + Column + Row de encabezado) puede ser leída
    por este mismo parser.
    """

    NS = {
        "ss": "urn:schemas-microsoft-com:office:spreadsheet"
    }

    # Mapeo de formatos numéricos conocidos a tipos de dato del dominio.
    # Se puede extender sin tocar el resto del parser.
    _FORMAT_TO_DATA_TYPE = {
        "@": "String",
        "General Date": "Date",
        "Short Date": "Date",
    }

    def parse(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

        tree = ET.parse(file_path)
        root = tree.getroot()

        style_data_types = self._parse_styles(root)

        worksheet = root.find("ss:Worksheet", self.NS)
        if worksheet is None:
            raise Exception("Worksheet no encontrado.")

        table = worksheet.find("ss:Table", self.NS)
        if table is None:
            raise Exception("Table no encontrada.")

        column_styles = self._parse_columns(table)

        header_row = table.find("ss:Row", self.NS)
        if header_row is None:
            raise Exception("No se encontró la fila de encabezado (Row).")

        fields = self._parse_header_fields(header_row, column_styles, style_data_types)

        if not fields:
            raise Exception("No se pudieron extraer campos desde la fila de encabezado.")

        template_name = os.path.splitext(os.path.basename(file_path))[0]

        return Template(
            name=template_name,
            description="",
            file_type="XML",
            plex_module="",
            fields=fields,
        )

    def _parse_styles(self, root):
        """
        Construye un mapeo {style_id: data_type} inspeccionando
        <Styles><Style ss:ID="..."><NumberFormat ss:Format="..."/></Style></Styles>
        """
        style_data_types = {}

        styles_node = root.find("ss:Styles", self.NS)
        if styles_node is None:
            return style_data_types

        style_id_attr = f"{{{self.NS['ss']}}}ID"
        format_attr = f"{{{self.NS['ss']}}}Format"

        for style in styles_node.findall("ss:Style", self.NS):
            style_id = style.get(style_id_attr)
            if style_id is None:
                continue

            number_format = style.find("ss:NumberFormat", self.NS)
            if number_format is None:
                continue

            fmt = number_format.get(format_attr)
            data_type = self._FORMAT_TO_DATA_TYPE.get(fmt, "String")
            style_data_types[style_id] = data_type

        return style_data_types

    def _parse_columns(self, table):
        """
        Construye un mapeo {indice_columna: style_id} a partir de
        <Column ss:Index="N" ss:StyleID="..."/>

        Respeta ss:Index cuando está presente (permite columnas dispersas);
        si no está presente, asume la siguiente posición secuencial,
        tal como indica la especificación SpreadsheetML.
        """
        index_attr = f"{{{self.NS['ss']}}}Index"
        style_attr = f"{{{self.NS['ss']}}}StyleID"

        column_styles = {}
        current_index = 0

        for column in table.findall("ss:Column", self.NS):
            explicit_index = column.get(index_attr)
            current_index = int(explicit_index) if explicit_index else current_index + 1

            style_id = column.get(style_attr)
            if style_id is not None:
                column_styles[current_index] = style_id

        return column_styles

    def _parse_header_fields(self, header_row, column_styles, style_data_types):
        """
        Recorre las celdas de la fila de encabezado y arma la lista
        de TemplateField, respetando ss:Index en cada Cell (celdas
        dispersas) al igual que en Column.
        """
        index_attr = f"{{{self.NS['ss']}}}Index"

        fields = []
        current_index = 0

        for cell in header_row.findall("ss:Cell", self.NS):
            explicit_index = cell.get(index_attr)
            current_index = int(explicit_index) if explicit_index else current_index + 1

            data_node = cell.find("ss:Data", self.NS)
            if data_node is None or not data_node.text:
                continue

            field_name = data_node.text.strip()

            style_id = column_styles.get(current_index)
            data_type = style_data_types.get(style_id, "String")

            fields.append(
                TemplateField(
                    order=current_index,
                    name=field_name,
                    data_type=data_type,
                    required=False,
                )
            )

        return fields