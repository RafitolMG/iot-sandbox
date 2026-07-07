# docker/ — Dockerfiles de los servicios

Un Dockerfile por servicio construido a medida (`api`, `worker`, `frontend`). Los
servicios de infraestructura (`db`, `redis`) usan imágenes oficiales directamente desde
`docker-compose.yml`.

| Dockerfile             | Servicio  | Imagen base                              | ADR      |
|------------------------|-----------|------------------------------------------|----------|
| `api.Dockerfile`       | api       | `python:3.12-slim-bookworm`              | ADR-007  |
| `worker.Dockerfile`    | worker    | `python:3.12-slim-trixie`                | ADR-008  |
| `emulation.Dockerfile` | (build/run QEMU) | `debian:trixie-slim` (QEMU 10)    | ADR-016  |
| `frontend.Dockerfile`  | frontend  | `node:22-bookworm-slim` → `nginx:1.29-alpine` | ADR-009/019 |

**Estado (CP-4 · MVP completo):** los cuatro Dockerfiles están implementados. `frontend` es
**multi-stage**: construye el bundle Vite con Node y lo sirve con nginx (que además
reverse-proxya `/api` → `api:8000`). Los servicios de infraestructura (`db`, `valkey`) usan
imágenes oficiales directamente desde `docker-compose.yml`.
