# docker/api.Dockerfile — API FastAPI (CP-1)
# Imagen base: ADR-007 (python:3.12-slim-bookworm).
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias primero (cache de capas): solo se reinstala si cambia requirements.txt.
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Código de la app (incluye alembic + entrypoint).
COPY backend/ ./
RUN chmod +x entrypoint.sh

EXPOSE 8000

# entrypoint: aplica migraciones (alembic upgrade head) y arranca uvicorn.
CMD ["./entrypoint.sh"]
