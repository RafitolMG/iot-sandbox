#!/bin/sh
# backend/entrypoint.sh — arranque de la API (CP-1)
# 1) aplica las migraciones de Alembic (idempotente: `upgrade head`)
# 2) lanza uvicorn
set -eu

echo "[api] Aplicando migraciones de base de datos (alembic upgrade head)..."
alembic upgrade head

echo "[api] Arrancando uvicorn en 0.0.0.0:8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
