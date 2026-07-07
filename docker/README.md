# docker/ — Dockerfiles de los servicios

Un Dockerfile por servicio construido a medida (`api`, `worker`, `frontend`). Los
servicios de infraestructura (`db`, `redis`) usan imágenes oficiales directamente desde
`docker-compose.yml`.

| Dockerfile             | Servicio  | Imagen base (propuesta)      | ADR      |
|------------------------|-----------|------------------------------|----------|
| `api.Dockerfile`       | api       | `python:3.12-slim-bookworm`  | ADR-007  |
| `worker.Dockerfile`    | worker    | `python:3.12-slim-trixie`    | ADR-008  |
| `frontend.Dockerfile`  | frontend  | `node:22-bookworm-slim`      | ADR-009  |

**Estado (CP-0):** los tres Dockerfiles son **PLACEHOLDER** — solo declaran la imagen
base y un `CMD` que imprime un aviso. No instalan dependencias ni copian código. Se
rellenan a partir de CP-1 (api/worker) y CP-4 (frontend).
