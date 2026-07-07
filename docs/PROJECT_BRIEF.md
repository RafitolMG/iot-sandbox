# PROJECT BRIEF — IoT Malware Dynamic Analysis Sandbox

> **Documento de encargo del proyecto.** Fija el alcance antes de escribir código; es la
> fuente de verdad junto con `DECISIONS.md` (registro de decisiones) y `ROADMAP.md` (hitos).

---

## 1. Contexto

Este proyecto es la contribución práctica de un Trabajo Fin de Máster (TFM) en Ciberseguridad
(Universidad Internacional de La Rioja). El TFM se titula *"Diseño e implementación de un
sistema automatizado de análisis dinámico de malware para entornos IoT multi-arquitectura"*.

Se construye una **sandbox** (entorno aislado) que ejecuta binarios de malware IoT compilados
para arquitecturas no estándar (ARM, MIPS, MIPSEL, x86_64) dentro de **QEMU en modo full-system**,
capturando su comportamiento en tiempo real para extraer **Indicadores de Compromiso (IoCs)**.
Todo se opera desde una **interfaz web** y se despliega con **Docker Compose**.

Es **investigación de seguridad legítima y autorizada** (TFM académico). Aun así, se manejan
binarios maliciosos reales: la seguridad y el aislamiento son requisitos de primer nivel
(ver §6).

## 2. Forma de trabajo

La arquitectura y el alcance no se deciden sobre la marcha: al llegar a un punto de decisión el
trabajo **se detiene** y la decisión se registra (ver `CHECKPOINTS.md`). Se resuelve fuera del
código —con el contexto del TFM y, cuando toca, con el tutor— y queda escrita en `DECISIONS.md`,
que se consulta antes de cada tramo de trabajo.

## 3. Stack tecnológico (ya decidido — NO lo cambies sin checkpoint)

| Capa | Tecnología | Notas |
|---|---|---|
| Backend / API | Python 3.12 + FastAPI | API REST asíncrona, validación con Pydantic |
| Cola de tareas | Celery + Redis | El análisis es lento; nunca bloquear la API |
| Base de datos | PostgreSQL | Datos relacionales: muestra → syscalls / red / ficheros / IoCs |
| Emulación | QEMU full-system | ARM primero (MVP); luego MIPS/MIPSEL/x86_64 |
| Simulación de red | INetSim (o FakeNet-NG) | Anti-evasión; se añade en hito posterior |
| Frontend | Vue 3 + Vite | SPA, Composition API |
| Orquestación | Docker Compose | web + db + redis + worker(s) |
| Telemetría en la VM | strace, tcpdump/tshark, inotify-tools | syscalls, red, sistema de ficheros |
| Calidad | Ruff + Black (Python), ESLint + Prettier (Vue), pytest | |
| Control de versiones | Git (repo local ya inicializado) | Commits pequeños y descriptivos, en inglés |

## 4. Objetivo del MVP (Hito 1) — enfoque "una arquitectura primero"

Hacer funcionar **el flujo completo de punta a punta con UNA sola arquitectura (ARM)** antes
de generalizar:

```
[subir binario ARM por la web] → [encolar tarea] → [worker lanza QEMU-ARM full-system]
   → [ejecuta el binario en un rootfs mínimo con telemetría]
   → [captura syscalls + tráfico de red + cambios en ficheros]
   → [extrae IoCs] → [guarda en PostgreSQL] → [muestra reporte en la web]
```

Cuando este flujo funcione con ARM, se añaden MIPS/MIPSEL/x86_64 (cambio casi mecánico:
otro kernel + otro rootfs + otro binario QEMU).

## 5. Principios de ingeniería

- **Reproducibilidad total**: `docker compose up` debe levantar el sistema en una máquina limpia.
- **Desacoplamiento**: API, workers, emulación y frontend son piezas independientes.
- **Trazabilidad**: cada decisión relevante queda en `DECISIONS.md` (sirve de material para el Cap. 4 del TFM).
- **Documentar para la memoria**: el código y las decisiones deben poder narrarse en el TFM
  (requisitos, diseño, implementación, evaluación). Mantén un `docs/DEV_LOG.md` con lo hecho en cada checkpoint.
- **Empezar simple**: nada de sobre-ingeniería. El MVP manda.

## 6. Seguridad y manejo de malware (OBLIGATORIO)

- Durante el desarrollo del MVP, **NO se ejecuta malware real**. Se usa un **binario ARM benigno
  de prueba** (por ejemplo, un `busybox` o un "hello world" ARM que haga syscalls, escriba un
  fichero y abra una conexión de red) para validar toda la tubería de telemetría.
- El malware real **solo** se ejecuta en la fase de evaluación (hito posterior) y **siempre**
  dentro de QEMU full-system, **nunca** en el host.
- El worker que lanza QEMU debe tratar la muestra como **no confiable**: sin montar el sistema
  de ficheros del host, red del invitado aislada/simulada, sin credenciales.
- El binario de la muestra nunca se ejecuta, `chmod +x` ni se abre fuera del invitado QEMU.
- No descargar muestras de malware de forma automática. Los datasets reales (p. ej. muestras
  Mirai/Gafgyt) los aporta Rafael manualmente en la fase de evaluación.

## 7. Qué NO hacer

- No cambiar el stack sin checkpoint.
- No saltarte los checkpoints (`CHECKPOINTS.md`).
- No ejecutar malware real fuera de QEMU, ni durante el MVP.
- No añadir arquitecturas hasta que ARM funcione de punta a punta.
- No dejar secretos/credenciales en el repo.

## 8. Ficheros de gobierno del proyecto

- `docs/PROJECT_BRIEF.md` — este documento (el encargo).
- `docs/DECISIONS.md` — registro de decisiones (ADR). **Léelo antes de cada tramo.**
- `docs/CHECKPOINTS.md` — protocolo de paradas de comunicación.
- `docs/ROADMAP.md` — hitos y estado.
- `docs/ARCHITECTURE.md` — arquitectura objetivo.
- `docs/DEV_LOG.md` — bitácora de desarrollo (la vas rellenando tú).
