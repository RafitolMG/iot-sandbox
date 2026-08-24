#!/usr/bin/env bash
# ============================================================================
# netsim.sh — Redirige TODO el tráfico de la detonación hacia INetSim (CP-5, ADR-022)
# ============================================================================
# Se ejecuta DENTRO del contenedor de emulación, antes de arrancar QEMU, cuando el worker
# pide simulación de red (SANDBOX_NET_SIM=1 + SANDBOX_SIM_IP=<ip de inetsim>).
#
# El invitado usa SLIRP (QEMU user-mode), así que sus paquetes salen del contenedor como
# tráfico local: basta con reescribir el destino en la cadena nat/output. Hay dos caminos y
# los dos acaban en INetSim:
#
#   1. DNS del invitado -> 10.0.2.3 lo atiende el propio SLIRP, que reenvía usando el
#      resolv.conf del contenedor. Por eso se apunta resolv.conf a INetSim.
#   2. Todo lo demás (IPs y puertos codificados a fuego en la muestra, DNS a 8.8.8.8, etc.)
#      sale como paquete real del contenedor y lo captura el DNAT.
#
# Lo que ve el invitado NO cambia: tcpdump corre dentro de QEMU, así que el pcap conserva la
# IP y el puerto que la muestra pidió de verdad. La reescritura ocurre una capa por fuera.
#
# Requiere CAP_NET_ADMIN en el contenedor (lo añade worker/emulation.py).
# ============================================================================
set -euo pipefail

SIM_IP="${SANDBOX_SIM_IP:?netsim.sh necesita SANDBOX_SIM_IP}"
# El DNS comodín vive en su propio contenedor (servicio `simdns`); si no se pasa, se asume
# que lo sirve el mismo INetSim.
SIM_DNS_IP="${SANDBOX_SIM_DNS_IP:-$SIM_IP}"
# Puerto del catch-all de INetSim (dummy_bind_port en inetsim.conf).
DUMMY_PORT="${SANDBOX_SIM_DUMMY_PORT:-1}"

# Puertos con servicio propio en INetSim: se conserva el puerto para que conteste el
# protocolo correcto. El resto cae al dummy, que solo completa el handshake.
SERVED_TCP="21, 25, 80, 110, 143, 443, 465, 587, 993, 995, 6667, 8080"
SERVED_UDP="69, 123, 514"

echo "== simulación de red: egress -> INetSim ($SIM_IP), DNS -> $SIM_DNS_IP =="

# 1. DNS del reenviador de SLIRP.
printf 'nameserver %s\n' "$SIM_DNS_IP" > /etc/resolv.conf

# 2. Ruta por defecto.
# La red de detonación es `internal: true`, así que Docker no le pone default gateway: sin
# ruta, un connect() a una IP codificada a fuego en la muestra falla con ENETUNREACH ANTES
# de generar paquete, el DNAT no llega a verlo y el invitado deduce que está en una sandbox.
# Se manda todo al propio INetSim como siguiente salto (está en la misma /24): el paquete se
# genera, la cadena nat/output reescribe el destino y se re-enruta.
if ! ip -4 route show default | grep -q .; then
    ip route add default via "$SIM_IP"
fi

# 3. DNAT del resto del tráfico.
nft -f - <<EOF
table ip sandbox_sim {
    chain output {
        type nat hook output priority -100; policy accept;

        # Loopback y los propios simuladores: sin tocar (si no, se redirigirían a sí mismos).
        ip daddr 127.0.0.0/8 return
        ip daddr $SIM_IP return
        ip daddr $SIM_DNS_IP return

        # DNS a su contenedor; el resto del tráfico, a INetSim.
        udp dport 53 dnat to $SIM_DNS_IP:53
        tcp dport 53 dnat to $SIM_DNS_IP:53

        tcp dport { $SERVED_TCP } dnat to $SIM_IP
        udp dport { $SERVED_UDP } dnat to $SIM_IP

        # Catch-all: cualquier otro puerto acaba en el servicio dummy. Se casa el protocolo
        # con meta l4proto porque un 'tcp' suelto no es un match válido para nft.
        meta l4proto tcp dnat to $SIM_IP:$DUMMY_PORT
        meta l4proto udp dnat to $SIM_IP:$DUMMY_PORT
    }
}
EOF

# Comprobación de que INetSim responde antes de detonar; si no, la muestra vería una red
# muerta y estaríamos midiendo justo lo que CP-5 quiere evitar.
if ! timeout 5 bash -c "</dev/tcp/$SIM_IP/80" 2>/dev/null; then
    echo "WARN: INetSim no responde en $SIM_IP:80 — la detonación seguirá, pero sin simulación útil"
fi
