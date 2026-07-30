import json

from integrations.openrouter_client import OpenRouterClient
from models.extraction import ExtractedField, ExtractedRecord, ExtractionResult
from models.template import Template
from pdf.pdf_reader import PdfContent


class LLMExtractor:
    """
    Construye el prompt a partir de los campos de un Template ya
    descubierto, y le pide al LLM que devuelva una LISTA de registros
    (uno por partida/renglón encontrado en el documento), cada uno
    con los mismos campos del template.

    El LLM NUNCA genera XML/CSV ni conoce reglas de negocio de Plex;
    solo interpreta el documento y devuelve datos crudos, replicando
    los campos de encabezado (cliente, PO, fechas) en cada registro
    cuando el documento tiene múltiples partidas.
    """

    def __init__(self, client: OpenRouterClient = None):
        self._client = client or OpenRouterClient()

    def extract(self, template: Template, pdf_content: PdfContent) -> ExtractionResult:
        field_names = [f.name for f in template.fields]

        messages = [
            {"role": "system", "content": self._build_system_prompt(field_names)},
            {
                "role": "user",
                "content": (
                    self._build_text_content(pdf_content)
                    if pdf_content.has_text_layer
                    else self._build_image_content(pdf_content)
                ),
            },
        ]

        raw_response = self._client.complete(messages, json_mode=True)
        records = self._parse_response(raw_response, field_names)

        return ExtractionResult(template_name=template.name, records=records)

    def _build_system_prompt(self, field_names: list[str]) -> str:
        fields_list = ", ".join(field_names)
        return (
            "Eres un asistente que extrae información de documentos "
            "(órdenes de compra, facturas, hojas de material) para "
            "importarla a un ERP.\n\n"
            "REGLA CRÍTICA sobre fechas: los documentos suelen tener fechas de "
            "METADATA en el encabezado o título (fecha de emisión, número de "
            "revisión, fecha de revisión del formato) que NO son fechas de "
            "entrega ni aplican a ninguna partida. NUNCA uses una fecha de "
            "revisión/emisión del documento como valor de un campo de fecha "
            "de una partida (ej. fecha efectiva, fecha de entrega). Si no "
            "encuentras una fecha que corresponda específicamente a esa "
            "partida, usa null.\n\n"
            "REGLA CRÍTICA sobre calendarios de entrega: si el documento "
            "contiene una tabla tipo calendario (columnas por día del mes, "
            "con el mes/año indicado en algún encabezado de esa tabla), y "
            "una partida tiene cantidad en MÁS DE UNA columna de día, debes "
            "generar UN REGISTRO POR CADA COLUMNA DE DÍA QUE TENGA CANTIDAD "
            "para esa partida (no solo la primera). La fecha completa de "
            "cada uno de esos registros se construye combinando el mes/año "
            "de la tabla con el número de día de esa columna específica — "
            "nunca con una fecha de revisión o emisión del documento.\n\n"
            "El documento puede contener UNA O VARIAS partidas/renglones. "
            "Si además cada partida tiene varias fechas con cantidad, cada "
            "combinación partida+fecha es un registro separado. Si el "
            "documento tiene datos de encabezado que aplican a todas las "
            "partidas (cliente, número de orden), repite esos mismos "
            "valores en cada registro.\n\n"
            "Devuelve ÚNICAMENTE un objeto JSON con esta forma exacta, "
            "sin texto adicional antes ni después:\n"
            '{"records": [{"fields": [{"name": "<nombre_de_campo>", '
            '"value": "<valor_o_null>", "confidence": <numero_entre_0_y_1>}]}]}\n\n'
            f"Cada registro debe incluir exactamente una entrada por cada uno de "
            f"estos campos: {fields_list}.\n"
            "Si un campo no aparece explícitamente en el documento para esa "
            "partida/fecha, usa value=null y confidence=0.0. No inventes "
            "valores, y no reutilices una fecha de un lugar del documento "
            "para un campo que corresponde a otro dato distinto."
        )

    def _build_text_content(self, pdf_content: PdfContent) -> str:
        full_text = "\n\n".join(
            f"--- Página {p.page_number} ---\n{p.text}"
            for p in pdf_content.pages
            if p.text
        )
        return f"Extrae los registros del siguiente documento:\n\n{full_text}"

    def _build_image_content(self, pdf_content: PdfContent) -> list[dict]:
        content = [
            {
                "type": "text",
                "text": "Extrae los registros del siguiente documento (imagen escaneada):",
            }
        ]
        for page in pdf_content.pages:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{page.image_base64}"},
                }
            )
        return content

    def _parse_response(self, raw_response: str, field_names: list[str]) -> list[ExtractedRecord]:
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"El LLM no devolvió JSON válido: {error}\nRespuesta cruda: {raw_response}"
            )

        raw_records = data.get("records", [])
        if not raw_records:
            raise ValueError(
                f"El LLM no devolvió ningún registro. Respuesta cruda: {raw_response}"
            )

        records = []
        for raw_record in raw_records:
            raw_fields = {
                item.get("name"): item
                for item in raw_record.get("fields", [])
                if isinstance(item, dict)
            }

            fields = [
                ExtractedField(
                    name=name,
                    value=raw_fields.get(name, {}).get("value"),
                    confidence=raw_fields.get(name, {}).get("confidence"),
                )
                for name in field_names
            ]
            records.append(ExtractedRecord(fields=fields))

        return records