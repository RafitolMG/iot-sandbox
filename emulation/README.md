# emulation/ — Registro de perfiles y scripts de QEMU por ISA

Capa de emulación **multi-arquitectura** (CP-6). En lugar de duplicar scripts por ISA, se
usa un **registro de perfiles** (ADR-020): dos scripts genéricos dirigidos por un fichero de
perfil que declara, para cada arquitectura, su máquina QEMU, kernel, rootfs, binario QEMU y
toolchain. La ISA se pasa como argumento.

```
emulation/
├── build_rootfs.sh          # GENÉRICO: build_rootfs.sh <arch>  (Buildroot: kernel+rootfs+binario)
├── run_emulation.sh         # GENÉRICO: run_emulation.sh <arch> [OUTDIR] [TIMEOUT]  (detona + recoge)
├── profiles/                # ← EL REGISTRO (un entry por ISA)
│   ├── arm.env              #   ARM Cortex-A9 / ARMv7-A hard-float (vexpress-a9)
│   ├── mips.env             #   MIPS32r2 big-endian (malta)
│   ├── mipsel.env           #   MIPS32r2 little-endian (malta)
│   └── x86_64.env           #   x86-64 (pc / virtio)
├── common/                  # ← COMPARTIDO por todas las ISAs (sin duplicar)
│   ├── overlay/sbin/telemetry_init   # PID 1 del invitado: orquesta sondas + muestra + apagado
│   ├── testbin/test_sample.c         # binario BENIGNO de prueba (C portable) — ADR-005
│   └── telemetry.fragment            # añadidos de Buildroot (strace/tcpdump/inotify + ext2)
└── <arch>/_build/           # árbol de build + imágenes + artefactos por ISA (gitignored)
    ├── images/{<kernel>,*.dtb?,rootfs.ext2}
    └── sample-overlay/opt/sample/test_sample   # binario compilado para ESA ISA
```

Los binarios pesados (kernels, rootfs, imágenes) **no se versionan** (`.gitignore`); se
generan de forma reproducible con Buildroot 2024.02.11 LTS (ADR-013/016). La cache de
descargas de Buildroot es **compartida** entre ISAs (`emulation/_dl/`).

## El registro de perfiles (ADR-020)

Cada `profiles/<arch>.env` declara las variables `P_*` que consumen los dos scripts:

| Variable | Qué declara | arm | mips | x86_64 |
|----------|-------------|-----|------|--------|
| `P_BR_DEFCONFIG` | defconfig de Buildroot | `qemu_arm_vexpress_defconfig` | `qemu_mips32r2_malta_defconfig` | `qemu_x86_64_defconfig` |
| `P_CROSS_CC` (+`P_CFLAGS`) | toolchain del binario de prueba | `arm-linux-gnueabihf-gcc` | `mips-linux-gnu-gcc` | `x86_64-linux-gnu-gcc` |
| `P_QEMU_BIN` / `P_QEMU_MACHINE` | binario y placa QEMU | `qemu-system-arm` / `vexpress-a9` | `qemu-system-mips` / `malta` | `qemu-system-x86_64` / `pc` |
| `P_KERNEL_IMAGE` / `P_DTB` | kernel y DTB | `zImage` / `vexpress-v2p-ca9.dtb` | `vmlinux` / — | `bzImage` / — |
| `P_DISK_IF` / `P_ROOT_DEV` | disco y raíz | `sd` / `/dev/mmcblk0` | `ide` / `/dev/sda` | `virtio` / `/dev/vda` |
| `P_CONSOLE` / `P_NIC_MODEL` | consola serie y NIC | `ttyAMA0` / `lan9118` | `ttyS0` / `pcnet` | `ttyS0` / `virtio` |
| `P_ELF_MACHINE` / `P_ELF_DATA` | mapeo de autodetección ELF | 40 / LSB | 8 / MSB | 62 / LSB |

Añadir una ISA nueva = **añadir un `profiles/<arch>.env`** (los defconfig/máquinas de otras
placas QEMU están documentados en `board/qemu/*/readme.txt` de Buildroot). No se tocan los scripts.

## Los tres artefactos del análisis dinámico

| Artefacto | Sonda (dentro del invitado) | Qué captura |
|-----------|-----------------------------|-------------|
| `strace.log`     | `strace -f -tt -T` sobre la muestra | syscalls del binario |
| `capture.pcap`   | `tcpdump -i any -U`                 | tráfico de red (intento de C2) |
| `fs_events.log`  | `inotifywait -m -r`                 | cambios en `/tmp` `/etc` `/root` |

## Uso (ejecutable a mano)

```bash
# 1) Construir kernel + rootfs + binario de prueba de una ISA (Buildroot; ~15-25 min).
emulation/build_rootfs.sh mips
#    -> emulation/mips/_build/images/{vmlinux,rootfs.ext2}

# 2) Detonar el binario benigno y recoger los 3 artefactos.
emulation/run_emulation.sh mips
#    -> emulation/mips/_build/artifacts/{strace.log,capture.pcap,fs_events.log}
```

Todo corre dentro del contenedor `iot-sandbox/emulation:dev` (Debian 13 + QEMU 10.0.8 +
toolchains), sin mutar el host ni requerir `sudo`. Los scripts se auto-reejecutan dentro del
contenedor (guarda `IN_SANDBOX`). La cross-arquitectura usa **TCG** (sin KVM), así que no se
requieren privilegios elevados.

> **Rebuild limpio de ARM:** el kernel+rootfs ARM de CP-2 (`emulation/arm/_build/images/`) se
> reutiliza tal cual. Para reconstruirlo desde cero con el layout nuevo (overlay común +
> sample-overlay): `rm -rf emulation/arm/_build && emulation/build_rootfs.sh arm`.

## Aislamiento y seguridad (ADR-004 / ADR-005)

- La muestra se ejecuta **siempre dentro del invitado QEMU**, nunca en el host.
- En el MVP solo se usa el **binario benigno** de prueba. Malware real: fase de evaluación
  (CP-7), siempre en este invitado.
- **Red:** SLIRP de QEMU (10.0.2.0/24). Por defecto se deja salir el *intento* de red para
  GARANTIZAR su captura (el binario contacta IPs/dominios de documentación RFC5737/RFC2606,
  no infraestructura real). Aislamiento pleno (`restrict=on` / INetSim) es CP-5; activable con
  `SANDBOX_NET_RESTRICT=1 emulation/run_emulation.sh <arch>`.
- **Extracción de artefactos:** los escribe el invitado en `/telemetry` (en el propio rootfs)
  y el host los lee con `debugfs` **sin montar** la imagen (sin privilegios).
- **Apagado limpio:** el invitado hace `reboot -f` con QEMU `-no-reboot` (sale solo); además
  `run_emulation.sh` impone un timeout de seguridad. No quedan procesos colgando.

## Integración con el worker (CP-3 / CP-6)

La tarea Celery `analyze` (en `worker/celery_app.py`) lee la `arch` de la muestra y lanza la
emulación vía **Docker-out-of-Docker** (ADR-017): arranca `iot-sandbox/emulation:dev` por el
socket de Docker y ejecuta `run_emulation.sh <arch>` dentro. La `arch` la fija la API por
**autodetección de la cabecera ELF** o de forma explícita (ADR-021). La muestra subida (NO
confiable) se pasa en `SAMPLE_BIN` y se **inyecta** en el rootfs con `debugfs -w` (sin montar),
sustituyendo `/opt/sample/test_sample`; solo se ejecuta después dentro de QEMU. Los 3 artefactos
se parsean (strace/fs por regex, pcap con scapy) y se extraen IoCs que se persisten en PostgreSQL.
