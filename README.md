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

Flujo completo operativo: subir un binario desde la web → detección automática de la
arquitectura por cabecera ELF → detonación en QEMU full-system → captura de telemetría
(syscalls / red / ficheros) → extracción de IoCs → persistencia → **reporte forense en el
navegador**. Todo se levanta con `docker compose up`.

Cuatro arquitecturas soportadas (ARM, MIPS, MIPSEL, x86_64), red de detonación aislada con
servicios simulados para que la muestra perciba conectividad sin alcanzar sistemas reales, y
traza opcional en vivo por un segundo puerto serie.

## Aviso de seguridad

Se manejan binarios maliciosos reales. La muestra **siempre se detona dentro de QEMU
full-system, nunca en el host ni en el contenedor que lo lanza**, y sobre una red sin
encaminamiento hacia Internet. El binario nunca se ejecuta, se marca ejecutable ni se abre
fuera del invitado.

## Arquitectura (resumen)

```
navegador ─▶ Frontend (Vue 3) ─▶ API (FastAPI) ─┬─▶ PostgreSQL
                                                 └─▶ Redis ─▶ Celery worker ─▶ QEMU full-system
                                                                                (rootfs mínimo + telemetría)
```

## Cómo se levanta

```bash
cp .env.example .env      # ajustar credenciales locales (opcional; hay defaults)
docker compose up --build # levanta db, valkey, api, worker y frontend
```

Cuando los 5 servicios estén `healthy` (`docker compose ps`), **abre la web en
http://localhost:5173**: sube el binario benigno de prueba
(el binario benigno de `emulation/common/testbin/`, horneado en cada rootfs), obsérvalo pasar de *En cola* →
*Analizando* → *Completado* (auto-refresco) y pincha en la muestra para ver el reporte forense
(cabecera + contadores + IoCs + pestañas Red/Syscalls/Ficheros).

> **Antes de la primera detonación** hay que generar el kernel y el rootfs de cada
> arquitectura: `emulation/build_rootfs.sh <arm|mips|mipsel|x86_64>`. Son artefactos que no
> se versionan (pesan gigas) y su construcción con Buildroot lleva unos 17 minutos por
> arquitectura, una sola vez; varias pueden construirse en paralelo compartiendo la caché de
> descargas. `docker compose up` levanta los servicios sin ellos, pero el análisis fallará
> hasta que existan.

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

## Tests

```bash
docker compose run --rm --no-deps -w /project worker pytest -p no:cacheprovider
```

Cubren los dos módulos de lógica pura —autodetección de ISA por cabecera ELF y parseo de
artefactos con extracción de IoCs—, que son donde han aparecido los defectos reales: bytes
NUL en las trazas, la distinción entre «no es un ELF» y «ELF de arquitectura desconocida», y
qué direcciones son infraestructura del banco de pruebas y no comportamiento de la muestra.
Se ejecutan dentro del contenedor del worker porque es donde están las dependencias.

## Traza en vivo

Por defecto los artefactos se extraen al terminar la detonación. Con `SANDBOX_LIVE_TRACE=1`
el invitado va emitiendo el strace por un segundo puerto serie y el anfitrión lo recibe en
`trace.live` mientras la muestra corre. Ralentiza al invitado, así que **no debe usarse en
tandas de evaluación**: alteraría los recuentos. Detalle en ADR-023.

## Estructura del repositorio

```
iot-sandbox/
├── backend/            # API REST (FastAPI, Python 3.12)          [CP-1/CP-3 ✅]
├── worker/             # Celery worker + orquestación de QEMU     [CP-2/CP-3 ✅]
├── frontend/           # SPA Vue 3 + Vite
├── emulation/          # Perfiles y scripts QEMU por ISA
│   ├── profiles/       #   un .env por arquitectura
│   └── common/         #   init del invitado y binario de prueba
├── docker/             # Dockerfiles de los servicios
├── tests/              # suite de tests (pytest)
├── docker-compose.yml  # orquestación
├── .env.example        # plantilla de variables de entorno (sin secretos)
└── .gitignore
```

## Stack

Python 3.12 + FastAPI · Celery + Valkey 8 · PostgreSQL 16 · QEMU 10 full-system ·
Buildroot · Vue 3 + Vite · nginx · Docker Compose · strace / tcpdump / inotify-tools ·
INetSim + dnsmasq. Todas las versiones fijadas en los Dockerfiles y en `docker-compose.yml`.
