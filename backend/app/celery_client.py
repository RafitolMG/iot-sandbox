"""Cliente Celery de la API (productor de tareas).

La API NO importa el código de las tareas del worker: las encola *por nombre* con
`send_task(...)`, manteniendo API y worker desacoplados (comparten solo broker+backend).
El worker registra la tarea como `name="ping"` (ver worker/celery_app.py).
"""
from celery import Celery

from app.config import settings

celery_client = Celery(
    "iot_sandbox_api",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_client.conf.broker_connection_retry_on_startup = True
