"""App Celery del worker — tarea `analyze` (pipeline completo, CP-3).

Flujo de `analyze(sample_id)`:
  1. Carga la muestra (sha256, arch) y la marca `running`.
  2. Detona el binario en la sandbox de su ISA (QEMU full-system, CP-2/CP-6) vía
     Docker-out-of-Docker (ADR-017): el worker selecciona el perfil por `arch` (ADR-020);
     la muestra NO confiable se ejecuta dentro del invitado, nunca aquí.
  3. Parsea los 3 artefactos (strace.log, capture.pcap, fs_events.log) y extrae IoCs.
  4. Persiste syscalls / flujos de red / fs_events / IoCs en PostgreSQL.
  5. Marca `done` (o `failed` con el error) y anota `finished_at`.

El broker es Valkey 8 (ADR-011); la BD PostgreSQL se accede en modo SÍNCRONO (worker/db.py).
El circuito de prueba `ping`/`emulate_arm` de CP-1/CP-2 se retira: `analyze` lo reemplaza.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import select

from db import engine, fs_event, ioc, network_flow, sample, syscall_event
from emulation import run_emulation
from parsers import parse_artifacts

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://valkey:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://valkey:6379/1")
EMULATION_TIMEOUT = int(os.environ.get("EMULATION_TIMEOUT", "180"))
SANDBOX_NET_RESTRICT = os.environ.get("SANDBOX_NET_RESTRICT", "0") == "1"

app = Celery("iot_sandbox_worker", broker=BROKER_URL, backend=RESULT_BACKEND)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    # La emulación es larga y no reentrante: 1 tarea por worker a la vez basta para el MVP.
    worker_prefetch_multiplier=1,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_status(sample_id: int, status: str, **extra) -> None:
    with engine.begin() as conn:
        conn.execute(
            sample.update().where(sample.c.id == sample_id).values(status=status, **extra)
        )


def _persist(sample_id: int, parsed) -> dict[str, int]:
    """Inserta eventos + IoCs (idempotente: borra los previos de la muestra)."""
    with engine.begin() as conn:
        for tbl in (syscall_event, network_flow, fs_event, ioc):
            conn.execute(tbl.delete().where(tbl.c.sample_id == sample_id))

        if parsed.syscalls:
            conn.execute(
                syscall_event.insert(),
                [{**s, "sample_id": sample_id} for s in parsed.syscalls],
            )
        if parsed.network_flows:
            conn.execute(
                network_flow.insert(),
                [{**f, "sample_id": sample_id} for f in parsed.network_flows],
            )
        if parsed.fs_events:
            conn.execute(
                fs_event.insert(),
                [{**e, "sample_id": sample_id} for e in parsed.fs_events],
            )
        if parsed.iocs:
            conn.execute(
                ioc.insert(),
                [
                    {
                        "sample_id": sample_id, "type": t, "value": v,
                        "source": ",".join(sorted(sources)),
                    }
                    for (t, v), sources in sorted(parsed.iocs.items())
                ],
            )
    return {
        "syscalls": len(parsed.syscalls),
        "network_flows": len(parsed.network_flows),
        "fs_events": len(parsed.fs_events),
        "iocs": len(parsed.iocs),
    }


@app.task(name="analyze", bind=True)
def analyze(self, sample_id: int) -> dict:
    """Pipeline de análisis dinámico de una muestra."""
    with engine.begin() as conn:
        row = conn.execute(
            select(sample.c.sha256, sample.c.arch).where(sample.c.id == sample_id)
        ).first()
    if row is None:
        return {"sample_id": sample_id, "status": "not_found"}
    sha256, arch = row

    _set_status(sample_id, "running")

    try:
        emu = run_emulation(
            sample_id, sha256, arch=arch or "arm",
            timeout_s=EMULATION_TIMEOUT,
            net_restrict=SANDBOX_NET_RESTRICT,
        )
        out = emu["out_dir"]
        strace_p = os.path.join(out, "strace.log")
        pcap_p = os.path.join(out, "capture.pcap")
        fs_p = os.path.join(out, "fs_events.log")

        if not os.path.exists(strace_p):
            tail = "\n".join(emu.get("logs", "").splitlines()[-25:])
            raise RuntimeError(
                f"la emulación no produjo strace.log (rc={emu.get('exit_code')}).\n{tail}"
            )

        parsed = parse_artifacts(strace_p, pcap_p, fs_p, sha256=sha256)
        counts = _persist(sample_id, parsed)
        _set_status(sample_id, "done", finished_at=_now(), error=None)
        return {"sample_id": sample_id, "status": "done", "counts": counts,
                "emulation_rc": emu.get("exit_code")}

    except Exception as exc:  # noqa: BLE001 — se registra el error en la muestra
        _set_status(sample_id, "failed", finished_at=_now(), error=str(exc)[:2000])
        raise
