"""
api/schemas.py — Modelos Pydantic para request/response de la API.
"""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str


class ProcessError(BaseModel):
    detail: str


class ProcessSummary(BaseModel):
    customer: str
    po_number: str
    records_total: int
    errors: int
    warnings: int
    files_generated: list[str]