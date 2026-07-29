from database.db import init_db
from database.template_repository import TemplateRepository
from extraction.llm_extractor import LLMExtractor
from parser.parser_factory import ParserFactory
from pdf.pdf_reader import PdfReader

TEMPLATE_FILE = "templates/xml/Order_Price_Upload_Template.xml"
PDF_FILE = "documents/PO_Topre.pdf"

init_db()

template_parser = ParserFactory.get_parser(TEMPLATE_FILE)
template = template_parser.parse(TEMPLATE_FILE)

repository = TemplateRepository()
repository.save(template)

pdf_content = PdfReader().read(PDF_FILE)
print(f"PDF leído: {len(pdf_content.pages)} página(s). "
      f"Capa de texto: {'sí' if pdf_content.has_text_layer else 'no (se usará visión)'}\n")

extractor = LLMExtractor()
result = extractor.extract(template, pdf_content)

print(f"Extracción para plantilla '{result.template_name}': {len(result.records)} registro(s)\n")
for i, record in enumerate(result.records, start=1):
    print(f"--- Registro {i} ---")
    for f in record.fields:
        print(f"  {f.name:<25} = {f.value!r:<30} (confianza={f.confidence})")
    print()