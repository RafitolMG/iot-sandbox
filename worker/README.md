# worker/ — Worker de análisis (Celery + QEMU)

Worker **Celery** que desacopla la ejecución lenta del ciclo request/response.
Orquesta una ejecución de **QEMU full-system** por muestra: prepara el rootfs, arranca
la VM de la ISA correspondiente, inyecta el binario, lo ejecuta con telemetría
(strace, tcpdump, inotify) y recoge/parses los artefactos para extraer IoCs.

**Estado (CP-0):** andamiaje. La implementación empieza en:
- **CP-1** — arranque del worker Celery + tarea `ping` de prueba.
- **CP-2** — arranque de QEMU full-system ARM y captura de los tres artefactos.
- **CP-3** — parseo de artefactos → extracción de IoCs → persistencia en PostgreSQL.

**Seguridad:** la muestra se trata como NO confiable (sin FS del host, red del invitado
aislada/simulada, sin credenciales). La emulación cross-ISA usa TCG (sin KVM), así que
el worker no requiere privilegios elevados. Ver §6 de `docs/PROJECT_BRIEF.md`.

Imagen base: `docker/worker.Dockerfile` (ver ADR-008 / ADR-012 en `docs/DECISIONS.md`).
