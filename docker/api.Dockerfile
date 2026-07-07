# docker/api.Dockerfile — PLACEHOLDER (CP-0)
# La API real (FastAPI + endpoint /health) se implementa en CP-1.
# Imagen base propuesta en ADR-007 (docs/DECISIONS.md).
FROM python:3.12-slim-bookworm

WORKDIR /app

# CP-1: COPY backend/ + instalar dependencias (FastAPI, uvicorn, SQLAlchemy, ...).
# CP-1: CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["python", "-c", "print('iot-sandbox api: placeholder CP-0, sin implementar (ver CP-1)')"]
