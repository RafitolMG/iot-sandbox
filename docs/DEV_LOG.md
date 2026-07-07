# DEV_LOG — Bitácora de desarrollo

> Una entrada por cada checkpoint cerrado.
> Sirve de material directo para narrar el Capítulo 4 del TFM.

<!-- Plantilla de entrada:

## CP-X · <título> — <fecha>
**Hecho:** ...
**Cómo verificar:** <comandos>
**Funciona / No funciona:** ...
**Decisiones abiertas (→ DECISIONS.md):** ...
**Siguiente:** ...
-->

## CP-0 · Kickoff y andamiaje — 2026-07-07

**Hecho:**
- Estructura del monorepo: `backend/`, `worker/`, `frontend/`, `emulation/arm/`, `docker/`
  (+ `docs/` preexistente). Cada carpeta de servicio lleva un `README.md` con su rol y el
  checkpoint en que se implementa.
- `README.md` raíz: qué es, aviso de seguridad, arquitectura resumida, cómo se levantará
  (`docker compose up`, a partir de CP-1), tabla de servicios/puertos y estructura de carpetas.
- `.gitignore`: Python (`__pycache__`, venvs, caches), Node (`node_modules`, `dist`), secretos
  (`.env` con excepción `!.env.example`), **artefactos de análisis y muestras**
  (`samples/`, `artifacts/`, `*.pcap`, `strace.log`, `fs_events.log`) e imágenes de emulación
  (`*.img`, `*.qcow2`, kernels, rootfs, `emulation/**/output/`).
- `.env.example`: plantilla de variables (Postgres, `DATABASE_URL`, `REDIS_URL`) **sin secretos**.
- `docker-compose.yml` **esqueleto** (Compose Spec, sin `version:`): servicios `api`, `worker`,
  `db` (postgres:16), `redis` (redis:7.2), `frontend`, con puertos, healthchecks de db/redis,
  volúmenes (`pgdata`, `sample_storage`, `artifacts`) y red `sandbox_net`. **Sin lógica de negocio.**
- Dockerfiles **placeholder** en `docker/` (`api`, `worker`, `frontend`): solo imagen base + un
  `CMD` que imprime un aviso; no instalan deps ni copian código.
- `docs/DECISIONS.md`: ADR-007 a ADR-014 en estado **PROPUESTA** con versiones exactas
  (Python, Node, PostgreSQL, Redis/Valkey, QEMU, rootfs ARM, convenciones de build).

**Cómo verificar:**
```bash
cd ~/Proyectos/iot-sandbox
git log --oneline -1                       # commit de CP-0
find . -path ./.git -prune -o -type f -print | sort   # árbol de ficheros
python3 -c 'import yaml,sys; yaml.safe_load(open("docker-compose.yml")); print("compose YAML OK")'
docker compose config >/dev/null && echo "compose config OK"   # opcional (no arranca nada)
git check-ignore -v .env samples/x.bin capture.pcap    # confirma que se ignoran
```
> `docker compose up` **NO** debe ejecutarse en CP-0: los servicios de aplicación son placeholder.

**Funciona / No funciona:**
- Funciona: estructura, documentación y `docker-compose.yml` sintácticamente válido (YAML validado).
- No aplica todavía: cualquier lógica ejecutable (API, worker/QEMU, frontend). Es solo andamiaje.

**Decisiones abiertas (→ DECISIONS.md, estado PROPUESTA):**
- ADR-008 ⚠ — verificar que exista el tag `python:3.12-slim-trixie` (para QEMU 9.2 vía apt).
- ADR-011 ⚠ — broker/licencia: Redis 7.2 (BSD) vs Redis 8 (AGPL) vs Valkey (BSD). Decisión de Rafael.
- ADR-013 ⚠ — tooling del rootfs ARM (Buildroot recomendado) y armel/armhf + máquina/kernel (se cierra en CP-2).
- Confirmar versiones de PostgreSQL (16 vs 17) y Node (22 vs 24).

**Siguiente:** CP-1 — infraestructura levanta (`docker compose up` con API `/health`, Postgres,
Redis, worker Celery con tarea `ping` y migraciones iniciales). **Requiere** aceptar primero
las versiones propuestas (ADR-007..014).
