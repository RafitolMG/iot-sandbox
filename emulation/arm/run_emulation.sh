#!/usr/bin/env bash
# ============================================================================
# run_emulation.sh — Ejecuta UNA detonacion en la sandbox ARM (IoT TFM, CP-2)
# ============================================================================
# Arranca QEMU full-system ARM (vexpress-a9) con el kernel+rootfs de Buildroot,
# ejecuta el binario benigno bajo telemetria (lo orquesta /sbin/telemetry_init
# dentro del invitado) y recoge en el host los TRES artefactos:
#     strace.log · capture.pcap · fs_events.log
#
# La extraccion se hace con `debugfs` (lee ficheros del ext2 SIN montar la imagen,
# sin privilegios). Al terminar, QEMU se apaga solo (el invitado hace reboot -f con
# -no-reboot); ademas hay un timeout de seguridad en el host. Nada queda colgando.
#
# Se auto-reejecuta dentro del contenedor `iot-sandbox/emulation:dev` (QEMU vive ahi).
#
# Uso:    emulation/arm/run_emulation.sh [OUTDIR] [TIMEOUT_SEG]
# Salida: OUTDIR (por defecto emulation/arm/_build/artifacts) con los 3 artefactos.
# ============================================================================
set -euo pipefail

IMAGE="iot-sandbox/emulation:dev"
TIMEOUT="${2:-180}"                 # timeout de seguridad del host (s)
# Aislamiento de red: en CP-2 se deja SLIRP normal para GARANTIZAR que el intento
# de red del binario quede capturado en el pcap. El aislamiento pleno (restrict/INetSim)
# es CP-5. Exporta SANDBOX_NET_RESTRICT=1 para bloquear egress ya en CP-2.
if [ "${SANDBOX_NET_RESTRICT:-0}" = "1" ]; then NETOPT="-net user,restrict=on"; else NETOPT="-net user"; fi

# ---------------------------------------------------------------------------
# HOST: reejecutar dentro del contenedor de emulacion.
# ---------------------------------------------------------------------------
if [ -z "${IN_SANDBOX:-}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
    OUT_HOST="${1:-$REPO/emulation/arm/_build/artifacts}"
    mkdir -p "$OUT_HOST"
    OUT_IN="/project/${OUT_HOST#$REPO/}"
    exec docker run --rm -u 1000:1000 -e IN_SANDBOX=1 \
        -e SANDBOX_NET_RESTRICT="${SANDBOX_NET_RESTRICT:-0}" \
        -v "$REPO":/project -w /project "$IMAGE" \
        bash emulation/arm/run_emulation.sh "$OUT_IN" "$TIMEOUT"
fi

# ---------------------------------------------------------------------------
# DENTRO del contenedor
# ---------------------------------------------------------------------------
ARM="/project/emulation/arm"
IMAGES="$ARM/_build/images"
OUT="${1:-$ARM/_build/artifacts}"
mkdir -p "$OUT"

ZIMAGE="$IMAGES/zImage"
DTB="$IMAGES/vexpress-v2p-ca9.dtb"
ROOTFS_SRC="$IMAGES/rootfs.ext2"
for f in "$ZIMAGE" "$DTB" "$ROOTFS_SRC"; do
    [ -f "$f" ] || { echo "ERROR: falta $f — ejecuta build_rootfs.sh primero"; exit 1; }
done

# Copia de trabajo del rootfs (el invitado escribe los artefactos dentro; no tocamos el pristino).
RUNDIR="$(mktemp -d)"
trap 'rm -rf "$RUNDIR"' EXIT
ROOTFS="$RUNDIR/rootfs.ext2"
cp "$ROOTFS_SRC" "$ROOTFS"
# La tarjeta SD de vexpress-a9 exige un tamaño potencia de 2; el ext2 (200M) se aloja
# en un dispositivo de 256M (el fs conserva su tamaño interno; el resto queda sin usar).
qemu-img resize -f raw "$ROOTFS" 256M >/dev/null

# --- Inyeccion de la muestra (CP-3) --------------------------------------
# Si SAMPLE_BIN apunta a un binario, SUSTITUYE el /opt/sample/test_sample horneado por
# la muestra subida (tratada como NO confiable). Se escribe en el ext2 con `debugfs -w`
# (sin montar la imagen, sin privilegios) y se marca ejecutable+root. La muestra solo se
# ejecuta despues DENTRO de QEMU (nunca en este contenedor ni en el host). Si SAMPLE_BIN
# no esta definido se usa el binario de prueba horneado (comportamiento de CP-2).
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

SERIAL="$OUT/serial.log"

echo "== arrancando QEMU vexpress-a9 (timeout ${TIMEOUT}s, net: $NETOPT) =="
export QEMU_AUDIO_DRV=none          # backend de audio "none" para el códec de la placa (evita ruido ALSA)
set +e
timeout -k 10 "$TIMEOUT" \
    qemu-system-arm \
        -M vexpress-a9 -smp 1 -m 256 -no-reboot \
        -kernel "$ZIMAGE" -dtb "$DTB" \
        -drive "file=$ROOTFS,if=sd,format=raw" \
        -append "console=ttyAMA0,115200 root=/dev/mmcblk0 rw rootwait init=/sbin/telemetry_init panic=1" \
        -net nic,model=lan9118 $NETOPT \
        -nographic \
    > "$SERIAL" 2>&1
QEMU_RC=$?
set -e
echo "== QEMU termino (rc=$QEMU_RC; 124 = timeout del host) =="

echo "== extrayendo artefactos con debugfs (sin montar) =="
extract() { debugfs -R "dump /telemetry/$1 $OUT/$1" "$ROOTFS" >/dev/null 2>&1 || echo "  (no encontrado: $1)"; }
for a in strace.log capture.pcap fs_events.log \
         sample.stdout sample.stderr tcpdump.stderr inotify.stderr; do
    extract "$a"
done

echo
echo "############################################################"
echo "#  VERIFICACION DE LOS 3 ARTEFACTOS                        #"
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

echo; echo "== hecho. Artefactos en: $OUT =="
