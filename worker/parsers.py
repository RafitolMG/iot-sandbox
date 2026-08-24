"""Parsers de artefactos + extracción de IoCs (CP-3).

Convierte los tres artefactos crudos que produce la emulación (CP-2) en filas de la
base de datos y en indicadores de compromiso (IoCs) deduplicados:

    strace.log     -> syscall_event[]  + IoCs (file, ip, port)
    capture.pcap   -> network_flow[]   + IoCs (ip, domain, port)   [scapy]
    fs_events.log  -> fs_event[]       + IoCs (file)

El sha256 de la propia muestra NO se registra como IoC: es su identidad, ya viaja en el
reporte y en el nombre del fichero. Contarlo inflaba el total en uno por muestra y hacía
que una muestra que ni siquiera llegó a ejecutarse apareciese con "1 IoC".

Se usa **scapy** (2.6.x) para el pcap: es Python puro (no requiere tshark en el worker),
disecciona nativamente el linktype "cooked" (SLL/SLLv2) de `tcpdump -i any` y extrae los
nombres de consulta DNS necesarios para los IoCs de dominio.

Nota de red: 10.0.2.0/24 es la subred interna de QEMU user-mode (SLIRP): 10.0.2.2 (gw),
10.0.2.3 (DNS), 10.0.2.15 (invitado). Es infraestructura del sandbox, no un IoC; se
excluye de los IoCs de IP/puerto para dejar solo destinos externos reales (p.ej. el C2).
"""
from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass, field

# --- Infraestructura de red del sandbox — NO son IoCs ------------------------
SLIRP_NET = ipaddress.ip_network("10.0.2.0/24")
# IP sintética con la que RESPONDE el resolutor comodín (CP-5): aparece en el pcap cuando la
# muestra resuelve un dominio y luego conecta, pero es del simulador, no del C2; el IoC bueno
# ahí es el dominio. OJO: no confundir con SANDBOX_SIM_DNS_IP, que es la dirección del
# contenedor que sirve el DNS y que el invitado nunca llega a ver, porque la redirección
# ocurre por fuera de QEMU. Debe coincidir con `address=/#/` de docker/simdns/dnsmasq.conf.
SIM_ANSWER_IP = ipaddress.ip_address(os.environ.get("SANDBOX_SIM_ANSWER_IP", "192.0.2.1"))

# Rutas de solo-lectura del sistema que NO cuentan como "fichero tocado" por la muestra.
_FS_IOC_IGNORE_PREFIXES = ("/proc", "/sys", "/dev", "/etc", "/usr", "/lib", "/opt/sample")

ARGS_MAXLEN = 400
RESULT_MAXLEN = 120


@dataclass
class ParseResult:
    syscalls: list[dict] = field(default_factory=list)
    network_flows: list[dict] = field(default_factory=list)
    fs_events: list[dict] = field(default_factory=list)
    # IoCs deduplicados por (type, value); el valor es el conjunto de fuentes que lo
    # corroboran (p.ej. una IP vista en strace Y en el pcap -> {"strace","pcap"}).
    iocs: dict[tuple[str, str], set[str]] = field(default_factory=dict)

    def limpiar_nul(self) -> None:
        """Quita los bytes NUL de todo lo que va a la base de datos.

        PostgreSQL no admite NUL en columnas de texto y aborta la transacción entera, así
        que un solo byte en una traza de 250.000 syscalls tiraba el análisis completo. El
        malware real los produce a menudo: buffers binarios en `sendto`, rutas construidas
        a mano, cadenas ofuscadas. Se limpia aquí, en un único punto, y no en cada parser.
        """
        def limpio(v):
            return v.replace("\x00", "") if isinstance(v, str) else v

        for filas in (self.syscalls, self.network_flows, self.fs_events):
            for fila in filas:
                for k, v in fila.items():
                    fila[k] = limpio(v)
        self.iocs = {(limpio(t), limpio(v)): s for (t, v), s in self.iocs.items()}

    def add_ioc(self, type_: str, value: str, source: str) -> None:
        if not value:
            return
        self.iocs.setdefault((type_, str(value)), set()).add(source)


# ============================================================================
# strace.log
# ============================================================================
# Formato (strace -f -tt -T):  PID  HH:MM:SS.ffffff  name(args) = result <dur>
_STRACE_RE = re.compile(
    r"^\s*(?P<pid>\d+)\s+(?P<ts>[\d:.]+)\s+"
    r"(?P<name>\w+)\((?P<args>.*)\)\s*=\s*(?P<result>.*?)(?:\s+<[\d.]+>)?\s*$"
)
# sockaddr embebido:  sin_port=htons(4444), sin_addr=inet_addr("198.51.100.23")
_SIN_PORT_RE = re.compile(r"sin_port=htons\((\d+)\)")
_SIN_ADDR_RE = re.compile(r'sin_addr=inet_addr\("([\d.]+)"\)')
# primer literal entre comillas de los argumentos (típicamente una ruta)
_FIRST_STR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')

# syscalls que denotan escritura/creación/alteración de ficheros
_FS_WRITE_SYSCALLS = {
    "chmod", "fchmodat", "chown", "fchownat", "unlink", "unlinkat", "rename",
    "renameat", "renameat2", "mkdir", "mkdirat", "creat", "mknod", "mknodat",
    "truncate", "link", "linkat", "symlink", "symlinkat",
}
_NET_SYSCALLS = {"connect", "sendto", "sendmsg"}


def parse_strace(text: str, res: ParseResult) -> None:
    seq = 0
    for line in text.splitlines():
        line = line.rstrip("\n")
        if not line:
            continue
        m = _STRACE_RE.match(line)
        if not m:
            # líneas de señal / exit (+++ exited ... +++, --- SIG... ---): se ignoran
            continue
        name = m.group("name")
        args = m.group("args")
        result = m.group("result")
        seq += 1
        res.syscalls.append({
            "seq": seq,
            "ts": m.group("ts"),
            "name": name,
            "args": args[:ARGS_MAXLEN],
            "result": (result or "")[:RESULT_MAXLEN] or None,
        })

        # --- IoCs de red: connect/sendto hacia un destino AF_INET -------------
        if name in _NET_SYSCALLS:
            ip_m = _SIN_ADDR_RE.search(args)
            port_m = _SIN_PORT_RE.search(args)
            if ip_m:
                ip = ip_m.group(1)
                if _is_external_ip(ip):
                    res.add_ioc("ip", ip, "strace")
                    if port_m:
                        res.add_ioc("port", port_m.group(1), "strace")

        # --- IoCs de fichero: syscalls de escritura + openat con O_CREAT/O_WR --
        elif name in _FS_WRITE_SYSCALLS:
            path = _first_path(args)
            if path and _is_fs_ioc_path(path):
                res.add_ioc("file", path, "strace")
        elif name in ("open", "openat"):
            if re.search(r"O_CREAT|O_WRONLY|O_RDWR", args):
                path = _first_path(args)
                if path and _is_fs_ioc_path(path):
                    res.add_ioc("file", path, "strace")


def _first_path(args: str) -> str | None:
    # Para openat el 1er literal suele ser AT_FDCWD (sin comillas) y el 2º la ruta.
    m = _FIRST_STR_RE.search(args)
    return m.group(1) if m else None


def _is_fs_ioc_path(path: str) -> bool:
    if not path.startswith("/"):
        return False
    return not path.startswith(_FS_IOC_IGNORE_PREFIXES)


def _is_external_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr in SLIRP_NET or addr == SIM_ANSWER_IP:
        return False
    if addr.is_loopback or addr.is_unspecified:
        return False
    return True


# ============================================================================
# capture.pcap  (scapy)
# ============================================================================
def parse_pcap(path: str, res: ParseResult) -> None:
    # Import perezoso: scapy es pesado de importar; solo se necesita si hay pcap.
    from scapy.all import DNS, ICMP, IP, TCP, UDP, rdpcap

    try:
        packets = rdpcap(path)
    except Exception:
        return

    # Agregación de flujos por 4-tupla (proto, src, dst, dport).
    flows: dict[tuple, dict] = {}

    for pkt in packets:
        if not pkt.haslayer(IP):
            continue  # ARP y otros L2 no generan flujo IP
        ip = pkt[IP]
        src, dst = ip.src, ip.dst
        nbytes = len(pkt)
        proto = "ip"
        dport = None
        info = None

        is_dns_query = False
        if pkt.haslayer(UDP):
            udp = pkt[UDP]
            dport = int(udp.dport)
            proto = "udp"
            # DNS: solo consultas salientes (qr==0) hacia el puerto 53.
            if pkt.haslayer(DNS) and dport == 53:
                dns = pkt[DNS]
                if getattr(dns, "qr", 1) == 0 and dns.qdcount and dns.qd is not None:
                    qname = _dns_name(dns.qd.qname)
                    proto = "dns"
                    info = qname
                    is_dns_query = True
                    if qname:
                        res.add_ioc("domain", qname, "pcap")
        elif pkt.haslayer(TCP):
            dport = int(pkt[TCP].dport)
            proto = "tcp"
        elif pkt.haslayer(ICMP):
            proto = "icmp"

        # IoCs de IP/puerto: destinos EXTERNOS (fuera de la SLIRP interna).
        if _is_external_ip(dst):
            res.add_ioc("ip", dst, "pcap")
            if dport is not None and proto in ("tcp", "udp"):
                res.add_ioc("port", str(dport), "pcap")

        key = (proto, src, dst, dport)
        flow = flows.get(key)
        if flow is None:
            flows[key] = {
                "proto": proto, "src": src, "dst": dst, "dport": dport,
                "packets": 1, "bytes": nbytes, "info": info,
            }
        else:
            flow["packets"] += 1
            flow["bytes"] += nbytes
            if info and not flow["info"]:
                flow["info"] = info
        _ = is_dns_query  # (documental)

    res.network_flows.extend(flows.values())


def _dns_name(qname) -> str:
    if isinstance(qname, bytes):
        qname = qname.decode("utf-8", "replace")
    return qname.rstrip(".")


# ============================================================================
# fs_events.log
# ============================================================================
# Formato (inotifywait '%T %e %w%f'):  2026-07-07T17:53:01 CREATE /tmp/marker.txt
_FS_RE = re.compile(r"^(?P<ts>\S+)\s+(?P<op>\S+)\s+(?P<path>.+)$")


def parse_fs_events(text: str, res: ParseResult) -> None:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _FS_RE.match(line)
        if not m:
            continue
        path = m.group("path").strip()
        op = m.group("op")
        res.fs_events.append({"ts": m.group("ts"), "op": op, "path": path})
        # Todo fichero tocado según inotify es un IoC de fichero.
        res.add_ioc("file", path, "fs")


# ============================================================================
# Orquestación
# ============================================================================
def parse_artifacts(
    strace_path: str | None,
    pcap_path: str | None,
    fs_path: str | None,
) -> ParseResult:
    """Parsea los 3 artefactos y devuelve eventos + IoCs deduplicados."""
    res = ParseResult()

    if strace_path:
        try:
            with open(strace_path, "r", errors="replace") as fh:
                parse_strace(fh.read(), res)
        except FileNotFoundError:
            pass

    if fs_path:
        try:
            with open(fs_path, "r", errors="replace") as fh:
                parse_fs_events(fh.read(), res)
        except FileNotFoundError:
            pass

    if pcap_path:
        parse_pcap(pcap_path, res)

    res.limpiar_nul()
    return res
