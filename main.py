from database.db import init_db
from database.template_repository import TemplateRepository
from extraction.llm_extractor import LLMExtractor
from parser.parser_factory import ParserFactory
from pdf.pdf_reader import PdfReader

TEMPLATE_FILE = "templates/xml/Order_Price_Upload_Template.xml"
PDF_FILE = "documents/PO_Topre.pdf"

init_db()

# 1. Descubrir y guardar la plantilla (ya probado en etapas anteriores)
template_parser = ParserFactory.get_parser(TEMPLATE_FILE)
template = template_parser.parse(TEMPLATE_FILE)

repository = TemplateRepository()
repository.save(template)

# 2. Leer el PDF del cliente (texto o imagen, según corresponda)
pdf_content = PdfReader().read(PDF_FILE)
print(f"PDF leído: {len(pdf_content.pages)} página(s). "
      f"Capa de texto: {'sí' if pdf_content.has_text_layer else 'no (se usará visión)'}\n")

# 3. Extraer datos del PDF usando el LLM, guiado por los campos de la plantilla
extractor = LLMExtractor()
result = extractor.extract(template, pdf_content)

print(f"Extracción para plantilla '{result.template_name}':\n")
for field in result.fields:
    print(f"  {field.name:<25} = {field.value!r:<30} (confianza={field.confidence})")