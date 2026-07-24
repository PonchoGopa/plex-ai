from database.db import init_db
from database.template_repository import TemplateRepository
from parser.xml_parser import XMLParser

init_db()

parser = XMLParser()
template = parser.parse("templates/xml/Order_Price_Upload_Template.xml")

repository = TemplateRepository()
template_id = repository.save(template)

print(f"Plantilla '{template.name}' guardada en MySQL con id={template_id}\n")

loaded = repository.find_by_name(template.name)

print(f"Plantilla recuperada desde MySQL: {loaded.name} ({len(loaded.fields)} campos)\n")
for f in loaded.fields:
    print(f"  {f.order:>2}. {f.name:<25} ({f.data_type}) requerido={f.required}")