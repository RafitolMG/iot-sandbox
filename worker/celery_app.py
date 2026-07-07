"""App Celery del worker (CP-1 + hook de CP-2).

CP-1 registró la tarea de prueba `ping` -> "pong" (circuito Celery <-> Valkey).
CP-2 añade un HOOK ligero `emulate_arm` que invoca el script autónomo de emulación
(`emulation/arm/run_emulation.sh`) y devuelve los artefactos generados. El grueso de
CP-2 es ese script (ejecutable a mano); esta tarea solo lo deja "invocable" desde Celery.
El parseo de IoCs y la persistencia en BD son CP-3.

El broker es Valkey 8 (ADR-011), accedido con protocolo redis:// (redis://valkey:6379/0).
"""
import os
import subprocess

from celery import Celery

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://valkey:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://valkey:6379/1")

app = Celery("iot_sandbox_worker", broker=BROKER_URL, backend=RESULT_BACKEND)

# Configuración conservadora para el MVP.
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=3600,
    # Mantiene el comportamiento de reintento de conexión al broker en arranque
    # (evita el CPendingDeprecationWarning de Celery 6).
    broker_connection_retry_on_startup=True,
)


@app.task(name="ping")
def ping() -> str:
    """Tarea de prueba de conectividad: devuelve 'pong'."""
    return "pong"


# Ruta al script de emulación autónomo de CP-2. En el MVP se resuelve por env; la
# integración plena (montaje del repo / acceso a Docker desde el worker) es CP-3.
EMULATION_RUNNER = os.environ.get(
    "EMULATION_RUNNER", "/project/emulation/arm/run_emulation.sh"
)


@app.task(name="emulate_arm")
def emulate_arm(out_dir: str = "/project/emulation/arm/_build/artifacts",
                timeout_s: int = 240) -> dict:
    """Hook CP-2: detona el binario benigno en la sandbox ARM y devuelve los artefactos.

    Ejecuta el script autónomo `run_emulation.sh` (QEMU full-system ARM -> strace/
    tcpdump/inotify) y comprueba que se generaron los 3 artefactos. NO parsea IoCs ni
    persiste nada (eso es CP-3). Si el runner no está disponible en el entorno del
    worker (requiere acceso a Docker/host, que se cablea en CP-3), devuelve un estado
    claro en lugar de fallar.
    """
    if not os.path.exists(EMULATION_RUNNER):
        return {
            "status": "runner_unavailable",
            "detail": f"no existe {EMULATION_RUNNER}; el cableado worker->emulación es CP-3",
            "runner": EMULATION_RUNNER,
        }

    proc = subprocess.run(
        ["bash", EMULATION_RUNNER, out_dir, str(timeout_s)],
        capture_output=True, text=True, timeout=timeout_s + 120,
    )
    artifacts = {
        name: os.path.join(out_dir, name)
        for name in ("strace.log", "capture.pcap", "fs_events.log")
        if os.path.exists(os.path.join(out_dir, name))
    }
    return {
        "status": "ok" if len(artifacts) == 3 else "incomplete",
        "returncode": proc.returncode,
        "artifacts": artifacts,
        "out_dir": out_dir,
    }
