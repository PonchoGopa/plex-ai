from parser.xml_parser import XMLParser

parser = XMLParser()

parser.parse("templates/xml/Order_Price_Upload_Template.xml")

print("Plantilla leída correctamente.")