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

**CP-0 — Kickoff y andamiaje (hecho).** Este repositorio contiene, por ahora, solo la
**estructura del monorepo, la documentación de gobierno y un `docker-compose.yml`
esqueleto**. Todavía **no hay lógica de negocio**: la infraestructura ejecutable llega
en CP-1. Ver el estado de los checkpoints en [`docs/CHECKPOINTS.md`](docs/CHECKPOINTS.md)
y la bitácora en [`docs/DEV_LOG.md`](docs/DEV_LOG.md).

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

## Cómo se levantará (a partir de CP-1)

```bash
cp .env.example .env      # ajustar credenciales locales
docker compose up --build
```

Servicios y puertos declarados en `docker-compose.yml`:

| Servicio  | Tecnología             | Puerto host |
|-----------|------------------------|-------------|
| api       | FastAPI (Python 3.12)  | 8000        |
| frontend  | Vue 3 + Vite           | 5173        |
| db        | PostgreSQL             | 5432        |
| redis     | Redis (broker Celery)  | 6379        |
| worker    | Celery + QEMU          | —           |

> En CP-0 los servicios apuntan a Dockerfiles/imágenes base **placeholder**. No ejecutes
> `docker compose up` todavía: no hará nada útil hasta CP-1.

## Estructura del repositorio

```
iot-sandbox/
├── backend/            # API REST (FastAPI, Python 3.12)          [andamiaje]
├── worker/             # Celery worker + orquestación de QEMU     [andamiaje]
├── frontend/           # SPA Vue 3 + Vite                         [andamiaje]
├── emulation/          # Perfiles y scripts QEMU por ISA
│   └── arm/            #   ARM primero (MVP)                      [andamiaje]
├── docker/             # Dockerfiles de los servicios             [placeholder]
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
