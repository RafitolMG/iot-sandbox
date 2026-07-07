# docker/emulation.Dockerfile — Imagen de construcción + ejecución de la sandbox MULTI-ISA
# (CP-2 ARM · CP-6 MIPS/MIPSEL/x86_64)
#
# Contiene TODO lo necesario, de forma reproducible y SIN mutar el host, para:
#   1. Construir el rootfs+kernel de cada ISA con Buildroot (toolchain interno, kernel, paquetes).
#   2. Cross-compilar el binario benigno de prueba (armhf / mips / mipsel / x86-64, estático).
#   3. Arrancar QEMU full-system (arm/mips/mipsel/x86_64) y recoger/verificar los 3 artefactos.
#
# Registro de perfiles por ISA: emulation/profiles/<arch>.env (ADR-020). Los scripts
# genéricos emulation/{build_rootfs,run_emulation}.sh se ejecutan dentro de esta imagen.
#
# Base: Debian 13 "trixie" (misma familia que el worker, ADR-008). QEMU vía apt = 10.0.x
# (ADR-012 proponía 9.2; trixie ya empaqueta 10.0.8, se documenta la corrección en ADR-016).
FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive

# tshark/wireshark: no instalar dumpcap con setuid (no lo necesitamos, solo leemos pcap).
RUN echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections

RUN apt-get update && apt-get install -y --no-install-recommends \
        # --- QEMU full-system por ISA (ejecución de la sandbox) ---
        #   qemu-system-arm  -> arm/aarch64 ; qemu-system-mips -> mips/mipsel(64) ;
        #   qemu-system-x86  -> x86_64/i386. Versiones de Debian 13 "trixie" (QEMU 10.0.x).
        qemu-system-arm qemu-system-mips qemu-system-x86 qemu-utils \
        # --- Toolchains de compilación del binario de prueba (estático, por ISA) ---
        #   ARM hard-float (EABI5), MIPS o32 big-endian y little-endian. x86-64 = gcc nativo.
        gcc-arm-linux-gnueabihf libc6-dev-armhf-cross \
        gcc-mips-linux-gnu libc6-dev-mips-cross \
        gcc-mipsel-linux-gnu libc6-dev-mipsel-cross \
        # --- Dependencias de build de Buildroot ---
        build-essential gcc g++ make git wget curl ca-certificates \
        cpio unzip rsync bc file python3 libncurses-dev \
        patch perl sed tar xz-utils bzip2 gzip findutils diffutils \
        gawk which locales \
        # --- Manipulación de imágenes ext2/ext4 sin privilegios (mke2fs -d, debugfs) ---
        e2fsprogs \
        # --- Verificación de artefactos (lectura de pcap) ---
        tshark tcpdump \
    && rm -rf /var/lib/apt/lists/*

# Buildroot exige un locale UTF-8 disponible.
RUN sed -i 's/^# *\(en_US.UTF-8\)/\1/' /etc/locale.gen && locale-gen
ENV LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# El build/run se ejecuta como uid 1000 (== usuario rafa en el host) para que los ficheros
# generados en el bind-mount pertenezcan al usuario y Buildroot no proteste por correr como root.
RUN useradd -m -u 1000 -s /bin/bash builder
USER builder
WORKDIR /project

CMD ["bash"]
