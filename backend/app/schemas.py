"""Esquemas Pydantic de la API (contrato REST del reporte de análisis).

Se serializan directamente desde las filas ORM (`from_attributes=True`).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SyscallEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    seq: int
    ts: str | None
    name: str
    args: str | None
    result: str | None


class NetworkFlowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    proto: str
    src: str | None
    dst: str | None
    dport: int | None
    packets: int | None
    bytes: int | None
    info: str | None


class FsEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ts: str | None
    op: str
    path: str


class IocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    type: str
    value: str
    source: str | None


class SampleSummary(BaseModel):
    """Fila del listado `GET /samples` (sin el detalle de eventos)."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    sha256: str
    size_bytes: int | None
    arch: str
    status: str
    created_at: datetime
    finished_at: datetime | None


class SampleReport(SampleSummary):
    """Reporte completo `GET /samples/{id}`."""

    error: str | None
    counts: dict[str, int]
    syscalls: list[SyscallEventOut]
    network_flows: list[NetworkFlowOut]
    fs_events: list[FsEventOut]
    iocs: list[IocOut]


class UploadAccepted(BaseModel):
    """Respuesta de `POST /samples`."""

    sample_id: int
    status: str
    sha256: str
    deduplicated: bool = False
