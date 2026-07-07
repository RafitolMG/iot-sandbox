# backend/ — API REST (FastAPI)

Servicio de API asíncrona (**Python 3.12 + FastAPI + Pydantic**). Recibe binarios de
muestra, los valida, encola tareas de análisis en Celery y expone los reportes
forenses (syscalls, red, ficheros, IoCs).

**Estado (CP-0):** andamiaje. La implementación empieza en:
- **CP-1** — endpoint `/health`, arranque con uvicorn.
- **CP-3** — `POST /samples` (subida) y `GET /samples/{id}` (reporte), modelo de datos.

Imagen base: `docker/api.Dockerfile` (ver ADR-007 en `docs/DECISIONS.md`).
