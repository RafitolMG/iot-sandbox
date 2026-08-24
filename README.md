# IoT Malware Dynamic Analysis Sandbox

Sandbox de **análisis dinámico de malware IoT multi-arquitectura**. Ejecuta binarios
(ARM primero; luego MIPS/MIPSEL/x86_64) dentro de **QEMU full-system**, captura su
comportamiento en tiempo real (syscalls, red, sistema de ficheros) y extrae
**Indicadores de Compromiso (IoCs)**. Todo se opera desde una interfaz web y se
despliega con **Docker Compose**.

> Contribución práctica de un Trabajo Fin de Máster (TFM) en Ciberseguridad (UNIR):
> *"Diseño e implementación de un sistema automatizado de análisis dinámico de malware
> para entornos IoT multi-arquitectura"*.

## Estado

**🏁 Hito 1 — MVP end-to-end (ARM) COMPLETO (CP-0 → CP-4).** Flujo completo operativo:
subir un binario ARM desde la web → detonación en QEMU full-system → captura de telemetría
(syscalls / red / ficheros) → extracción de IoCs → persistencia → **reporte forense en el
navegador**. Todo se levanta con `docker compose up`. Ver el estado de los checkpoints en
[`docs/CHECKPOINTS.md`](docs/CHECKPOINTS.md) y la bitácora en [`docs/DEV_LOG.md`](docs/DEV_LOG.md).

Fuera del MVP (siguientes hitos): CP-5 anti-evasión (INetSim), CP-6 multi-arquitectura
(MIPS/MIPSEL/x86_64), CP-7 evaluación con malware real.

## Aviso de seguridad

Se manejan binarios maliciosos reales. **Durante el desarrollo del MVP NO se ejecuta
malware real**: la tubería se valida con un binario ARM benigno de prueba. El malware
real solo se detona en la fase de evaluación, **siempre dentro de QEMU full-system,
nunca en el host**. Ver §6 de [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md).

## Arquitectura (resumen)

```
navegador ─▶ Frontend (Vue 3) ─▶ API (FastAPI) ─┬─▶ PostgreSQL
                                                 └─▶ Redis ─▶ Celery worker ─▶ QEMU full-system
                                                                                (rootfs mínimo + telemetría)
```

Detalle en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Cómo se levanta

```bash
cp .env.example .env      # ajustar credenciales locales (opcional; hay defaults)
docker compose up --build # levanta db, valkey, api, worker y frontend
```

Cuando los 5 servicios estén `healthy` (`docker compose ps`), **abre la web en
http://localhost:5173**: sube el binario benigno de prueba
(`emulation/arm/overlay/opt/sample/test_sample`, arch ARM), obsérvalo pasar de *En cola* →
*Analizando* → *Completado* (auto-refresco) y pincha en la muestra para ver el reporte forense
(cabecera + contadores + IoCs + pestañas Red/Syscalls/Ficheros).

> La primera detonación requiere la imagen de emulación `iot-sandbox/emulation:dev` y los
> artefactos de kernel/rootfs (`emulation/arm/_build/images/`), generados en CP-2 con
> `emulation/arm/build_rootfs.sh`.

Servicios y puertos declarados en `docker-compose.yml`:

| Servicio  | Tecnología                        | Puerto host |
|-----------|-----------------------------------|-------------|
| frontend  | Vue 3 + Vite (servida por nginx)  | 5173        |
| api       | FastAPI (Python 3.12)             | 8000        |
| db        | PostgreSQL 16                     | 5432        |
| valkey    | Valkey 8 (broker Celery, BSD)     | 6379        |
| worker    | Celery + QEMU (DooD)              | —           |
| inetsim   | INetSim 1.3.2 (servicios simulados) | —         |
| simdns    | dnsmasq (DNS comodín)             | —           |

El frontend (nginx) reverse-proxya `/api` → `api:8000`, así que el navegador solo usa el
puerto **5173** (SPA *same-origin*, sin CORS).

`inetsim` y `simdns` no publican puertos al host: viven en la red `sandbox_sim`
(`internal: true`), donde se detona la muestra y desde donde **no hay salida a Internet**.
Todo el tráfico del invitado se redirige a ellos, de modo que el binario ve conectividad
mientras el pcap conserva la IP y el puerto reales que pidió (CP-5, ADR-022).

## Estructura del repositorio

```
iot-sandbox/
├── backend/            # API REST (FastAPI, Python 3.12)          [CP-1/CP-3 ✅]
├── worker/             # Celery worker + orquestación de QEMU     [CP-2/CP-3 ✅]
├── frontend/           # SPA Vue 3 + Vite                         [CP-4 ✅]
├── emulation/          # Perfiles y scripts QEMU por ISA
│   └── arm/            #   ARM primero (MVP)                      [CP-2 ✅]
├── docker/             # Dockerfiles de los servicios             [✅]
├── docs/               # Documentación de gobierno del proyecto
│   ├── PROJECT_BRIEF.md   # el encargo (fuente de verdad)
│   ├── DECISIONS.md       # registro de decisiones (ADR)
│   ├── ARCHITECTURE.md    # arquitectura objetivo
│   ├── ROADMAP.md         # hitos
│   ├── CHECKPOINTS.md     # protocolo de paradas
│   └── DEV_LOG.md         # bitácora de desarrollo
├── docker-compose.yml  # orquestación (esqueleto en CP-0)
├── .env.example        # plantilla de variables de entorno (sin secretos)
└── .gitignore
```

## Stack

Python 3.12 + FastAPI · Celery + Redis · PostgreSQL · QEMU full-system · Vue 3 + Vite ·
Docker Compose · strace / tcpdump / inotify-tools. Versiones exactas propuestas en
[`docs/DECISIONS.md`](docs/DECISIONS.md) (ADR-007 en adelante).
