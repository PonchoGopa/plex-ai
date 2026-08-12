"""
api/router.py — Rutas FastAPI.

GET  /health  → estado del servicio
POST /process → recibe PDF, devuelve ZIP con los XMLs generados
"""
import io
import logging
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from api.schemas import HealthResponse, ProcessSummary
from api.pipeline import run_pipeline, PipelineError

logger = logging.getLogger(__name__)

router = APIRouter()

_VERSION = "0.9.0"

_OUTPUT_BASE = Path("output")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Estado del servicio",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=_VERSION)


@router.post(
    "/process",
    summary="Procesa un PDF y devuelve los archivos XML en un ZIP",
    responses={
        200: {"content": {"application/zip": {}}, "description": "ZIP con los XMLs generados"},
        422: {"description": "PDF inválido o error de validación"},
        500: {"description": "Error interno del pipeline"},
    },
)
async def process_pdf(
    file: UploadFile = File(..., description="Archivo PDF a procesar"),
) -> StreamingResponse:

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="El archivo debe ser un PDF (.pdf).")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=422, detail="El archivo recibido está vacío.")

    logger.info("POST /process — archivo: %s  tamaño: %d bytes", file.filename, len(pdf_bytes))

    try:
        # Primera pasada para resolver el po_number y definir carpeta definitiva
        result = run_pipeline(pdf_bytes, output_dir=_OUTPUT_BASE / "tmp_process")

        po_number = result["po_number"] or "unknown"
        final_dir = _OUTPUT_BASE / po_number
        final_dir.mkdir(parents=True, exist_ok=True)

        # Segunda pasada en carpeta definitiva (idempotente)
        result = run_pipeline(pdf_bytes, output_dir=final_dir)

    except PipelineError as exc:
        logger.warning("Pipeline bloqueado: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Error inesperado en el pipeline")
        raise HTTPException(status_code=500, detail=f"Error interno: {exc}")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in result["files_generated"]:
            fp = Path(file_path)
            if fp.exists():
                zf.write(fp, arcname=fp.name)

    zip_buffer.seek(0)

    zip_filename = f"{result['po_number']}_plex_import.zip"

    logger.info(
        "Respuesta OK — customer=%s  po=%s  records=%d  files=%d",
        result["customer"],
        result["po_number"],
        result["records_total"],
        len(result["files_generated"]),
    )

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "X-Customer": result["customer"],
            "X-PO-Number": result["po_number"],
            "X-Records": str(result["records_total"]),
            "X-Warnings": str(result["warnings"]),
        },
    )