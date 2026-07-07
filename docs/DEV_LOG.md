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

---

## CP-2 · Núcleo de emulación ARM — 2026-07-07

**Enfoque de rootfs:** **Buildroot (PRIMARIO), sin necesidad de fallback.** Buildroot
2024.02.11 LTS + `qemu_arm_vexpress_defconfig` + fragmento con `strace`/`tcpdump`/
`inotify-tools` + rootfs-overlay. Build ~20 min (`make -j16`), reproducible (Buildroot
compila sus propios host-tools pinneados). Detalles y cierre de ADR-013/012 → **ADR-016**.

**Par máquina / kernel / ISA (fijado):** `-M vexpress-a9` (Cortex-A9 / **ARMv7-A**),
**armhf** (EABIhf hard-float, VFPv3-D16, glibc), kernel **zImage Linux 6.1.44** + DTB
`vexpress-v2p-ca9.dtb`, rootfs `rootfs.ext2` (SD → `/dev/mmcblk0`, ajustada a 256 MiB en
arranque). QEMU **`qemu-system-arm` 10.0.8** (Debian 13, corrige el 9.2 de ADR-012).

**Hecho:**
- **Imagen de build+run** `docker/emulation.Dockerfile` (Debian 13 + QEMU 10 + cross-toolchain
  `arm-linux-gnueabihf` + deps de Buildroot + `e2fsprogs` + `tshark`). Todo en contenedor,
  sin mutar el host, sin `sudo`; QEMU cross-ISA por TCG (sin KVM, sin privilegios).
- **Binario ARM benigno de prueba** `emulation/arm/testbin/test_sample.c` (ADR-005): hace
  (a) syscalls varias, (b) escribe `/tmp/iot_sandbox_marker.txt`, (c) intento de red
  (getaddrinfo + consulta DNS UDP manual + `connect()` TCP a `198.51.100.23:4444`). Estático
  ARMv7 hard-float. Se ejecuta SIEMPRE dentro del invitado, nunca en el host.
- **PID 1 del invitado** `emulation/arm/overlay/sbin/telemetry_init`: monta pseudo-FS + tmpfs,
  levanta la red SLIRP, arranca las 3 sondas, ejecuta la muestra bajo `strace`, cierra sondas,
  sincroniza y apaga (`reboot -f` con `-no-reboot`).
- **Scripts autónomos** `emulation/arm/build_rootfs.sh` (construye imagen + kernel/rootfs +
  binario) y `emulation/arm/run_emulation.sh` (arranca QEMU, extrae con `debugfs` sin montar,
  verifica). Se auto-reejecutan dentro del contenedor.
- **Hook de worker (ligero)** `worker/celery_app.py` → tarea Celery `emulate_arm` que invoca
  `run_emulation.sh` y comprueba los 3 artefactos. Sin parseo de IoCs ni BD (eso es CP-3).

**Cómo verificar:**
```bash
cd ~/Proyectos/iot-sandbox
emulation/arm/build_rootfs.sh          # 1ª vez: ~20 min (Buildroot). Genera _build/images/
emulation/arm/run_emulation.sh         # arranca QEMU, deja los 3 artefactos + los resume
ls -l emulation/arm/_build/artifacts/  # strace.log · capture.pcap · fs_events.log
tshark -r emulation/arm/_build/artifacts/capture.pcap
```

**Funciona / No funciona (verificado con detonación real):**
- QEMU arranca (kernel 6.1.44 armv7l), corre `test_sample` bajo telemetría (rc=0) y **apaga
  limpio** (`reboot: Restarting system`, QEMU rc=0). Sin procesos QEMU ni contenedores
  residuales.
- **`strace.log`** (8.4 KB) — p.ej.:
  `execve("/opt/sample/test_sample", …) = 0`;
  `openat(AT_FDCWD, "/tmp/iot_sandbox_marker.txt", O_WRONLY|O_CREAT|O_TRUNC…) = 3`;
  `chmod("/tmp/iot_sandbox_marker.txt", 0644) = 0`;
  `sendto(3, "\\0237\\1\\0…\\2c2\\fsandbox-test\\7exa"…, 41, …htons(53)…10.0.2.3…) = 41`;
  `connect(3, {…htons(4444), inet_addr("198.51.100.23")}, 16) = -1 EINPROGRESS`.
- **`capture.pcap`** (1.3 KB) — `tshark -z io,phs`: 11 frames (arp 4, dns 4, icmp 1, tcp 2).
  Query DNS A `c2.sandbox-test.example` → respuesta *No such name*; SYN + retransmisión TCP
  `10.0.2.15 → 198.51.100.23:4444`. Queda registrado el intento de C2.
- **`fs_events.log`** (4 eventos): `CREATE`, `MODIFY`, `CLOSE_WRITE,CLOSE`, `ATTRIB` sobre
  `/tmp/iot_sandbox_marker.txt`.

**Instalado en el entorno:** nada en el host (no había `sudo`). Todo vive en la imagen Docker
`iot-sandbox/emulation:dev`: `qemu-system-arm 10.0.8`, `gcc-arm-linux-gnueabihf 14`,
`e2fsprogs 1.47`, `tshark 4.4`, deps de Buildroot. Buildroot 2024.02.11 se descarga y compila
dentro del contenedor (cache en `_build/dl`).

**Decisiones abiertas (→ DECISIONS.md):** ADR-016 registrada como **ACEPTADA** (cierra
ADR-013, corrige la versión de QEMU de ADR-012). Sin decisiones humanas pendientes. Matiz de
red (SLIRP abierto en CP-2 vs aislamiento pleno en CP-5) documentado en ADR-016 y README.

**Siguiente:** CP-3 — `POST /samples` → Celery `analyze` → corre CP-2 → parsea artefactos →
extrae IoCs → persiste en PostgreSQL; `GET /samples/{id}` devuelve el reporte. También cablear
worker↔Docker/host (el hook `emulate_arm` requiere acceso a Docker desde el worker).
