"""
ingestion/document_detector.py

Detecta automáticamente el cliente a partir del contenido del archivo
y devuelve (MosHeader, list[MosRecord]) usando el parser correcto.

Clientes soportados:
  - Topre       → PDF con "Material Order Sheet"
  - Y-tec       → PDF con "DELIVERY INSTRUCTION" / "Y-tec"
  - S-Riko      → Excel .xlsx con "S-Riko" en contenido

Detección por prioridad:
  1. Extensión del archivo (.xlsx → S-Riko)
  2. Palabras clave en el texto del PDF
"""
from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

import pdfplumber

from pdf.mos_table_parser import MosHeader, MosRecord

logger = logging.getLogger(__name__)

# Palabras clave para identificar cliente en PDF
_TOPRE_KEYWORDS = ["material order sheet", "topre"]
_YTEC_KEYWORDS  = ["delivery instruction", "y-tec", "ytec", "ypu"]


class DocumentDetector:
    """
    Punto de entrada único para ingesta de documentos.

    Uso:
        detector = DocumentDetector()
        header, records = detector.detect_and_parse(
            file_bytes=...,
            filename="PO_Topre.pdf",
        )
    """

    def detect_and_parse(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> tuple[MosHeader, list[MosRecord]]:
        """
        Detecta el tipo de documento y ejecuta el parser correspondiente.

        Returns
        -------
        (MosHeader, list[MosRecord])

        Raises
        ------
        ValueError
            Si el formato del documento no es reconocido.
        """
        ext = Path(filename).suffix.lower()

        # ── Excel → S-Riko ───────────────────────────────────────────────────
        if ext in (".xlsx", ".xls"):
            return self._parse_sriko(file_bytes)

        # ── PDF → detectar por contenido ─────────────────────────────────────
        if ext == ".pdf":
            raw_text, raw_tables = self._extract_pdf(file_bytes)
            client = self._identify_pdf_client(raw_text)

            if client == "topre":
                return self._parse_topre(raw_text, raw_tables)
            elif client == "ytec":
                return self._parse_ytec(raw_text, raw_tables)
            else:
                raise ValueError(
                    f"PDF no reconocido. Clientes soportados: Topre, Y-tec. "
                    f"Palabras clave encontradas: {raw_text[:200]!r}"
                )

        raise ValueError(
            f"Formato de archivo no soportado: '{ext}'. "
            f"Formatos aceptados: .pdf, .xlsx"
        )

    # ── Parsers por cliente ───────────────────────────────────────────────────

    def _parse_topre(
        self,
        raw_text: str,
        raw_tables: list,
    ) -> tuple[MosHeader, list[MosRecord]]:
        from pdf.mos_table_parser import MosTableParser
        from pdf.mos_header_parser import MosHeaderParser

        header  = MosHeaderParser().parse(raw_text)
        records = MosTableParser().parse(raw_tables)
        logger.info("DocumentDetector → cliente=Topre | %d registros", len(records))
        return header, records

    def _parse_ytec(
        self,
        raw_text: str,
        raw_tables: list,
    ) -> tuple[MosHeader, list[MosRecord]]:
        from pdf.ytec_parser import YtecParser

        header, records = YtecParser().parse(raw_text, raw_tables)
        logger.info("DocumentDetector → cliente=Y-tec | %d registros", len(records))
        return header, records

    def _parse_sriko(
        self,
        file_bytes: bytes,
    ) -> tuple[MosHeader, list[MosRecord]]:
        from excel.sriko_parser import SRikoParser

        # SRikoParser necesita ruta en disco (openpyxl no lee bytes directo)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            header, records = SRikoParser().parse(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        logger.info("DocumentDetector → cliente=S-Riko | %d registros", len(records))
        return header, records

    # ── Extracción PDF ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_pdf(pdf_bytes: bytes) -> tuple[str, list]:
        text_parts: list[str] = []
        raw_tables: list      = []

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text() or ""
                    if t:
                        text_parts.append(t)
                    for tbl in page.extract_tables() or []:
                        raw_tables.append(tbl)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return "\n\n".join(text_parts), raw_tables

    @staticmethod
    def _identify_pdf_client(text: str) -> str:
        """
        Devuelve 'topre', 'ytec' o 'unknown' según palabras clave.
        """
        lower = text.lower()
        topre_score = sum(1 for kw in _TOPRE_KEYWORDS if kw in lower)
        ytec_score  = sum(1 for kw in _YTEC_KEYWORDS  if kw in lower)

        if topre_score == 0 and ytec_score == 0:
            return "unknown"
        return "topre" if topre_score >= ytec_score else "ytec"