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
**✔ Confirmado en CP-2 (ver ADR-016):** ARM **hard-float (armhf, EABIhf)**, máquina
`-M vexpress-a9` (Cortex-A9 / ARMv7-A), kernel `zImage` 6.1.44 + rootfs `rootfs.ext2`
generados con Buildroot 2024.02.11.
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

### ADR-016 — Enfoque final del rootfs ARM y cierre del par máquina/kernel/ISA (CP-2) · ACEPTADA
**(enmienda que CIERRA ADR-013 y corrige ADR-012)**

**Contexto:** CP-2 debía fijar el tooling del rootfs (ADR-013), el par máquina/kernel/ISA y
el entorno QEMU (ADR-012). Se fijaron y se verificaron con una detonación real del binario
benigno de prueba (los 3 artefactos se generan con contenido real).

**Decisiones (firmes, MVP):**
- **Rootfs = Buildroot (opción A de ADR-013), confirmado como enfoque PRIMARIO.** No hizo
  falta el fallback. Buildroot **2024.02.11 LTS** + defconfig oficial
  `qemu_arm_vexpress_defconfig` + fragmento `emulation/arm/buildroot/telemetry.fragment`
  (añade `strace`, `tcpdump`, `inotify-tools` y un rootfs-overlay con el binario de prueba y
  `/sbin/telemetry_init`). Reproducible: Buildroot auto-construye sus host-tools
  (m4/bison/flex…) pinneados, sin depender de versiones del host; los tarballs se cachean en
  `emulation/arm/_build/dl`.
- **Par máquina / kernel / ISA (CIERRA ADR-013):**
  - Máquina: **`-M vexpress-a9`** (ARM Versatile Express), CPU **Cortex-A9 / ARMv7-A**.
  - ISA/ABI del invitado: **armhf** — `BR2_ARM_EABIHF` (hard-float), `VFPv3-D16`, set de
    instrucciones ARM, **glibc** (`BR2_TOOLCHAIN_BUILDROOT_GLIBC`).
  - Kernel: **`zImage` Linux 6.1.44** + DTB `vexpress-v2p-ca9.dtb`.
  - Rootfs: `rootfs.ext2` como tarjeta SD → `/dev/mmcblk0` (tamaño se ajusta a 256 MiB,
    potencia de 2, en tiempo de arranque; requisito de la SD de vexpress-a9).
  - Binario de prueba: `arm-linux-gnueabihf-gcc -static` (ARMv7-A hard-float); estático →
    corre en el invitado con independencia de su libc.
- **Corrección de ADR-012 (versión de QEMU):** Debian 13 «trixie» empaqueta
  **`qemu-system-arm` 10.0.8** (no 9.2). Se adopta 10.0.8 vía apt (más reciente, igualmente
  reproducible). Sin impacto funcional.
- **Entorno de build+run:** todo en el contenedor `iot-sandbox/emulation:dev`
  (`docker/emulation.Dockerfile`, Debian 13). No muta el host ni requiere `sudo`. QEMU
  cross-ISA usa **TCG** (sin KVM) → sin privilegios elevados.
- **Extracción de artefactos:** el invitado los escribe en `/telemetry` (en el propio ext2) y
  el host los lee con **`debugfs` SIN montar** la imagen (sin privilegios). Alternativa a 9p,
  elegida por robustez (no depende de drivers 9p en el kernel de la placa).
- **Apagado limpio:** el invitado hace `reboot -f` con QEMU `-no-reboot` (sale con rc=0);
  `run_emulation.sh` añade un timeout de seguridad. No quedan procesos/contenedores colgando.

**Aislamiento de red (matiz):** en CP-2 se deja SLIRP normal para GARANTIZAR que el intento
de red del binario quede capturado (contacta IPs/dominios de documentación RFC5737/RFC2606).
El aislamiento pleno (`restrict=on` / INetSim) es **CP-5**; activable ya con
`SANDBOX_NET_RESTRICT=1`.

**Impacto en el TFM:** cierra el núcleo de la implementación (Cap. 4.2.2) y su reproducibilidad.

### ADR-017 — Cableado worker→emulación: Docker-out-of-Docker (DooD) (CP-3) · ACEPTADA
**Contexto:** el worker Celery debe lanzar la emulación de CP-2, que vive en la imagen
`iot-sandbox/emulation:dev` (QEMU 10 + Buildroot + toolchain, ADR-016). Hay que decidir CÓMO
el worker (un contenedor) arranca otro contenedor con QEMU sin duplicar esa imagen ni meter
QEMU en el worker.

**Opciones:** A) **DooD** — montar el socket `/var/run/docker.sock` del host en el worker;
el worker usa el SDK de Docker (`docker==7.1.0`) para lanzar `iot-sandbox/emulation:dev`.
B) **DinD** (sidecar `docker:dind` privilegiado) — más pesado y también privilegiado.
C) instalar QEMU+Buildroot+imágenes dentro del worker — duplica la capa de emulación y acopla
dos servicios que ADR-016 dejó aislados.

**Decisión:** **A (DooD).** Reutiliza VERBATIM la imagen de CP-2; el worker queda fino (solo
deps Python). El worker resuelve el intercambio de datos SIN codificar rutas del host:
inspecciona sus propios montajes (`inspect_container($HOSTNAME).Mounts`) para derivar (1) la
ruta del repo en el host (bind `/project`), (2) el nombre del volumen de muestras
(`/data/samples`) y (3) el de artefactos (`/data/artifacts`); admite override por env
`HOST_PROJECT_DIR` / `SAMPLE_VOLUME` / `ARTIFACTS_VOLUME`. Lanza la emulación con esos tres
montajes (proyecto ro, muestras ro, artefactos rw), `IN_SANDBOX=1`, `SAMPLE_BIN=<vol>/<sha256>`
y recoge los artefactos de su propio montaje del volumen `artifacts`.

**Inyección de la muestra:** la muestra NO confiable se escribe en el rootfs ext2 con
`debugfs -w` (sin montar, sin privilegios) sustituyendo `/opt/sample/test_sample` y marcándola
`0100755 uid=0`; solo se ejecuta DESPUÉS dentro de QEMU (`SAMPLE_BIN` en `run_emulation.sh`).

**⚠ Riesgo de seguridad (relevante):** montar `docker.sock` en el worker equivale a acceso
root en el host (quien controla el socket puede crear contenedores privilegiados, montar `/`,
etc.). **Mitigaciones adoptadas:**
- El worker solo lanza una **imagen fija y conocida** con un comando fijo; **sin** `--privileged`,
  sin `/dev/kvm`, sin caps extra (QEMU cross-ISA por TCG, ADR-016).
- La muestra maliciosa se ejecuta **dentro de QEMU**, dos capas de aislamiento por debajo del
  socket; **nunca** toca el proceso worker ni el socket. Montajes al contenedor de emulación:
  proyecto y muestras en **solo lectura**.
- El worker no expone el socket a la muestra ni a la red.

**Mitigaciones futuras (fuera del MVP):** socket-proxy (p.ej. `tecnativa/docker-socket-proxy`)
restringido a crear-contenedor sobre esa única imagen; Docker rootless; o un runner dedicado
(VM/microVM). Se anota para el capítulo de seguridad/limitaciones del TFM.

**Impacto en el TFM:** describe la integración worker↔emulación y su superficie de riesgo
(Cap. 4.2.2 + apartado de seguridad/limitaciones).

### ADR-018 — Modelo de datos del análisis y estrategia de parseo (CP-3) · ACEPTADA
**Contexto:** CP-3 debía cerrar el modelo de datos (borrador de `ARCHITECTURE.md`) y elegir las
librerías de parseo de los 3 artefactos.

**Modelo de datos (firme, MVP):** `sample 1─* {syscall_event, network_flow, fs_event, ioc}`,
todas las hijas con **FK ON DELETE CASCADE**. Se añaden a `sample` las columnas `size_bytes`,
`error` y `finished_at` (migración Alembic `0002_analysis_model`). Ciclo de estado de la
muestra: `queued → running → done | failed`. `ioc` lleva **UNIQUE(sample_id, type, value)**:
un indicador por muestra, con la columna `source` = fuentes que lo corroboran unidas por comas
(p.ej. una IP vista en strace Y en el pcap → `"pcap,strace"`). `network_flow` guarda flujos IP
**agregados por 4-tupla** (proto, src, dst, dport) con contadores `packets`/`bytes`.

**Extracción de IoCs:** `type ∈ {ip, domain, file, port, hash}`. Reglas: dominios de las
consultas DNS del pcap; IPs/puertos de destinos **externos** (se excluye la subred interna de
QEMU SLIRP `10.0.2.0/24`, que es infraestructura del sandbox, no un IoC) tanto del pcap como de
`connect/sendto` en strace; ficheros de los syscalls de escritura/creación (`openat` con
`O_CREAT|O_WRONLY|O_RDWR`, `chmod`, `unlink`, `rename`…) y de `fs_events.log`, ignorando rutas de
solo-lectura del sistema (`/proc`, `/sys`, `/etc`, …); y el `sha256` de la muestra como IoC
`hash`. Deduplicado por (type, value).

**Librerías de parseo:**
- **pcap → `scapy==2.6.1`** (Python puro). **Motivo:** NO requiere `tshark`/wireshark en la
  imagen del worker (que queda fina, solo pip), disecciona nativamente el linktype "cooked"
  (SLL/SLLv2) que produce `tcpdump -i any` y extrae los nombres de consulta DNS necesarios para
  los IoCs de dominio. Alternativa descartada: **pyshark** (envuelve `tshark` → obligaría a
  instalar wireshark-common en el worker, +100 MB y un binario externo).
- **strace/fs_events → parseo propio con expresiones regulares** (formato line-oriented estable
  de `strace -f -tt -T` e `inotifywait --format`), sin dependencias.
- **BD del worker → SQLAlchemy Core SÍNCRONO + `psycopg[binary]==3.2.3`.** Las tareas Celery son
  síncronas; la `DATABASE_URL` async (`+asyncpg`) se reescribe a `+psycopg`. El worker declara
  las tablas como objetos Core (no importa el ORM de la API) manteniendo el desacoplo API↔worker
  de ADR-015 (comparten broker+BD, no código; la DDL la posee Alembic en el lado API).

**Impacto en el TFM:** fija el modelo relacional y la técnica de extracción de IoCs (Cap. 4.2.2)
que se evalúan con malware real en CP-7.

### ADR-019 — Frontend SPA: routing, cliente HTTP y estrategia de servido/proxy (CP-4) · ACEPTADA
**Contexto:** CP-4 cierra el MVP con la SPA Vue 3 (ADR-003/009). Había que fijar la forma de
navegación, el cliente HTTP, y —sobre todo— CÓMO se sirve la web y cómo alcanza a la API tanto en
Docker como en desarrollo local, sin CORS.

**Decisiones (firmes, MVP):**
- **Framework/tooling:** **Vue 3.5.39** (Composition API, `<script setup>`) + **Vite 6.4.3** +
  **vue-router 4.6.4**. Dos rutas: dashboard `/` (subida + listado) y reporte `/samples/:id`.
  **Sin store global** (Pinia): el estado es local a cada vista (listado, reporte); el MVP no
  justifica una capa de estado compartida. Gestor `npm` + `package-lock.json` (ADR-014), versiones
  **fijadas exactas** (nada de `^`/`latest`).
- **Cliente HTTP = `fetch` nativo** (sin axios). Menos dependencias que auditar/justificar y
  suficiente para el contrato REST (multipart en `POST`, JSON en `GET`). Un módulo `src/api.js`
  centraliza las llamadas y normaliza los errores (`ApiError` con `status` + `detail`), de modo que
  la UI distingue 400 (arch/vacío), 413 (tamaño), 404 (id) y el flag `deduplicated`.
- **Servido en producción = build estático + nginx (multi-stage), NO dev-server.** El Dockerfile
  hace `vite build` con `node:22-bookworm-slim` (ADR-009) y sirve el bundle con `nginx:1.29-alpine`.
  nginx **reverse-proxya** `/api/ → http://api:8000/`, dejando la SPA **same-origin (sin CORS)**; el
  navegador solo habla con el puerto **5173**. En desarrollo (`npm run dev`) el proxy equivalente lo
  provee el dev-server de Vite (`/api` → `http://localhost:8000`). El destino es configurable por
  **`VITE_API_BASE`** (default `/api`). Alternativa descartada: `vite preview` (dev-server en prod,
  sin proxy real ni caché/gzip; menos representativo para las capturas del TFM).
- **Actualización de estado = polling** (no websockets). Listado y reporte reprograman un
  `setTimeout` mientras haya muestras en `queued`/`running`; se detiene al `done`/`failed`. Simple,
  robusto y suficiente para detonaciones de ~15 s. WebSockets/SSE quedan fuera del MVP.
- **Healthcheck del contenedor frontend apunta a `127.0.0.1`** (no `localhost`): dentro de Alpine
  `localhost` resuelve primero a `::1` (IPv6) y nginx (`listen 5173`) escucha solo en IPv4 →
  `connection refused`. El acceso del host va por el puerto mapeado IPv4 y no se ve afectado.

**Impacto en el TFM:** describe la capa de presentación y su integración con la API (Cap. 4.2.2);
las capturas de la web para la memoria se obtienen de esta SPA.

### ADR-020 — Registro de perfiles de emulación por ISA (CP-6) · ACEPTADA
**Contexto:** el título del TFM es «multi-arquitectura». ADR-002 anticipó que generalizar más
allá de ARM es «casi mecánico» (otro kernel + rootfs + binario QEMU). CP-6 lo materializa sin
duplicar la capa de emulación de ARM (CP-2, ADR-016).

**Decisión:** sustituir los scripts específicos de ARM (`emulation/arm/{build_rootfs,run_emulation}.sh`)
por **dos scripts genéricos** (`emulation/{build_rootfs,run_emulation}.sh <arch>`) **dirigidos por
un registro de perfiles**: `emulation/profiles/<arch>.env`. Cada perfil declara variables `P_*`
que describen íntegramente la ISA: defconfig de Buildroot, toolchain (+cflags) del binario de
prueba, binario y máquina de QEMU, kernel/DTB, interfaz de disco y dispositivo raíz, consola
serie, modelo de NIC, resize del rootfs y el mapeo ELF (`e_machine`/endianness) para la
autodetección (ADR-021). Se **comparte** todo lo arch-agnóstico en `emulation/common/`:
`overlay/sbin/telemetry_init` (PID 1 del invitado, shell POSIX), `testbin/test_sample.c` (C
portable, ADR-005) y `telemetry.fragment` (paquetes strace/tcpdump/inotify + tamaño ext2). El
binario de prueba se cross-compila **estático** por ISA en un `sample-overlay` propio; Buildroot
funde ambos overlays (`BR2_ROOTFS_OVERLAY="…/common/overlay …/<arch>/_build/sample-overlay"`).

- **ARM = primer entry del registro** (`profiles/arm.env`): mismo par máquina/kernel/rootfs de
  ADR-016 (vexpress-a9, armhf, zImage+DTB, SD→/dev/mmcblk0). El kernel+rootfs ya construidos se
  reutilizan sin recompilar; verificado con el script genérico (regresión OK).
- **Pares máquina/kernel/rootfs de las ISAs nuevas** tomados del readme oficial de cada placa
  QEMU de Buildroot (`board/qemu/*/readme.txt`), no inventados:
  - **mips / mipsel:** `qemu_mips32r2{,el}_malta_defconfig`, `-M malta`, kernel `vmlinux`, disco
    IDE→**/dev/sda** (libata), NIC **pcnet**, consola **ttyS0**. Toolchain `mips{,el}-linux-gnu-gcc`
    (`-march=mips32r2 -mabi=32 -E{B,L}`).
  - **x86_64:** `qemu_x86_64_defconfig`, `-M pc`, kernel `bzImage`, disco **virtio→/dev/vda**, NIC
    **virtio**, consola **ttyS0**. Binario de prueba con el gcc nativo del contenedor.
- **Entorno de build/run:** un único contenedor `iot-sandbox/emulation:dev` (Debian 13) con
  `qemu-system-{arm,mips,x86}` (QEMU 10.0.8) + toolchains armhf/mips/mipsel; cross-ISA por **TCG**
  (sin KVM/privilegios). Cache de descargas de Buildroot **compartida** (`emulation/_dl/`).
- **Worker:** `run_emulation(arch=…)` pasa la ISA como 1er argumento al script genérico (DooD,
  ADR-017 intacto). No hay rutas por ISA codificadas en el worker.

**Alternativa descartada:** duplicar `emulation/<arch>/{build,run}.sh` por ISA (lo que sugería el
scaffolding de CP-0) → divergencia y mantenimiento cuadrático. El registro deja «añadir una ISA =
añadir un `.env`».

**Impacto en el TFM:** núcleo de la generalización multi-arquitectura (Cap. 4.2.2); el registro
es directamente tabulable en la memoria.

### ADR-021 — Autodetección de arquitectura por cabecera ELF (CP-6) · ACEPTADA
**Contexto:** al subir una muestra hay que elegir el perfil de la sandbox. Exigir que el analista
declare la ISA es frágil (malware IoT llega sin metadatos fiables).

**Decisión:** `POST /samples` **autodetecta la ISA** leyendo la cabecera ELF de los primeros
bytes del binario (`backend/app/archdetect.py`, sin dependencias): magic `\x7fELF`, `EI_DATA`
(endianness) y `e_machine` (offset 18, uint16 en esa endianness). Mapeo: `EM_ARM(40)→arm`,
`EM_MIPS(8)→mips` si big-endian / `mipsel` si little-endian, `EM_X86_64(62)→x86_64`
(`EM_386(3)→i386`, `EM_AARCH64(183)→aarch64` se reconocen pero no tienen perfil). El campo
`arch` del multipart pasa a `auto` por defecto: **si viene explícito (arm|mips|mipsel|x86_64) se
respeta; si es `auto`/vacío se autodetecta**. Se rechaza con **400** (mensaje claro) toda ISA sin
perfil disponible o cuando el fichero no es un ELF reconocible y no se dio `arch`. El gate
`supported_arches` es overridable por env (`SUPPORTED_ARCHES="arm,mips,…"`). El frontend ofrece
«Detección automática (ELF)» como opción por defecto.

**Alternativas descartadas:** `python-magic`/`libmagic` o invocar `file`/`readelf` (dependencia
externa en la imagen de la API por 12 bytes de cabecera); heurísticas por extensión de fichero
(el malware IoT no tiene extensión fiable).

**Impacto en el TFM:** describe la selección automática de sandbox (Cap. 4.2.2) y refuerza la
usabilidad del análisis multi-arquitectura.

### ADR-022 — Simulación de servicios de red y aislamiento de la detonación (CP-5) · ACEPTADA

**Contexto:** hasta CP-4 el invitado salía por SLIRP con NAT del contenedor, así que (a) su
tráfico podía alcanzar Internet de verdad —inaceptable para detonar malware real en CP-7— y
(b) nadie le contestaba: el DNS devolvía NXDOMAIN y los SYN al C2 se perdían. Ese es
justamente el escenario de evasión descrito en §2.2.4 de la memoria: el binario comprueba la
conectividad, ve que no hay red y no despliega su carga.

**Decisión.** Tres piezas:

1. **Red de detonación aislada.** Red Docker `sandbox_sim` con `internal: true` (172.31.240.0/24).
   El contenedor de emulación se lanza ahí en lugar del bridge por defecto, de modo que **no
   existe ruta a Internet** aunque fallase todo lo demás. Verificado: `Network is unreachable`.

2. **Servicios simulados.** `inetsim` (INetSim 1.3.2, 172.31.240.10) sirve HTTP, HTTPS, FTP,
   SMTP, POP3, IRC, NTP, TFTP, syslog, time y un catch-all `dummy` que acepta la conexión en
   cualquier otro puerto. `simdns` (dnsmasq, 172.31.240.11) resuelve **cualquier** dominio a
   192.0.2.1 (TEST-NET-1, RFC 5737).

3. **Redirección del egress.** El contenedor de emulación instala con nftables un DNAT en
   `nat/output` que manda el 53 a `simdns`, los puertos con servicio propio a INetSim
   conservando el puerto, y **todo lo demás al catch-all**. Requiere `CAP_NET_ADMIN`.

**Por qué DNAT en el contenedor y no una tap + bridge.** Con SLIRP el invitado ya sale como
tráfico local del contenedor, así que basta reescribir el destino una capa por fuera: QEMU
sigue **sin privilegios ni /dev/net/tun**, y el único permiso extra es `NET_ADMIN` sobre una
red sin salida. La alternativa (tap + bridge) obligaba a dar tun y más capacidades al proceso
que ejecuta la muestra, que es exactamente lo que interesa no hacer.

**Por qué dnsmasq y no el DNS de INetSim.** INetSim 1.3.2 (2020) llama a
`Net::DNS::Nameserver->main_loop`, retirado en Net::DNS ≥ 1.01 (Debian 13 trae 1.56): el
servicio muere al nacer con *Can't locate object method "main_loop"*. La API que lo sustituye
(`start_server`) aborta explícitamente si se la invoca desde un subproceso, que es como
INetSim arranca cada servicio, así que el arreglo obligaba a parchear dos módulos de terceros.
dnsmasq da el mismo comportamiento comodín (`address=/#/192.0.2.1`) con un paquete mantenido.
Va en **su propio contenedor**: conviviendo con INetSim bajo el mismo PID 1, INetSim se queda
colgado en «Forking services…» sin arrancar ninguno (comprobado).

**Ruta por defecto.** En una red `internal` Docker no instala *default gateway*, y sin ruta un
`connect()` a una IP codificada en la muestra falla con `ENETUNREACH` **antes** de generar
paquete: el DNAT no lo vería y el invitado deduciría que está enjaulado. El contenedor añade
`default via <INetSim>`, que está en la misma /24.

**Efecto sobre los IoCs: ninguno.** `tcpdump` corre DENTRO del invitado, así que el pcap
conserva la IP y el puerto que la muestra pidió de verdad; la reescritura ocurre por fuera.
La única IP sintética que puede aparecer es 192.0.2.1 (respuesta del DNS), y `parsers.py` la
trata como infraestructura, igual que la 10.0.2.0/24 de SLIRP. El IoC bueno ahí es el dominio.

**Activada por defecto** (`SANDBOX_NET_SIM=1` en compose) por ser la postura segura;
`SANDBOX_NET_SIM=0` vuelve al comportamiento de CP-2..CP-4.

**✔ `CAP_NET_ADMIN` confirmado en revisión (2026-08-24).** Se acepta como contrapartida
necesaria del aislamiento: es lo que permite encerrar la detonación en una red sin salida y
redirigir su tráfico, evitando que la muestra alcance sistemas de terceros. La capacidad la
recibe el contenedor de emulación, no el proceso que ejecuta la muestra —QEMU sigue sin
privilegios ni `/dev/net/tun`— y actúa sobre una red `internal` sin ruta a Internet. Queda
así cerrado el requisito de aislamiento antes de detonar malware real en CP-7.

**Impacto en el TFM:** cumple el objetivo específico 3 (§3.2) y el Sprint 4 (§3.3.2); pasa a
Cap. 4.2 como componente propio y **deja sin efecto la limitación de §4.3.4**, que declaraba la
simulación de red «diseñada pero pendiente de integración». Aporta además un resultado medible
para §4.3: mismo binario, con y sin simulación (NXDOMAIN + SYN sin respuesta → NOERROR +
handshake completo).

---

---

## Cómo se conecta con la "memoria" del TFM

- Cada ADR `ACEPTADA` que afecte al **diseño** o a los **requisitos** se traslada al Capítulo 4
  del TFM (secciones 4.2.1 Identificación de requisitos y 4.2.2 Descripción de la herramienta).
- Las restricciones del TFM (stack del Cap. 3, arquitectura del §2.3) se reflejan aquí como
  ADRs `ACEPTADA` de partida. Flujo bidireccional: **proyecto ⇄ memoria**.
