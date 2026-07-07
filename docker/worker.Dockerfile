# docker/worker.Dockerfile — PLACEHOLDER (CP-0)
# El worker (Celery + QEMU full-system) se implementa en CP-1 (tarea ping) y CP-2 (ARM).
# Imagen base y QEMU propuestos en ADR-008 / ADR-012 (docs/DECISIONS.md).
FROM python:3.12-slim-trixie

WORKDIR /app

# CP-1: apt-get install qemu-system-arm (+ tcpdump, ...) + pip install celery, redis.
# CP-2: consumir los perfiles de emulation/arm/ para arrancar QEMU full-system.
CMD ["python", "-c", "print('iot-sandbox worker: placeholder CP-0, sin implementar (ver CP-1/CP-2)')"]
