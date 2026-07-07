"""Punto de entrada de la API FastAPI (CP-1).

Endpoints:
  - GET /health     : liveness mínimo -> {"status": "ok"}.
  - GET /ping-task   : endpoint TEMPORAL de CP-1. Encola la tarea `ping` en el worker
                       Celery a través de Valkey y devuelve el resultado ("pong"),
                       demostrando el circuito API -> Valkey -> Worker. Se retirará en CP-3.
"""
from fastapi import FastAPI

from app.celery_client import celery_client

app = FastAPI(
    title="IoT Malware Dynamic Analysis Sandbox API",
    version="0.1.0",
    description="API de análisis dinámico de malware IoT (TFM). CP-1: infraestructura.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: la API está en pie."""
    return {"status": "ok"}


@app.get("/ping-task")
def ping_task() -> dict[str, str]:
    """CP-1 (temporal): demuestra que Celery <-> Valkey funciona.

    Endpoint síncrono a propósito: FastAPI lo ejecuta en un threadpool, así el
    `result.get()` bloqueante no congela el event loop async.
    """
    result = celery_client.send_task("ping")
    value = result.get(timeout=10)
    return {"task_id": result.id, "result": value}
