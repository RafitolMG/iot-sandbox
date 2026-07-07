# DECISIONS — Registro de decisiones del proyecto (ADR)

> **Registro de decisiones del proyecto**, en formato ligero tipo ADR (Architecture Decision
> Record). Se consulta antes de cada tramo de trabajo. Una decisión que surge durante la
> construcción se añade en estado `PROPUESTA` y detiene el desarrollo; resuelta en la revisión,
> pasa a `ACEPTADA`.
>
> Estados: `ACEPTADA` · `PROPUESTA` (pendiente de resolver) · `RECHAZADA` · `SUPERSEDED`

---

## Decisiones ya tomadas (seed inicial)

### ADR-001 — Ubicación del proyecto · ACEPTADA
`~/Proyectos/iot-sandbox`, repositorio git local.

### ADR-002 — Enfoque de hito 1: MVP una arquitectura · ACEPTADA
Se construye el flujo completo end-to-end con **ARM** primero. MIPS/MIPSEL/x86_64 después.
**Motivo:** reduce riesgo, da resultados demostrables antes, y la generalización a otras ISAs
es casi mecánica (kernel + rootfs + binario QEMU distintos).

### ADR-003 — Stack tecnológico · ACEPTADA
Python 3.12 + FastAPI · Celery + Redis · PostgreSQL · QEMU full-system · Vue 3 + Vite ·
Docker Compose · strace/tcpdump/inotify. Justificado en el Cap. 3 del TFM.

### ADR-004 — Emulación en modo full-system (no user-mode) · ACEPTADA
QEMU full-system para poder capturar comportamiento a nivel de kernel y ofrecer un rootfs
realista. **Motivo:** user-mode no intercepta interacciones de kernel (justificado en §2.1.4 del TFM).

### ADR-005 — Sin malware real durante el MVP · ACEPTADA
El MVP se valida con un binario ARM benigno de prueba. El malware real solo en la fase de
evaluación, siempre dentro de QEMU. **Motivo:** seguridad + validar la tubería sin riesgo.

### ADR-006 — Metodología: iteraciones con checkpoints de revisión · ACEPTADA
El trabajo avanza en tramos cortos que terminan en un checkpoint: se para, se verifica lo hecho
y se revisa antes de seguir. Las decisiones que surjan se registran aquí.

---

## Decisiones pendientes / propuestas

<!-- Las decisiones que surjan se añaden aquí en estado PROPUESTA y detienen el desarrollo. -->
<!-- Ejemplo de plantilla:

### ADR-0XX — <título corto> · PROPUESTA
**Contexto:** <por qué surge>
**Opciones:** A) ... B) ... C) ...
**Recomendación:** <cuál y por qué>
**Impacto en el TFM:** <si afecta a requisitos/diseño/evaluación>
-->

> Añadidas en **CP-0** (2026-07-07). **RESUELTAS en la revisión de CP-0 (2026-07-07)** →
> todas pasan a `ACEPTADA`. Resumen de resoluciones:
> - **ADR-008:** el tag `python:3.12-slim-trixie` verificado como existente en Docker Hub
>   (imagen amd64, push 2026-06-24) → aceptado, sin fallback.
> - **ADR-011 (licencia):** Rafael elige **Valkey 8 (BSD)** — fork Linux Foundation tras el
>   cambio de licencia de Redis (2024). Stack 100% open source permisivo. `docker-compose.yml`
>   debe usar `valkey/valkey:8-alpine` en lugar de `redis:7.2-alpine` a partir de CP-1.
> - **ADR-009/010:** aceptadas conservadoras (Node 22 LTS, PostgreSQL 16).
> - **ADR-013:** aceptado el enfoque Buildroot; armel/armhf + par máquina/kernel se cierran en CP-2.
> - Resto (007, 012, 014): aceptadas tal cual.

### ADR-007 — Imagen base de la API (Python) · ACEPTADA
**Recomendación:** `python:3.12-slim-bookworm`.
**Justificación:** fija el Python 3.12 ya decidido (ADR-003); `slim` reduce la imagen y
la superficie; `bookworm` (Debian 12) es la base más madura y con mejor compatibilidad de
wheels/tooling para el ecosistema FastAPI/SQLAlchemy.

### ADR-008 — Imagen base del worker (Python + QEMU) · ACEPTADA
**Contexto:** el worker necesita, además de Python 3.12, un `qemu-system-*` reciente para
emulación full-system ARM/MIPS con virtio y modelos de placa modernos. Debian 12
(bookworm) solo empaqueta QEMU 7.2; Debian 13 (trixie, estable desde ago-2025) empaqueta
QEMU 9.2.
**Opciones:** A) `python:3.12-slim-trixie` + `apt install qemu-system-arm` (QEMU 9.2).
B) `python:3.12-slim-bookworm` + QEMU de backports (frágil). C) `debian:trixie-slim` +
instalar Python 3.12 a mano. D) compilar QEMU desde fuente (control total, build lento).
**Recomendación:** A — base Python oficial sobre Debian 13, QEMU 9.2 vía
apt (reproducible, sin compilar).
**⚠ A verificar:** que el tag `python:3.12-slim-trixie` esté publicado; si no, fallback a C.
**Impacto en el TFM:** afecta al diseño de la capa de emulación (Cap. 4.2.2) y a la
reproducibilidad (principio de ingeniería del brief).

### ADR-009 — Imagen base del frontend (Node) · ACEPTADA
**Recomendación:** `node:22-bookworm-slim` (Node.js 22 «Jod», Active LTS, soporte hasta
2027).
**Justificación:** LTS estable y ampliamente adoptada; solo se usa para construir/servir la
SPA de Vite, no necesita features de Node 24. **Alternativa:** `node:24-bookworm-slim` si se
prefiere la LTS más reciente.

### ADR-010 — Imagen de PostgreSQL · ACEPTADA
**Recomendación:** `postgres:16-bookworm` (PostgreSQL 16.x).
**Justificación:** rama muy probada, excelente soporte en `asyncpg`/SQLAlchemy; el modelo de
datos del proyecto (muestra → syscalls/red/fs/IoCs) no requiere ninguna feature exclusiva de
PG17. **Alternativa:** `postgres:17-bookworm` si se quiere la rama más nueva.

### ADR-011 — Broker de Celery: Redis vs Valkey (LICENCIA) · ACEPTADA
**Contexto:** Celery necesita un broker con protocolo Redis. Desde Redis 7.4 (mar-2024) la
licencia dejó de ser BSD (pasó a SSPLv1/RSALv2, no OSI); Redis 8.0 (may-2025) reañadió
AGPLv3. Para un TFM la trazabilidad de licencias importa.
**Opciones:** A) `redis:7.2-alpine` — última versión **BSD-3** (permisiva, open source),
súper probada con Celery, pero rama antigua. B) `redis:8-alpine` — actual, **AGPLv3** (open
source copyleft; como broker de red sin modificar, las obligaciones AGPL son mínimas).
C) `valkey/valkey:8-alpine` — fork de la Linux Foundation, **BSD-3**, drop-in para Celery.
**Recomendación:** A (`redis:7.2-alpine`) para el MVP por licencia permisiva
y compatibilidad probada; migrar a C (Valkey) si se quiere versión moderna con licencia
limpia. Cualquiera es drop-in para Celery.
**⚠ Decisión humana:** elegir A / B / C es una cuestión de licencia → la resuelve Rafael.
**Impacto en el TFM:** menor técnicamente, pero conviene justificar la elección de licencia
en la memoria (Cap. 3/4).

### ADR-012 — Versión de QEMU y máquina ARM objetivo · ACEPTADA
**Recomendación:** **QEMU 9.2.x** full-system, instalado como paquete de la distro base del
worker (Debian 13, ADR-008) para reproducibilidad. Máquina ARM propuesta: `-M virt` (virtio,
moderna) frente a placas legacy (`versatilepb`, `vexpress-a9`).
**Justificación:** 9.2 es reciente y estable, con buen soporte de placas ARM/MIPS y virtio;
instalarla vía apt evita compilar. La selección definitiva de máquina/kernel/CPU se cierra en
**CP-2** (hito técnico más arriesgado) según el rootfs elegido.

### ADR-013 — Tooling y distro del rootfs ARM · ACEPTADA
**Contexto:** el invitado necesita un rootfs mínimo con `strace`, `tcpdump`/`tshark` e
`inotify-tools`, reproducible y pequeño.
**Opciones:** A) **Buildroot** (rama LTS `2024.02.x`) — genera kernel + rootfs mínimos y
reproducibles; los tres paquetes de telemetría existen como opciones BR2. B) Debian `armhf`
vía `debootstrap`/`mmdebstrap` + `qemu-user-static` — más «realista» pero más pesado y lento.
C) imagen prehecha de terceros (p. ej. `qemu` sample images) — rápida pero opaca/poco
reproducible.
**Recomendación:** A (Buildroot 2024.02 LTS) por tamaño, reproducibilidad y
control fino de la telemetría; se documenta el `defconfig` para la memoria.
**⚠ A confirmar en CP-2:** ARM soft-float vs hard-float (armel/armhf) y el par
máquina+kernel, que dependen del binario de prueba y de las muestras reales previstas.
**Impacto en el TFM:** núcleo de la sección de implementación (Cap. 4.2.2) y de la
reproducibilidad.

### ADR-014 — Convenciones de build y orquestación · ACEPTADA
**Recomendación:** (1) **Compose Spec** sin clave `version:` (obsoleta en Compose v2).
(2) Gestión de dependencias Python con **`pip` + `requirements.txt` con versiones fijadas**
(simple y reproducible; `uv` como opción futura si el build lento molesta). (3) Gestor del
frontend: **`npm`** con `package-lock.json` (por defecto, sin fricción).
**Justificación:** minimiza complejidad en el MVP («empezar simple») manteniendo builds
deterministas. Todas revisables sin coste de migración más adelante.

---

## Decisiones de implementación (añadidas durante la construcción)

### ADR-015 — Estructura de la app y estrategia de migraciones (CP-1) · ACEPTADA
**Contexto:** al implementar CP-1 hubo que fijar cómo se organiza el código y quién/cómo
aplica el esquema de BD, sin que estuviera detallado en ADRs previos.
**Decisiones (firmes, MVP):**
- **API** como paquete `backend/app/`: `config.py` (pydantic-settings, lee env vars),
  `db.py` (engine async `create_async_engine` + `async_sessionmaker` sobre asyncpg),
  `models.py` (SQLAlchemy 2.0 declarativo, `DeclarativeBase` + `Mapped`), `celery_client.py`
  (productor de tareas) y `main.py` (FastAPI). **Worker** como módulo plano
  `worker/celery_app.py` (más simple; crece en CP-2/CP-3).
- **Alembic en modo ASÍNCRONO**: `env.py` usa `async_engine_from_config` + `run_sync`, de modo
  que una **única** `DATABASE_URL` (`postgresql+asyncpg://…`) sirve para la app y para las
  migraciones (sin driver sync adicional). La URL se inyecta desde `app.config.settings`
  (fuente única de verdad), no se duplica en `alembic.ini`.
- **Quién migra:** las migraciones se aplican en el **entrypoint de la API**
  (`alembic upgrade head` antes de arrancar uvicorn), no en el worker → un único responsable
  del esquema y arranque idempotente.
- **Desacoplo API↔worker:** la API encola la tarea **por nombre** con `send_task("ping")` sin
  importar el código del worker; comparten solo broker+backend. En Valkey: **DB 0 = broker**
  (cola), **DB 1 = backend de resultados**.
- **Endpoint temporal `GET /ping-task`:** solo para CP-1, demuestra el circuito
  API→Valkey→worker→`"pong"`. Es síncrono a propósito (FastAPI lo corre en threadpool, el
  `.get()` bloqueante no congela el event loop). **Se retira en CP-3** al llegar el flujo real.
**Impacto en el TFM:** describe la capa de aplicación y el arranque reproducible (Cap. 4.2.2).

---

## Cómo se conecta con la "memoria" del TFM

- Cada ADR `ACEPTADA` que afecte al **diseño** o a los **requisitos** se traslada al Capítulo 4
  del TFM (secciones 4.2.1 Identificación de requisitos y 4.2.2 Descripción de la herramienta).
- Las restricciones del TFM (stack del Cap. 3, arquitectura del §2.3) se reflejan aquí como
  ADRs `ACEPTADA` de partida. Flujo bidireccional: **proyecto ⇄ memoria**.
