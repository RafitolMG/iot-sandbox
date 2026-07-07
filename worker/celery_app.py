"""App Celery del worker (CP-1).

CP-1 solo registra una tarea de prueba `ping` -> "pong" para validar el circuito
Celery <-> Valkey. La orquestación real de QEMU (analyze) llega en CP-2/CP-3.

El broker es Valkey 8 (ADR-011), accedido con protocolo redis:// (redis://valkey:6379/0).
"""
import os

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
