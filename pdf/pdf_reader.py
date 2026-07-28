import base64
from dataclasses import dataclass
from typing import Optional

import fitz  # PyMuPDF
import pdfplumber


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
        return any(p.text for p in self.pages)


class PdfReader:
    """
    Lee un PDF y decide automáticamente la estrategia de extracción:

    - Si al menos una página tiene texto real (capa de texto), se
      extrae texto de todas las páginas con pdfplumber.
    - Si NINGUNA página tiene texto (documento escaneado / impreso
      como imagen, como PO_Topre.pdf), se rasteriza cada página con
      PyMuPDF y se guarda como imagen base64, para que el LLM la
      lea directamente por visión.
    """

    RASTER_DPI = 150

    def read(self, file_path: str) -> PdfContent:
        pages = self._extract_text_pages(file_path)

        if any(p.text for p in pages):
            return PdfContent(file_path=file_path, pages=pages)

        rasterized_pages = self._rasterize_pages(file_path)
        return PdfContent(file_path=file_path, pages=rasterized_pages)

    def _extract_text_pages(self, file_path: str) -> list[PageContent]:
        pages = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                pages.append(PageContent(page_number=i, text=text, image_base64=None))
        return pages

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