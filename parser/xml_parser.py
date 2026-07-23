import os
import xml.etree.ElementTree as ET

from parser.base_parser import BaseTemplateParser
from models.template import Template, TemplateField


class XMLParser(BaseTemplateParser):

    def parse(self, file_path):

        # Namespace utilizado por SpreadsheetML (Excel 2003)
        namespaces = {
            "ss": "urn:schemas-microsoft-com:office:spreadsheet"
        }

        # Leer el archivo XML
        tree = ET.parse(file_path)

        root = tree.getroot()

        worksheet = root.find("ss:Worksheet", namespaces)

        if worksheet is None:
            raise Exception("Worksheet no encontrado.")

        table = worksheet.find("ss:Table", namespaces)

        if table is None:
            raise Exception("Table no encontrada.")