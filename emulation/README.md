# emulation/ — Perfiles y scripts de QEMU por ISA

Contiene, **un subdirectorio por arquitectura (ISA)**, todo lo necesario para arrancar
un invitado QEMU full-system aislado donde se detona la muestra con telemetría:

- el kernel invitado,
- el rootfs mínimo (con `strace`, `tcpdump`/`tshark`, `inotify-tools`),
- el perfil/script de invocación de `qemu-system-<arch>`,
- la lógica de inyección de la muestra y recogida de artefactos.

Los binarios pesados (kernels, rootfs, imágenes de disco) **no se versionan** (ver
`.gitignore`); se generan de forma reproducible o se documentan sus fuentes.

## Estado (CP-0)

Solo existe el andamiaje de `arm/` (MVP — ARM primero, ADR-002). La emulación real se
implementa en **CP-2**. Las demás ISAs (MIPS, MIPSEL, x86_64) se añaden en **CP-6**,
replicando la estructura de `arm/` (kernel + rootfs + binario QEMU distintos).

```
emulation/
└── arm/        # perfil ARM (MVP)          [andamiaje CP-0 → implementación CP-2]
    (mips/, mipsel/, x86_64/  llegan en CP-6)
```
