"""Punto de entrada de la API FastAPI.

Endpoints (CP-3):
  - GET  /health          : liveness -> {"status": "ok"}.
  - POST /samples         : sube un binario (multipart), lo guarda, crea el registro
                            `sample(status=queued)` y encola la tarea Celery `analyze`.
  - GET  /samples         : listado de muestras (resumen) — para el frontend (CP-4).
  - GET  /samples/{id}    : reporte completo (estado + syscalls + red + fs + IoCs).

El binario subido es NO confiable: solo se almacena en disco (nunca se ejecuta en la
API); su detonación ocurre dentro de QEMU en el worker (CP-2).
"""
import hashlib
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.archdetect import detect_arch_from_bytes, is_elf, is_known_unsupported
from app.celery_client import celery_client
from app.config import settings
from app.db import get_session
from app.models import FsEvent, Ioc, NetworkFlow, Sample, SyscallEvent
from app.schemas import SampleReport, SampleSummary, UploadAccepted

app = FastAPI(
    title="IoT Malware Dynamic Analysis Sandbox API",
    version="0.3.0",
    description="API de análisis dinámico de malware IoT (TFM). CP-3: pipeline end-to-end.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: la API está en pie."""
    return {"status": "ok"}


@app.post("/samples", response_model=UploadAccepted, status_code=202)
async def upload_sample(
    file: UploadFile = File(...),
    arch: str = Form("auto"),
    session: AsyncSession = Depends(get_session),
) -> UploadAccepted:
    """Recibe un binario, lo persiste y encola su análisis dinámico.

    Selección de arquitectura (CP-6, ADR-021): si `arch` viene explícito (arm|mips|
    mipsel|x86_64) se respeta; si es `auto`/vacío se AUTODETECTA leyendo la cabecera ELF
    (e_machine + endianness). Se rechaza (400) toda ISA sin perfil disponible.

    Idempotente por contenido: si ya existe una muestra con el mismo sha256 se devuelve
    la existente (no se vuelve a encolar).
    """
    arch = arch.lower().strip()
    explicit = arch not in ("", "auto")
    if explicit and arch not in settings.supported_arches:
        raise HTTPException(
            status_code=400,
            detail=f"arquitectura '{arch}' no soportada (soportadas: "
            f"{', '.join(settings.supported_arches)})",
        )

    # Lectura en streaming + sha256 + límite de tamaño (sin cargar todo en memoria a ciegas).
    # Se conserva la cabecera (primeros bytes) para autodetectar la ISA por el ELF.
    sha = hashlib.sha256()
    size = 0
    head = b""
    storage_dir = Path(settings.sample_storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = storage_dir / f".upload-{os.getpid()}-{id(file)}.part"
    try:
        with tmp_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                if not head:
                    head = chunk[:64]
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="fichero demasiado grande")
                sha.update(chunk)
                out.write(chunk)
    except HTTPException:
        tmp_path.unlink(missing_ok=True)
        raise

    if size == 0:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="fichero vacío")

    # --- Resolución de arquitectura (autodetección ELF si no vino explícita) ----
    if not explicit:
        detected = detect_arch_from_bytes(head)
        if detected is None:
            tmp_path.unlink(missing_ok=True)
            motivo = (
                "es un ELF pero su arquitectura (e_machine) no se reconoce"
                if is_elf(head) else "no parece un ELF"
            )
            raise HTTPException(
                status_code=400,
                detail=f"no se pudo detectar la arquitectura: {motivo}; "
                "especifica 'arch' explícitamente "
                f"(soportadas: {', '.join(settings.supported_arches)})",
            )
        if detected not in settings.supported_arches:
            tmp_path.unlink(missing_ok=True)
            hint = " (reconocida pero sin perfil en la sandbox)" if is_known_unsupported(detected) else ""
            raise HTTPException(
                status_code=400,
                detail=f"arquitectura detectada '{detected}' no soportada{hint} "
                f"(soportadas: {', '.join(settings.supported_arches)})",
            )
        arch = detected

    sha256 = sha.hexdigest()

    # Deduplicación por hash: una muestra por binario.
    existing = (
        await session.execute(select(Sample).where(Sample.sha256 == sha256))
    ).scalar_one_or_none()
    if existing is not None:
        tmp_path.unlink(missing_ok=True)
        return UploadAccepted(
            sample_id=existing.id,
            status=existing.status,
            sha256=sha256,
            deduplicated=True,
        )

    # Almacenamiento canónico por contenido: <storage>/<sha256>.
    final_path = storage_dir / sha256
    os.replace(tmp_path, final_path)

    sample = Sample(
        filename=file.filename or "sample.bin",
        sha256=sha256,
        size_bytes=size,
        arch=arch,
        status="queued",
    )
    session.add(sample)
    await session.commit()
    await session.refresh(sample)

    # Encola por NOMBRE (API y worker desacoplados, comparten solo broker+db) — ADR-015.
    celery_client.send_task("analyze", args=[sample.id])

    return UploadAccepted(sample_id=sample.id, status="queued", sha256=sha256)


@app.get("/samples", response_model=list[SampleSummary])
async def list_samples(
    session: AsyncSession = Depends(get_session),
) -> list[Sample]:
    """Listado de muestras (más recientes primero)."""
    rows = (
        await session.execute(select(Sample).order_by(Sample.id.desc()))
    ).scalars().all()
    return list(rows)


@app.get("/samples/{sample_id}", response_model=SampleReport)
async def get_sample(
    sample_id: int,
    session: AsyncSession = Depends(get_session),
) -> SampleReport:
    """Reporte completo de una muestra: estado + telemetría parseada + IoCs."""
    sample = await session.get(Sample, sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="muestra no encontrada")

    syscalls = (
        await session.execute(
            select(SyscallEvent)
            .where(SyscallEvent.sample_id == sample_id)
            .order_by(SyscallEvent.seq)
        )
    ).scalars().all()
    flows = (
        await session.execute(
            select(NetworkFlow).where(NetworkFlow.sample_id == sample_id).order_by(NetworkFlow.id)
        )
    ).scalars().all()
    fs_events = (
        await session.execute(
            select(FsEvent).where(FsEvent.sample_id == sample_id).order_by(FsEvent.id)
        )
    ).scalars().all()
    iocs = (
        await session.execute(
            select(Ioc).where(Ioc.sample_id == sample_id).order_by(Ioc.type, Ioc.value)
        )
    ).scalars().all()

    return SampleReport(
        id=sample.id,
        filename=sample.filename,
        sha256=sample.sha256,
        size_bytes=sample.size_bytes,
        arch=sample.arch,
        status=sample.status,
        error=sample.error,
        created_at=sample.created_at,
        finished_at=sample.finished_at,
        counts={
            "syscalls": len(syscalls),
            "network_flows": len(flows),
            "fs_events": len(fs_events),
            "iocs": len(iocs),
        },
        syscalls=syscalls,
        network_flows=flows,
        fs_events=fs_events,
        iocs=iocs,
    )
