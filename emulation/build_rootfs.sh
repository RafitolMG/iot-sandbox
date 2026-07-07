#!/usr/bin/env bash
# ============================================================================
# build_rootfs.sh — Construye kernel + rootfs de la sandbox para UNA ISA (CP-6)
# ============================================================================
# Script GENÉRICO dirigido por el registro de perfiles (ADR-020): recibe la ISA como
# argumento, carga emulation/profiles/<arch>.env y construye con Buildroot el kernel +
# rootfs de esa arquitectura, más el binario benigno de prueba cross-compilado estático.
#
# Reutiliza el patrón de ARM (ADR-013/016) sin duplicar scripts:
#   - overlay COMPARTIDO (emulation/common/overlay) -> /sbin/telemetry_init.
#   - sample-overlay POR ISA (_build/sample-overlay) -> /opt/sample/test_sample.
#   - fragmento de Buildroot COMPARTIDO (emulation/common/telemetry.fragment).
#
# TODO ocurre dentro del contenedor `iot-sandbox/emulation:dev` (Debian 13 + QEMU +
# toolchains), reproducible y SIN mutar el host ni requerir sudo. El script se
# auto-reejecuta dentro del contenedor (guarda IN_SANDBOX).
#
# Uso:    emulation/build_rootfs.sh <arch>            # arm | mips | mipsel | x86_64
# Salida (gitignored):  emulation/<arch>/_build/images/{<kernel>,*.dtb?,rootfs.ext2}
# ============================================================================
set -euo pipefail

BR_VERSION="2024.02.11"                       # Buildroot LTS (ADR-013)
IMAGE="iot-sandbox/emulation:dev"
ARCH="${1:?uso: build_rootfs.sh <arch>  (arm|mips|mipsel|x86_64)}"

# ---------------------------------------------------------------------------
# Fase 0 (HOST): construir la imagen y reejecutar este script dentro de ella.
# ---------------------------------------------------------------------------
if [ -z "${IN_SANDBOX:-}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
    echo "[build_rootfs] construyendo imagen $IMAGE ..."
    docker build -t "$IMAGE" -f "$REPO/docker/emulation.Dockerfile" "$REPO"
    echo "[build_rootfs] entrando al contenedor para construir el rootfs $ARCH ..."
    exec docker run --rm -u 1000:1000 -e IN_SANDBOX=1 \
        -v "$REPO":/project -w /project "$IMAGE" \
        bash emulation/build_rootfs.sh "$ARCH"
fi

# ---------------------------------------------------------------------------
# Fase 1..4 (DENTRO del contenedor)
# ---------------------------------------------------------------------------
EMU="/project/emulation"
PROFILE="$EMU/profiles/$ARCH.env"
[ -f "$PROFILE" ] || { echo "ERROR: no existe el perfil $PROFILE (ISA sin registro)"; exit 1; }
# shellcheck disable=SC1090
. "$PROFILE"

BUILD="$EMU/$ARCH/_build"
DL="$EMU/_dl"                                 # cache de descargas COMPARTIDA entre ISAs
SAMPLE_OVERLAY="$BUILD/sample-overlay"
mkdir -p "$DL" "$SAMPLE_OVERLAY/opt/sample" "$BUILD"
export BR2_DL_DIR="$DL"

echo "== [1/4] cross-compilando el binario benigno de prueba ($P_ARCH, estatico) =="
# shellcheck disable=SC2086
"$P_CROSS_CC" -static -O2 $P_CFLAGS \
    -o "$SAMPLE_OVERLAY/opt/sample/test_sample" "$EMU/common/testbin/test_sample.c"
chmod 0755 "$SAMPLE_OVERLAY/opt/sample/test_sample"
file "$SAMPLE_OVERLAY/opt/sample/test_sample"

echo "== [2/4] obteniendo Buildroot $BR_VERSION =="
BR_DIR="$BUILD/buildroot-$BR_VERSION"
if [ ! -d "$BR_DIR" ]; then
    TARBALL="$BUILD/buildroot-$BR_VERSION.tar.xz"
    [ -f "$TARBALL" ] || curl -fL -o "$TARBALL" \
        "https://buildroot.org/downloads/buildroot-$BR_VERSION.tar.xz"
    tar -C "$BUILD" -xf "$TARBALL"
fi
cd "$BR_DIR"

echo "== [3/4] configurando ($P_BR_DEFCONFIG + telemetry.fragment + overlays) =="
if [ ! -f .config ]; then
    make "$P_BR_DEFCONFIG"
    cat "$EMU/common/telemetry.fragment" >> .config
    # Overlays de rootfs (rutas ABSOLUTAS dentro del contenedor; el repo se monta en /project):
    #   1) overlay COMPARTIDO  -> /sbin/telemetry_init
    #   2) sample-overlay ISA  -> /opt/sample/test_sample (binario recien compilado)
    printf 'BR2_ROOTFS_OVERLAY="%s %s"\n' \
        "/project/emulation/common/overlay" \
        "/project/emulation/$ARCH/_build/sample-overlay" >> .config
    make olddefconfig
fi

echo "== [4/4] make -j$(nproc) (toolchain + kernel + rootfs; puede tardar ~15-25 min) =="
time make -j"$(nproc)"

echo "== copiando imagenes a $BUILD/images =="
mkdir -p "$BUILD/images"
cp -v "output/images/$P_KERNEL_IMAGE" "$BUILD/images/"
if [ -n "$P_DTB" ]; then cp -v output/images/*.dtb "$BUILD/images/"; fi
cp -v output/images/rootfs.ext2 "$BUILD/images/"

echo
echo "[build_rootfs] OK. Perfil $ARCH ($P_DESC):"
echo "  qemu=$P_QEMU_BIN machine=$P_QEMU_MACHINE kernel=$P_KERNEL_IMAGE root=$P_ROOT_DEV nic=$P_NIC_MODEL"
echo "[build_rootfs] Imagenes listas en $BUILD/images"
