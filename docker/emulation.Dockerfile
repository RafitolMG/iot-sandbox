# docker/emulation.Dockerfile — Imagen de construcción + ejecución de la sandbox ARM (CP-2)
#
# Contiene TODO lo necesario, de forma reproducible y SIN mutar el host, para:
#   1. Construir el rootfs+kernel ARM con Buildroot (toolchain interno, kernel, paquetes).
#   2. Compilar el binario ARM benigno de prueba (cross-compiler gnueabihf, estático).
#   3. Arrancar QEMU full-system ARM y recoger/verificar los 3 artefactos.
#
# Base: Debian 13 "trixie" (misma familia que el worker, ADR-008). QEMU vía apt = 10.0.x
# (ADR-012 proponía 9.2; trixie ya empaqueta 10.0.8, se documenta la corrección en ADR-016).
FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive

# tshark/wireshark: no instalar dumpcap con setuid (no lo necesitamos, solo leemos pcap).
RUN echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections

RUN apt-get update && apt-get install -y --no-install-recommends \
        # --- QEMU full-system ARM (ejecución de la sandbox) ---
        qemu-system-arm qemu-utils \
        # --- Toolchain de compilación del binario de prueba (ARM hard-float, EABI5) ---
        gcc-arm-linux-gnueabihf libc6-dev-armhf-cross \
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
