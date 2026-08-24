#!/usr/bin/env bash
# ============================================================================
# run_emulation.sh — Ejecuta UNA detonacion en la sandbox para UNA ISA (CP-6)
# ============================================================================
# Script GENÉRICO dirigido por el registro de perfiles (ADR-020): recibe la ISA como
# primer argumento, carga emulation/profiles/<arch>.env y arranca QEMU full-system con
# la máquina/kernel/rootfs de ese perfil, ejecuta el binario benigno bajo telemetría (lo
# orquesta /sbin/telemetry_init dentro del invitado) y recoge en el host los TRES
# artefactos:   strace.log · capture.pcap · fs_events.log
#
# La extraccion se hace con `debugfs` (lee ficheros del ext2 SIN montar la imagen, sin
# privilegios). Al terminar, QEMU se apaga solo (el invitado hace reboot -f con
# -no-reboot); ademas hay un timeout de seguridad en el host. Nada queda colgando.
#
# Se auto-reejecuta dentro del contenedor `iot-sandbox/emulation:dev` (QEMU vive ahi).
#
# Uso:    emulation/run_emulation.sh <arch> [OUTDIR] [TIMEOUT_SEG]
# Salida: OUTDIR (por defecto emulation/<arch>/_build/artifacts) con los 3 artefactos.
# ============================================================================
set -euo pipefail

IMAGE="iot-sandbox/emulation:dev"
ARCH="${1:?uso: run_emulation.sh <arch> [OUTDIR] [TIMEOUT]  (arm|mips|mipsel|x86_64)}"
TIMEOUT="${3:-180}"                 # timeout de seguridad del host (s)
# Aislamiento de red. Tres modos, de menos a mas aislado:
#   (por defecto)             SLIRP normal: el egress sale por el contenedor.
#   SANDBOX_NET_RESTRICT=1    SLIRP con restrict=on: el invitado no sale a ningun sitio.
#   SANDBOX_NET_SIM=1         simulacion (CP-5, ADR-022): el egress se redirige a INetSim y
#                             el contenedor va en una red Docker sin salida a Internet.
# NET_SIM manda sobre NET_RESTRICT: con restrict=on el trafico ni siquiera saldria de SLIRP,
# asi que no habria nada que redirigir.
if [ "${SANDBOX_NET_SIM:-0}" = "1" ]; then
    NETOPT="-net user"
elif [ "${SANDBOX_NET_RESTRICT:-0}" = "1" ]; then
    NETOPT="-net user,restrict=on"
else
    NETOPT="-net user"
fi

# ---------------------------------------------------------------------------
# HOST: reejecutar dentro del contenedor de emulacion.
# ---------------------------------------------------------------------------
if [ -z "${IN_SANDBOX:-}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
    OUT_HOST="${2:-$REPO/emulation/$ARCH/_build/artifacts}"
    mkdir -p "$OUT_HOST"
    OUT_IN="/project/${OUT_HOST#$REPO/}"
    exec docker run --rm -u 1000:1000 -e IN_SANDBOX=1 \
        -e SANDBOX_NET_RESTRICT="${SANDBOX_NET_RESTRICT:-0}" \
        -e SANDBOX_NET_SIM="${SANDBOX_NET_SIM:-0}" \
        -e SANDBOX_SIM_IP="${SANDBOX_SIM_IP:-}" \
        -v "$REPO":/project -w /project "$IMAGE" \
        bash emulation/run_emulation.sh "$ARCH" "$OUT_IN" "$TIMEOUT"
fi

# ---------------------------------------------------------------------------
# DENTRO del contenedor
# ---------------------------------------------------------------------------
EMU="/project/emulation"
PROFILE="$EMU/profiles/$ARCH.env"
[ -f "$PROFILE" ] || { echo "ERROR: no existe el perfil $PROFILE (ISA sin registro)"; exit 1; }
# shellcheck disable=SC1090
. "$PROFILE"

IMAGES="$EMU/$ARCH/_build/images"
OUT="${2:-$EMU/$ARCH/_build/artifacts}"
mkdir -p "$OUT"

KERNEL="$IMAGES/$P_KERNEL_IMAGE"
ROOTFS_SRC="$IMAGES/rootfs.ext2"
for f in "$KERNEL" "$ROOTFS_SRC"; do
    [ -f "$f" ] || { echo "ERROR: falta $f — ejecuta 'build_rootfs.sh $ARCH' primero"; exit 1; }
done
DTB_ARG=""
if [ -n "$P_DTB" ]; then
    DTB_PATH="$IMAGES/$P_DTB"
    [ -f "$DTB_PATH" ] || { echo "ERROR: falta el DTB $DTB_PATH"; exit 1; }
    DTB_ARG="-dtb $DTB_PATH"
fi

# Copia de trabajo del rootfs (el invitado escribe los artefactos dentro; no tocamos el pristino).
RUNDIR="$(mktemp -d)"
trap 'kill -KILL "${QEMU_PID:-0}" 2>/dev/null; rm -rf "$RUNDIR"' EXIT
ROOTFS="$RUNDIR/rootfs.ext2"
cp "$ROOTFS_SRC" "$ROOTFS"
# Algunas placas (p.ej. la SD de vexpress-a9) exigen un disco de tamaño potencia de 2;
# el ext2 conserva su tamaño interno y el resto queda sin usar. El resto de ISAs no resiza.
if [ -n "$P_ROOTFS_RESIZE" ]; then
    qemu-img resize -f raw "$ROOTFS" "$P_ROOTFS_RESIZE" >/dev/null
fi

# --- Inyeccion de la muestra (CP-3) --------------------------------------
# Si SAMPLE_BIN apunta a un binario, SUSTITUYE el /opt/sample/test_sample horneado por la
# muestra subida (tratada como NO confiable). Se escribe en el ext2 con `debugfs -w` (sin
# montar la imagen, sin privilegios) y se marca ejecutable+root. La muestra solo se ejecuta
# despues DENTRO de QEMU (nunca en este contenedor ni en el host). Si SAMPLE_BIN no esta
# definido se usa el binario de prueba horneado (comportamiento de CP-2).
if [ -n "${SAMPLE_BIN:-}" ] && [ -f "$SAMPLE_BIN" ]; then
    echo "== inyectando muestra: $SAMPLE_BIN -> /opt/sample/test_sample (debugfs, sin montar) =="
    debugfs -w -R "rm /opt/sample/test_sample"                 "$ROOTFS" >/dev/null 2>&1 || true
    debugfs -w -R "write $SAMPLE_BIN /opt/sample/test_sample"  "$ROOTFS" >/dev/null 2>&1
    debugfs -w -R "sif /opt/sample/test_sample mode 0100755"   "$ROOTFS" >/dev/null 2>&1 || true
    debugfs -w -R "sif /opt/sample/test_sample uid 0"          "$ROOTFS" >/dev/null 2>&1 || true
    debugfs -w -R "sif /opt/sample/test_sample gid 0"          "$ROOTFS" >/dev/null 2>&1 || true
    debugfs -R "stat /opt/sample/test_sample" "$ROOTFS" 2>/dev/null | grep -Ei 'mode|size' | head -n 2 || true
elif [ -n "${SAMPLE_BIN:-}" ]; then
    echo "WARN: SAMPLE_BIN='$SAMPLE_BIN' no existe; se usa el binario de prueba horneado"
fi

# --- Simulacion de red (CP-5) --------------------------------------------
# Redirige el egress del contenedor a INetSim para que la muestra crea que hay Internet.
if [ "${SANDBOX_NET_SIM:-0}" = "1" ]; then
    bash "$EMU/common/netsim.sh"
fi

# --- Argumentos QEMU derivados del perfil --------------------------------
case "$P_DISK_IF" in
    sd)     DRIVE_ARG="-drive file=$ROOTFS,if=sd,format=raw" ;;
    ide)    DRIVE_ARG="-drive file=$ROOTFS,if=ide,format=raw" ;;
    virtio) DRIVE_ARG="-drive file=$ROOTFS,if=virtio,format=raw" ;;
    *) echo "ERROR: P_DISK_IF desconocido: '$P_DISK_IF'"; exit 1 ;;
esac
CPU_ARG=""; [ -n "$P_QEMU_CPU" ] && CPU_ARG="-cpu $P_QEMU_CPU"
APPEND="console=$P_CONSOLE root=$P_ROOT_DEV rw rootwait init=/sbin/telemetry_init panic=1"

SERIAL="$OUT/serial.log"
# Sentinela de fin: telemetry_init lo imprime tras cerrar sondas, sincronizar y remontar ro
# la raíz — el momento seguro para parar QEMU. Se usa porque el reboot limpio NO funciona por
# igual en todas las placas: en vexpress-a9 `reboot -f` + `-no-reboot` hace salir a QEMU, pero
# en malta (mips/mipsel) el kernel HALTA ("Reboot failed -- System halted") y QEMU no saldría
# hasta el timeout. Vigilando el serial paramos pronto en TODAS las ISAs (~15 s en vez de 180).
SENTINEL="=== apagando QEMU ==="
echo "== arrancando QEMU $P_QEMU_BIN -M $P_QEMU_MACHINE ($P_DESC; timeout ${TIMEOUT}s, net: $NETOPT) =="
export QEMU_AUDIO_DRV=none          # backend de audio "none" (evita ruido ALSA de la placa)
set +e
# shellcheck disable=SC2086
"$P_QEMU_BIN" \
        -M "$P_QEMU_MACHINE" $CPU_ARG -smp 1 -m "$P_QEMU_MEM" -no-reboot \
        -kernel "$KERNEL" $DTB_ARG \
        $DRIVE_ARG \
        -append "$APPEND" \
        -net nic,model=$P_NIC_MODEL $NETOPT \
        -nographic \
    > "$SERIAL" 2>&1 &
QEMU_PID=$!
# Para QEMU en cuanto el invitado señale fin (sentinela) o al agotarse el timeout de seguridad.
# Si QEMU sale por sí mismo (p.ej. vexpress-a9: reboot -f + -no-reboot), el bucle acaba solo.
REASON="QEMU salió solo (reboot limpio)"
waited=0
while kill -0 "$QEMU_PID" 2>/dev/null; do
    if grep -qF "$SENTINEL" "$SERIAL" 2>/dev/null; then
        REASON="sentinela (fin de telemetria)"; sleep 1
        kill -TERM "$QEMU_PID" 2>/dev/null; sleep 2; kill -KILL "$QEMU_PID" 2>/dev/null
        break
    fi
    if [ "$waited" -ge "$TIMEOUT" ]; then
        REASON="timeout de seguridad (${TIMEOUT}s)"
        kill -TERM "$QEMU_PID" 2>/dev/null; sleep 2; kill -KILL "$QEMU_PID" 2>/dev/null
        break
    fi
    sleep 1; waited=$((waited + 1))
done
wait "$QEMU_PID" 2>/dev/null
QEMU_RC=$?
set -e
echo "== QEMU termino (rc=$QEMU_RC; parada por: $REASON; ~${waited}s) =="

echo "== extrayendo artefactos con debugfs (sin montar) =="
extract() { debugfs -R "dump /telemetry/$1 $OUT/$1" "$ROOTFS" >/dev/null 2>&1 || echo "  (no encontrado: $1)"; }
for a in strace.log capture.pcap fs_events.log \
         sample.stdout sample.stderr tcpdump.stderr inotify.stderr; do
    extract "$a"
done

echo
echo "############################################################"
echo "#  VERIFICACION DE LOS 3 ARTEFACTOS ($ARCH)               #"
echo "############################################################"
ls -l "$OUT"/strace.log "$OUT"/capture.pcap "$OUT"/fs_events.log 2>/dev/null || true

echo; echo "----- [1] strace.log (primeras lineas + red/fichero) -----"
head -n 15 "$OUT/strace.log" 2>/dev/null || echo "  (vacio)"
echo "  ... syscalls de red/fichero relevantes:"
grep -nE 'connect|sendto|socket|openat.*/tmp|/tmp/iot_sandbox' "$OUT/strace.log" 2>/dev/null | head -n 12 || true

echo; echo "----- [2] capture.pcap (resumen tshark) -----"
if [ -s "$OUT/capture.pcap" ]; then
    tshark -r "$OUT/capture.pcap" -q -z io,phs 2>/dev/null | sed -n '1,40p' || true
    echo "  primeros paquetes:"
    tshark -r "$OUT/capture.pcap" -n 2>/dev/null | head -n 20 || true
else
    echo "  (pcap vacio o ausente)"
fi

echo; echo "----- [3] fs_events.log (eventos de FS) -----"
grep -nE 'iot_sandbox_marker|/tmp/' "$OUT/fs_events.log" 2>/dev/null | head -n 15 || true
echo "  (total eventos: $(wc -l < "$OUT/fs_events.log" 2>/dev/null || echo 0))"

echo; echo "== hecho. Artefactos ($ARCH) en: $OUT =="
