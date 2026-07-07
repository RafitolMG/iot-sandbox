#!/usr/bin/env bash
# ============================================================================
# build_rootfs.sh — Construye kernel + rootfs ARM de la sandbox (IoT TFM, CP-2)
# ============================================================================
# Estrategia PRIMARIA (ADR-013 / ADR-016): Buildroot 2024.02 LTS con el defconfig
# oficial `qemu_arm_vexpress_defconfig` (maquina vexpress-a9, Cortex-A9 / ARMv7-A)
# + fragmento `buildroot/telemetry.fragment` (strace, tcpdump, inotify-tools) +
# un rootfs-overlay con el binario benigno de prueba y /sbin/telemetry_init.
#
# TODO ocurre dentro del contenedor `iot-sandbox/emulation:dev` (Debian 13 +
# QEMU 10 + toolchain), de forma reproducible y SIN mutar el host ni requerir sudo.
# El script se auto-reejecuta dentro del contenedor (guarda IN_SANDBOX).
#
# Uso:   emulation/arm/build_rootfs.sh
# Salida (gitignored):  emulation/arm/_build/images/{zImage,*.dtb,rootfs.ext2}
# ============================================================================
set -euo pipefail

BR_VERSION="2024.02.11"                       # Buildroot LTS (ADR-013)
IMAGE="iot-sandbox/emulation:dev"

# ---------------------------------------------------------------------------
# Fase 0 (HOST): construir la imagen y reejecutar este script dentro de ella.
# ---------------------------------------------------------------------------
if [ -z "${IN_SANDBOX:-}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
    echo "[build_rootfs] construyendo imagen $IMAGE ..."
    docker build -t "$IMAGE" -f "$REPO/docker/emulation.Dockerfile" "$REPO"
    echo "[build_rootfs] entrando al contenedor para construir el rootfs ..."
    exec docker run --rm -u 1000:1000 -e IN_SANDBOX=1 \
        -v "$REPO":/project -w /project "$IMAGE" \
        bash emulation/arm/build_rootfs.sh "$@"
fi

# ---------------------------------------------------------------------------
# Fase 1..4 (DENTRO del contenedor)
# ---------------------------------------------------------------------------
ARM="/project/emulation/arm"
BUILD="$ARM/_build"
OVERLAY="$ARM/overlay"
mkdir -p "$BUILD/dl"
export BR2_DL_DIR="$BUILD/dl"                 # cache de descargas persistente (reproducibilidad)

echo "== [1/4] compilando el binario ARM benigno de prueba (estatico, armv7 hard-float) =="
arm-linux-gnueabihf-gcc -static -O2 \
    -march=armv7-a -mfpu=vfpv3-d16 -mfloat-abi=hard \
    -o "$OVERLAY/opt/sample/test_sample" "$ARM/testbin/test_sample.c"
chmod 0755 "$OVERLAY/opt/sample/test_sample"
file "$OVERLAY/opt/sample/test_sample"

echo "== [2/4] obteniendo Buildroot $BR_VERSION =="
BR_DIR="$BUILD/buildroot-$BR_VERSION"
if [ ! -d "$BR_DIR" ]; then
    TARBALL="$BUILD/buildroot-$BR_VERSION.tar.xz"
    [ -f "$TARBALL" ] || curl -fL -o "$TARBALL" \
        "https://buildroot.org/downloads/buildroot-$BR_VERSION.tar.xz"
    tar -C "$BUILD" -xf "$TARBALL"
fi
cd "$BR_DIR"

echo "== [3/4] configurando (qemu_arm_vexpress_defconfig + telemetry.fragment) =="
if [ ! -f .config ]; then
    make qemu_arm_vexpress_defconfig
    cat "$ARM/buildroot/telemetry.fragment" >> .config
    make olddefconfig
fi

echo "== [4/4] make -j$(nproc) (toolchain + kernel + rootfs; puede tardar) =="
time make -j"$(nproc)"

echo "== copiando imagenes a $BUILD/images =="
mkdir -p "$BUILD/images"
cp -v output/images/zImage           "$BUILD/images/"
cp -v output/images/*.dtb            "$BUILD/images/"
cp -v output/images/rootfs.ext2      "$BUILD/images/"

echo
echo "[build_rootfs] OK. Config ARM efectiva:"
grep -E '^(BR2_arm|BR2_cortex_a9|BR2_ARM_EABI|BR2_ARM_FPU|BR2_TOOLCHAIN_BUILDROOT_(GLIBC|UCLIBC|MUSL)|BR2_ARM_INSTRUCTIONS)' .config || true
echo "[build_rootfs] Imagenes listas en $BUILD/images"
