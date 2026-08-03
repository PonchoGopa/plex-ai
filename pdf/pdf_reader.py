import base64
from dataclasses import dataclass
from typing import Optional

import fitz  # PyMuPDF
import pdfplumber


MIN_MEANINGFUL_TEXT_LENGTH = 20


@dataclass
class PageContent:
    page_number: int
    text: Optional[str]
    image_base64: Optional[str]


@dataclass
class PdfContent:
    file_path: str
    pages: list[PageContent]

    @property
    def has_text_layer(self) -> bool:
        return any(
            p.text and len(p.text.strip()) >= MIN_MEANINGFUL_TEXT_LENGTH
            for p in self.pages
        )


class PdfReader:
    """
    Lee un PDF y decide automáticamente la estrategia de extracción:

    - Si hay texto real: se extrae texto narrativo (encabezados, notas)
      CON pdfplumber.extract_text(), Y ADEMÁS se detectan tablas con
      pdfplumber.extract_tables(), que preservan la posición exacta
      fila/columna de cada celda. El texto lineal por sí solo destruye
      la alineación de tablas anchas (como calendarios de entrega),
      mezclando valores de columnas distintas — por eso la tabla se
      serializa aparte, con su estructura intacta.
    - Si NO hay texto: se rasteriza a imagen para visión del LLM.
    """

    RASTER_DPI = 150

    def read(self, file_path: str) -> PdfContent:
        pages = self._extract_text_pages(file_path)

        content = PdfContent(file_path=file_path, pages=pages)
        if content.has_text_layer:
            return content

        rasterized_pages = self._rasterize_pages(file_path)
        return PdfContent(file_path=file_path, pages=rasterized_pages)

    def _extract_text_pages(self, file_path: str) -> list[PageContent]:
        pages = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                narrative_text = page.extract_text()
                tables_text = self._extract_tables_as_text(page)

                combined_parts = []
                if narrative_text and narrative_text.strip():
                    combined_parts.append(narrative_text.strip())
                if tables_text:
                    combined_parts.append(tables_text)

                combined = "\n\n".join(combined_parts) if combined_parts else None
                pages.append(PageContent(page_number=i, text=combined, image_base64=None))
        return pages

    def _extract_tables_as_text(self, page) -> Optional[str]:
        """
        Serializa cada tabla detectada como filas delimitadas por '|',
        preservando la posición exacta de cada celda (incluyendo
        celdas vacías), para que el LLM pueda razonar correctamente
        sobre encabezados de varias filas (ej. mes -> día -> día de
        la semana) sin perder la alineación de columnas.
        """
        tables = page.extract_tables()
        if not tables:
            return None

        blocks = []
        for table_index, table in enumerate(tables, start=1):
            rows_text = []
            for row in table:
                cells = [str(cell).strip() if cell is not None else "" for cell in row]
                rows_text.append(" | ".join(cells))
            blocks.append(
                f"--- Tabla {table_index} (estructura exacta fila/columna) ---\n"
                + "\n".join(rows_text)
            )

        return "\n\n".join(blocks)

    def _rasterize_pages(self, file_path: str) -> list[PageContent]:
        pages = []
        doc = fitz.open(file_path)
        try:
            for i, page in enumerate(doc, start=1):
                pixmap = page.get_pixmap(dpi=self.RASTER_DPI)
                image_bytes = pixmap.tobytes("png")
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                pages.append(
                    PageContent(page_number=i, text=None, image_base64=image_b64)
                )
        finally:
            doc.close()
        return pages