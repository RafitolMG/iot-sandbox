# docker/worker.Dockerfile — Worker Celery (CP-1)
# Imagen base: ADR-008 (python:3.12-slim-trixie). Trixie (Debian 13) se elige AHORA para
# que en CP-2 se pueda instalar QEMU 9.2 vía apt sin cambiar de base. En CP-1 NO se instala
# QEMU (arranque rápido); esa capa se añade en CP-2.
FROM python:3.12-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY worker/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY worker/ ./

# Worker Celery: descubre la app en celery_app.py (módulo `app`). Concurrencia baja para el MVP.
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=2"]
