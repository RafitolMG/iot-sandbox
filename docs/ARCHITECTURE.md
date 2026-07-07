# ARCHITECTURE — Arquitectura objetivo

> Vista de la arquitectura destino. Coherente con §2.3 y §3.3.3 del TFM.

## Diagrama lógico

```
                          ┌──────────────────────────────────────────────┐
                          │            Servidor Host (rafa-desktop)        │
                          │                                                │
   navegador ──HTTP──▶  ┌─┴──────────────┐   ┌──────────────┐            │
   (analista)           │  Frontend       │   │  PostgreSQL  │            │
                        │  Vue 3 + Vite   │   │  (metadatos, │            │
                        └───────┬─────────┘   │  IoCs, logs) │            │
                                │ REST        └──────▲───────┘            │
                        ┌───────▼─────────┐          │                    │
                        │  API FastAPI    │──────────┘                    │
                        │  (async)        │                               │
                        └───────┬─────────┘                               │
                                │ encola                                  │
                        ┌───────▼─────────┐   ┌──────────────┐            │
                        │  Redis (broker) │◀─▶│ Celery worker│            │
                        └─────────────────┘   └──────┬───────┘            │
                                                     │ lanza              │
                          ┌──────────────────────────▼─────────────────┐ │
                          │  QEMU full-system (ARM/MIPS/...)            │ │
                          │  ┌──────────────────────────────────────┐  │ │
                          │  │ rootfs mínimo + muestra (no confiable)│  │ │
                          │  │ telemetría: strace · tcpdump · inotify│  │ │
                          │  └──────────────────────────────────────┘  │ │
                          │        red simulada (INetSim) ─ aislada     │ │
                          └────────────────────────────────────────────┘ │
                          │        (todo salvo QEMU en Docker Compose)   │
                          └──────────────────────────────────────────────┘
```

## Componentes

- **Frontend (Vue 3 + Vite):** subir muestra, ver estado, ver reporte forense (syscalls, red, FS, IoCs).
- **API (FastAPI):** recibe binarios, valida, encola, expone reportes. Contrato REST versionado.
- **Broker (Redis) + Celery:** desacopla la ejecución lenta del ciclo request/response.
- **Worker (Celery):** orquesta una ejecución QEMU por muestra; recoge y parsea artefactos.
- **Emulación (QEMU full-system):** aísla la muestra a nivel de hardware. Un perfil por ISA.
- **INetSim:** responde DNS/HTTP falsos para derrotar la evasión por desconexión.
- **PostgreSQL:** modelo relacional muestra → (syscalls, flujos de red, cambios FS, IoCs).

## Flujo de datos (una muestra)

1. Analista sube binario → `POST /samples` → se guarda el fichero y un registro `sample(status=queued)`.
2. API encola `analyze(sample_id)` en Celery.
3. Worker prepara el rootfs, arranca QEMU-ISA, inyecta la muestra, la ejecuta con telemetría.
4. Worker recoge `strace.log`, `capture.pcap`, `fs_events.log`.
5. Parser extrae IoCs (IPs, dominios, puertos, ficheros, syscalls relevantes).
6. Se persiste todo; `sample.status=done`.
7. Frontend consulta `GET /samples/{id}` y renderiza el reporte.

## Modelo de datos (borrador, se afina en CP-3)

- `sample` (id, filename, sha256, arch, status, created_at, finished_at)
- `syscall_event` (id, sample_id, ts, name, args)
- `network_flow` (id, sample_id, proto, src, dst, dport, bytes)
- `fs_event` (id, sample_id, op, path)
- `ioc` (id, sample_id, type[ip|domain|file|port|hash], value)
