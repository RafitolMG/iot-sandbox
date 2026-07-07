# emulation/arm/ — Perfil de emulación ARM (MVP)

Primera (y única, en el MVP) arquitectura soportada. La implementación real llega en
**CP-2**; este README documenta el **plan** de forma que sirva de referencia.

**Estado (CP-0):** andamiaje. Aún NO hay kernel, rootfs ni scripts ejecutables.

## Plan (a implementar en CP-2 — NO ejecutar todavía)

- **QEMU:** `qemu-system-arm`, full-system (ADR-004, ADR-012).
- **Máquina/CPU:** propuesta `-M virt` (moderna, virtio, flexible) frente a placas
  legacy (`versatilepb`, `vexpress-a9`). Selección definitiva en CP-2 según el rootfs.
- **Kernel + rootfs:** rootfs mínimo generado con Buildroot (ADR-013), con `strace`,
  `tcpdump`/`tshark` e `inotify-tools` incluidos.
- **Telemetría dentro del invitado:**
  - syscalls  → `strace -f -tt -o /telemetry/strace.log <muestra>`
  - red       → `tcpdump -i any -w /telemetry/capture.pcap`
  - ficheros  → `inotifywait`/`inotifywatch` → `/telemetry/fs_events.log`
- **Muestra:** binario ARM **benigno** de prueba durante el MVP (ADR-005). El malware
  real solo en la fase de evaluación (CP-7), siempre dentro de este invitado.
- **Aislamiento:** sin FS del host montado, red del invitado aislada (y simulada con
  INetSim en CP-5), sin credenciales.

## Artefactos esperados (por ejecución)

`strace.log` · `capture.pcap` · `fs_events.log` → recogidos por el worker y parseados
para extraer IoCs (CP-3).
