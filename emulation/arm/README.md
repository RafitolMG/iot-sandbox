# emulation/arm/ — Núcleo de emulación ARM (CP-2)

Primera (y única, en el MVP) arquitectura soportada. **Implementado en CP-2.**

Arranca **QEMU full-system ARM** con un kernel + rootfs mínimos (Buildroot), inyecta un
**binario ARM benigno de prueba**, lo ejecuta bajo telemetría y recoge en el host los
**tres artefactos** del análisis dinámico:

| Artefacto | Sonda (dentro del invitado) | Qué captura |
|-----------|-----------------------------|-------------|
| `strace.log`     | `strace -f -tt -T` sobre la muestra | syscalls del binario |
| `capture.pcap`   | `tcpdump -i any -U`                 | tráfico de red (intento de C2) |
| `fs_events.log`  | `inotifywait -m -r`                 | cambios en `/tmp` `/etc` `/root` |

## Par máquina / kernel / ISA (cierra ADR-013)

- **QEMU:** `qemu-system-arm` **10.0.8** (Debian 13 «trixie» vía apt; ADR-012 proponía 9.2,
  trixie ya trae 10.0 → corregido en ADR-016).
- **Máquina:** `-M vexpress-a9` (ARM Versatile Express, **Cortex-A9 / ARMv7-A**).
- **Kernel + rootfs:** generados con **Buildroot 2024.02.11 LTS**, defconfig oficial
  `qemu_arm_vexpress_defconfig` + `buildroot/telemetry.fragment` (añade strace, tcpdump,
  inotify-tools y un rootfs-overlay). Kernel `zImage` + `vexpress-v2p-ca9.dtb`, rootfs
  `rootfs.ext2` (tarjeta SD → `/dev/mmcblk0`).
- **ISA / toolchain del invitado:** ARMv7-A EABI (los valores exactos de float/libc los
  imprime `build_rootfs.sh` al final, leídos del `.config` generado).
- **Binario de prueba:** compilado aparte con `arm-linux-gnueabihf-gcc -static` (ARMv7-A
  hard-float); al ser estático corre en el invitado con independencia de su libc.

## Ficheros

```
emulation/arm/
├── build_rootfs.sh        # construye imagen Docker + kernel/rootfs (Buildroot) + binario
├── run_emulation.sh       # arranca QEMU, ejecuta la muestra, extrae y verifica artefactos
├── testbin/test_sample.c  # binario ARM BENIGNO de prueba (syscalls + /tmp + red) — ADR-005
├── overlay/               # rootfs-overlay de Buildroot
│   ├── sbin/telemetry_init #   PID 1 del invitado: orquesta sondas + muestra + apagado
│   └── opt/sample/         #   (aquí se inyecta test_sample compilado; gitignored)
├── buildroot/telemetry.fragment  # añadidos al defconfig (paquetes + overlay + tamaño)
└── _build/                # árbol de build + imágenes + artefactos (gitignored)
```

## Uso (ejecutable a mano)

```bash
# 1) Construir kernel + rootfs + binario de prueba (Buildroot; primera vez tarda).
emulation/arm/build_rootfs.sh
#    -> emulation/arm/_build/images/{zImage,vexpress-v2p-ca9.dtb,rootfs.ext2}

# 2) Detonar el binario benigno y recoger los 3 artefactos.
emulation/arm/run_emulation.sh
#    -> emulation/arm/_build/artifacts/{strace.log,capture.pcap,fs_events.log}
```

Todo corre dentro del contenedor `iot-sandbox/emulation:dev` (Debian 13 + QEMU 10 +
toolchain), sin mutar el host ni requerir `sudo`. Los scripts se auto-reejecutan dentro
del contenedor (guarda `IN_SANDBOX`). La cross-arquitectura usa **TCG** (sin KVM), así
que no se requieren privilegios elevados.

## Aislamiento y seguridad (ADR-004 / ADR-005)

- La muestra se ejecuta **siempre dentro del invitado QEMU**, nunca en el host.
- En el MVP solo se usa el **binario benigno** de prueba. Malware real: fase de
  evaluación (CP-7), siempre en este invitado.
- **Red (CP-2):** SLIRP de QEMU (10.0.2.0/24). Por defecto se deja salir el *intento* de
  red para GARANTIZAR su captura en el pcap (el binario contacta IPs/dominios de
  documentación RFC5737/RFC2606, no infraestructura real). El aislamiento pleno de red
  (`restrict=on` / INetSim) es **CP-5**; se puede activar ya con
  `SANDBOX_NET_RESTRICT=1 emulation/arm/run_emulation.sh`.
- **Extracción de artefactos:** los escribe el invitado en `/telemetry` (en el propio
  rootfs) y el host los lee con `debugfs` **sin montar** la imagen (sin privilegios).
- **Apagado limpio:** el invitado hace `reboot -f` con QEMU `-no-reboot` (sale solo);
  además `run_emulation.sh` impone un timeout de seguridad. No quedan procesos colgando.

## Integración con el worker (CP-3)

La tarea Celery `analyze` (en `worker/celery_app.py`) lanza esta emulación vía
**Docker-out-of-Docker** (ADR-017): el worker arranca `iot-sandbox/emulation:dev` por el
socket de Docker y ejecuta `run_emulation.sh` dentro. La muestra subida (NO confiable) se
pasa en `SAMPLE_BIN` y se **inyecta** en el rootfs con `debugfs -w` (sin montar),
sustituyendo `/opt/sample/test_sample`; solo se ejecuta después dentro de QEMU. Los 3
artefactos se parsean (strace/fs por regex, pcap con scapy) y se extraen IoCs que se
persisten en PostgreSQL. El binario de prueba horneado sigue usándose si `SAMPLE_BIN` no
está definido (ejecución manual de CP-2).
