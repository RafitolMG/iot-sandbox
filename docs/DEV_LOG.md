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

---

## CP-1 · Infraestructura levanta — 2026-07-07

**Hecho:**
- **Broker migrado a Valkey 8** (ADR-011 resuelta): `docker-compose.yml` usa
  `valkey/valkey:8-alpine` (servicio `valkey`, healthcheck `valkey-cli ping`). Protocolo sigue
  siendo `redis://valkey:6379/N`.
- **API FastAPI** (`backend/app/`): `GET /health` → `{"status":"ok"}`. App como paquete:
  `config.py` (pydantic-settings), `db.py` (SQLAlchemy async: `create_async_engine` +
  `async_sessionmaker` sobre asyncpg), `models.py` (tabla `sample`), `celery_client.py`
  (productor Celery), `main.py`. Dockerfile real `docker/api.Dockerfile` (instala
  `backend/requirements.txt` con pins).
- **Worker Celery** (`worker/celery_app.py`): tarea de prueba `ping` → `"pong"`. Dockerfile real
  `docker/worker.Dockerfile` sobre `python:3.12-slim-trixie` (base lista para QEMU 9.2 en CP-2;
  **sin instalar QEMU aún** → arranque rápido).
- **Migraciones Alembic en modo async** (una sola `DATABASE_URL` asyncpg para app y migraciones).
  Revisión inicial `0001_initial` crea la tabla `sample` (id, filename, sha256[unique], arch,
  status, created_at). Se aplican en el **entrypoint de la API** (`alembic upgrade head`) antes
  de uvicorn.
- **Compose:** 5 servicios (api, worker, db, valkey, frontend[placeholder]) con `depends_on` +
  healthchecks (db, valkey, api, worker), red `sandbox_net`, env `DATABASE_URL` /
  `REDIS_URL=redis://valkey:6379/0` / `CELERY_BROKER_URL` (DB 0) / `CELERY_RESULT_BACKEND` (DB 1).
- `.env.example` ampliado (Celery), `.dockerignore` nuevo, ADR-015 registrada (ACEPTADA).
- Frontend intacto (placeholder de CP-0).

**Cómo verificar:**
```bash
cd ~/Proyectos/iot-sandbox
docker compose build api worker
docker compose up -d db valkey            # esperar healthy
docker compose up -d api worker
curl -s localhost:8000/health             # {"status":"ok"}
curl -s localhost:8000/ping-task          # {"task_id":"...","result":"pong"}
docker compose exec -T db psql -U sandbox -d sandbox -c '\d sample'
docker compose down
```

**Funciona / No funciona:**
- Funciona (verificado): build de api+worker OK; db+valkey healthy; API healthy; migración
  `0001_initial` aplicada (tabla `sample` creada, `alembic_version=0001_initial`);
  `GET /health` → `{"status":"ok"}`; `GET /ping-task` →
  `{"task_id":"41c962d8-…","result":"pong"}` (worker log: `Task ping[…] succeeded … 'pong'`);
  worker healthy. `docker compose down` ejecutado (sin contenedores ni volúmenes residuales).
- Pendiente por diseño: QEMU/emulación (CP-2), `POST/GET /samples` + persistencia (CP-3),
  frontend real (CP-4). El endpoint `/ping-task` es temporal y se retira en CP-3.

**Decisiones abiertas (→ DECISIONS.md):** ninguna nueva. ADR-015 (estructura app + migraciones)
registrada como **ACEPTADA** (micro-decisión de implementación, no requiere revisión humana).

**Siguiente:** CP-2 — núcleo de emulación ARM (QEMU full-system + rootfs + binario benigno →
strace/tcpdump/inotify). Hito técnico más arriesgado.
