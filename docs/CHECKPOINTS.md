# CHECKPOINTS — Protocolo de paradas de comunicación

> Define **dónde se detiene el desarrollo** para revisar, decidir y registrar en
> `DECISIONS.md` antes de continuar. Cada checkpoint es una parada de revisión.

## Regla general de parada

Al llegar a un checkpoint:

1. **Parar de programar.**
2. Escribir un **CHECKPOINT REPORT** al final de `docs/DEV_LOG.md` con:
   - Qué se ha construido y cómo verificarlo (comandos concretos).
   - Qué funciona / qué no.
   - **Decisiones abiertas** (las añade también a `DECISIONS.md` como `PROPUESTA`).
   - Riesgos o dudas.
3. **Parar hasta la revisión.** Con el reporte delante se resuelven las decisiones abiertas,
   se actualiza `DECISIONS.md` y se arranca el siguiente tramo.

El desarrollo **también para** —fuera de estos hitos— ante una bifurcación de diseño no
cubierta por `DECISIONS.md`. No se improvisa arquitectura.

---

## Gates del MVP (ARM primero)

### CP-0 · Kickoff y andamiaje
- Crea la estructura de carpetas del repo (`backend/`, `frontend/`, `emulation/`, `worker/`,
  `docker/`, `docs/`), `README.md`, `.gitignore`, `docker-compose.yml` esqueleto (servicios
  declarados, aún sin lógica).
- Propón versiones exactas (imágenes base Docker, versión de QEMU, Node, etc.) en `DECISIONS.md`.
- **PARA.** Revisión de estructura y versiones.

### CP-1 · Infraestructura levanta
- `docker compose up` arranca: API FastAPI (con un `/health`), PostgreSQL, Redis, worker Celery
  (con una tarea `ping` de prueba). Migraciones de BD iniciales.
- Verificable: `curl localhost:8000/health` responde; el worker procesa la tarea `ping`.
- **PARA.** Revisión de infra.

### CP-2 · Núcleo de emulación ARM
- El worker es capaz de arrancar QEMU full-system ARM con un kernel + rootfs mínimo (Buildroot o
  imagen preparada), inyectar un **binario ARM benigno de prueba**, ejecutarlo y recoger:
  - trazas de syscalls (strace),
  - captura de red (tcpdump → PCAP),
  - cambios en el sistema de ficheros (inotify).
- Verificable: script que ejecuta el binario de prueba y deja los tres artefactos en disco.
- **PARA.** Este es el hito técnico más arriesgado. Revisión detallada.

### CP-3 · API + cola + persistencia
- Endpoint `POST /samples` (subir binario) → encola tarea Celery → worker corre CP-2 →
  parsea artefactos → extrae IoCs básicos (IPs, dominios, ficheros tocados, syscalls clave) →
  guarda en PostgreSQL. Endpoint `GET /samples/{id}` devuelve el reporte.
- Verificable: subir el binario de prueba por API y recuperar el reporte con IoCs.
- **PARA.** Revisión del contrato de API y del modelo de datos (importa para el Cap. 4).

### CP-4 · Frontend
- Vue 3: pantalla de subida de muestra + listado + vista de reporte (syscalls, red, ficheros, IoCs).
- Verificable: flujo completo desde el navegador.
- **PARA.** Revisión de UX y del flujo end-to-end del MVP (¡hito MVP completo!).

### CP-5 · Anti-evasión (INetSim)
- Integrar simulación de servicios de red (DNS/HTTP) para que el binario crea tener conectividad.
- **PARA.** Revisión.

### CP-6 · Generalización multi-arquitectura
- Añadir MIPS/MIPSEL/x86_64 (kernel + rootfs + binario QEMU por ISA). Selección de arquitectura
  automática o manual al subir la muestra.
- **PARA.** Revisión.

### CP-7 · Evaluación con malware real
- Con Rafael aportando muestras reales (Mirai/Gafgyt/Mozi), ejecutar en la sandbox y validar
  extracción de IoCs. Recoger métricas para el capítulo de evaluación del TFM.
- **PARA.** Cierre y recogida de resultados para la memoria.

---

## Estado de checkpoints

| CP | Descripción | Estado |
|----|-------------|--------|
| CP-0 | Kickoff y andamiaje | ✅ Hecho (2026-07-07) |
| CP-1 | Infraestructura levanta | ✅ Hecho (2026-07-07) |
| CP-2 | Núcleo emulación ARM | ✅ Hecho (2026-07-07) |
| CP-3 | API + cola + persistencia | ⬜ Pendiente |
| CP-4 | Frontend (MVP completo) | ⬜ Pendiente |
| CP-5 | Anti-evasión INetSim | ⬜ Pendiente |
| CP-6 | Multi-arquitectura | ⬜ Pendiente |
| CP-7 | Evaluación malware real | ⬜ Pendiente |
