from database.db import init_db
from database.template_repository import TemplateRepository
from parser.parser_factory import ParserFactory
from pdf.pdf_reader import PdfReader
from pdf.mos_table_parser import parse_mos_table

# 1. Inicializar DB
init_db()

# 2. Parsear plantilla y guardar en MySQL
factory = ParserFactory()
parser = factory.get_parser("templates/xml/Price Upload.xml")
template = parser.parse("templates/xml/Price Upload.xml")

repository = TemplateRepository()
repository.save(template)

print(f"Plantilla '{template.name}' guardada. Campos: {len(template.fields)}")

# 3. Leer PDF
reader = PdfReader()
pdf_content = reader.read("documents/PO_Topre.pdf")
print(f"PDF leído: {len(pdf_content.pages)} página(s). Capa de texto: {'sí' if pdf_content.has_text_layer else 'no'}")

# 4. Pre-procesar tabla calendario con Python (sin LLM)
records = parse_mos_table(pdf_content)

print(f"\nTotal de registros extraídos: {len(records)}")
print()

for i, rec in enumerate(records, 1):
    print(
        f"  [{i:02d}] {rec.part_number} | {rec.part_name} | "
        f"Fecha: {rec.date} | BOX: {rec.quantity_box} | QTY: {rec.quantity_qty}"
    )
    