"""Parseo de artefactos y extracción de IoCs.

Las trazas de ejemplo están tomadas de detonaciones reales de CP-7, incluidas las que
destaparon defectos: los bytes NUL que tumbaban la transacción entera y el criterio de qué
direcciones son infraestructura del banco de pruebas y no comportamiento de la muestra.
"""
from parsers import ParseResult, parse_artifacts, parse_fs_events, parse_strace

STRACE_MIRAI = """\
53    16:03:30.949273 execve("/opt/sample/test_sample", ["/opt/sample/test_sample"], 0x7ffc /* 5 vars */) = 0 <0.002068>
53    16:03:30.949962 socket(AF_INET, SOCK_DGRAM, IPPROTO_IP) = 3 <0.000092>
53    16:03:30.954136 connect(3, {sa_family=AF_INET, sin_port=htons(53), sin_addr=inet_addr("8.8.8.8")}, 16) = 0 <0.001973>
54    16:03:31.001880 connect(0, {sa_family=AF_INET, sin_port=htons(666), sin_addr=inet_addr("64.89.163.215")}, 16) = -1 EINPROGRESS <0.019114>
54    16:03:31.044670 openat(AT_FDCWD, "/tmp/marcador.txt", O_WRONLY|O_CREAT|O_TRUNC, 0644) = 3 <0.000431>
54    16:03:31.050000 unlink("/opt/sample/test_sample") = 0 <0.000200>
"""


def parsear(texto: str) -> ParseResult:
    res = ParseResult()
    parse_strace(texto, res)
    return res


def iocs_de(res: ParseResult, tipo: str) -> set[str]:
    return {v for (t, v) in res.iocs if t == tipo}


# --------------------------------------------------------------------------- strace

def test_numera_las_syscalls_en_orden():
    res = parsear(STRACE_MIRAI)
    assert [s["seq"] for s in res.syscalls] == [1, 2, 3, 4, 5, 6]
    assert res.syscalls[0]["name"] == "execve"
    assert res.syscalls[0]["result"] == "0"


def test_ignora_lineas_de_senal_y_salida():
    res = parsear(
        STRACE_MIRAI
        + "54    16:03:32.000000 +++ killed by SIGSEGV +++\n"
        + "54    16:03:32.100000 --- SIGCHLD {si_signo=SIGCHLD} ---\n"
    )
    assert len(res.syscalls) == 6


def test_extrae_ip_y_puerto_del_sockaddr():
    res = parsear(STRACE_MIRAI)
    assert "64.89.163.215" in iocs_de(res, "ip")
    assert "666" in iocs_de(res, "port")


def test_el_resolutor_publico_tambien_cuenta():
    """8.8.8.8 es externo: aunque sea un DNS conocido, la muestra decidió ir ahí."""
    assert "8.8.8.8" in iocs_de(parsear(STRACE_MIRAI), "ip")


def test_la_red_interna_del_emulador_no_es_un_ioc():
    """10.0.2.0/24 es SLIRP: puerta de enlace, DNS e IP del invitado. Es andamiaje."""
    traza = '1 00:00:00.1 connect(3, {sa_family=AF_INET, sin_port=htons(53), sin_addr=inet_addr("10.0.2.3")}, 16) = 0 <0.1>\n'
    assert iocs_de(parsear(traza), "ip") == set()


def test_la_ip_sintetica_del_dns_simulado_tampoco():
    """192.0.2.1 la inventa el resolutor comodín de CP-5; el IoC bueno ahí es el dominio."""
    traza = '1 00:00:00.1 connect(3, {sa_family=AF_INET, sin_port=htons(80), sin_addr=inet_addr("192.0.2.1")}, 16) = 0 <0.1>\n'
    assert iocs_de(parsear(traza), "ip") == set()


def test_el_fichero_escrito_es_un_ioc():
    assert "/tmp/marcador.txt" in iocs_de(parsear(STRACE_MIRAI), "file")


def test_la_propia_muestra_no_es_un_fichero_tocado():
    """El binario vive en /opt/sample: que se borre a sí mismo no es un fichero de víctima."""
    assert "/opt/sample/test_sample" not in iocs_de(parsear(STRACE_MIRAI), "file")


def test_las_rutas_de_solo_lectura_del_sistema_se_ignoran():
    traza = '1 00:00:00.1 openat(AT_FDCWD, "/proc/self/status", O_RDONLY) = 3 <0.1>\n'
    assert iocs_de(parsear(traza), "file") == set()


def test_los_argumentos_muy_largos_se_recortan():
    from parsers import ARGS_MAXLEN

    traza = f'1 00:00:00.1 write(1, "{"A" * 5000}", 5000) = 5000 <0.1>\n'
    assert len(parsear(traza).syscalls[0]["args"]) <= ARGS_MAXLEN


# --------------------------------------------------------------------------- fs events

def test_parsea_los_eventos_de_inotify():
    res = ParseResult()
    parse_fs_events(
        "2026-08-24T17:23:31 CREATE /tmp/marcador.txt\n"
        "2026-08-24T17:23:32 MODIFY /tmp/marcador.txt\n",
        res,
    )
    assert [e["op"] for e in res.fs_events] == ["CREATE", "MODIFY"]
    assert iocs_de(res, "file") == {"/tmp/marcador.txt"}


def test_inotify_no_aplica_la_lista_de_rutas_ignoradas():
    """Asimetría deliberada, documentada aquí para que no se rompa sin querer.

    `parse_strace` descarta /etc como IoC de fichero, pero inotify solo vigila /tmp, /etc y
    /root, así que lo que reporta es por definición relevante: la escritura en /etc/inittab
    es persistencia de manual. La consecuencia es que un mismo fichero puede ser IoC o no
    según qué sonda lo viera.
    """
    res = ParseResult()
    parse_fs_events("2026-08-24T17:23:31 MODIFY /etc/inittab\n", res)
    assert "/etc/inittab" in iocs_de(res, "file")

    assert iocs_de(parsear('1 00:00:00.1 openat(AT_FDCWD, "/etc/inittab", O_WRONLY) = 3 <0.1>\n'), "file") == set()


# --------------------------------------------------------------------------- IoCs

def test_un_ioc_acumula_las_fuentes_que_lo_corroboran():
    res = ParseResult()
    res.add_ioc("ip", "198.51.100.23", "strace")
    res.add_ioc("ip", "198.51.100.23", "pcap")
    assert res.iocs[("ip", "198.51.100.23")] == {"strace", "pcap"}


def test_el_hash_de_la_muestra_ya_no_es_un_ioc(tmp_path):
    """Es su identidad, no un hallazgo. Contarlo daba «1 IoC» a muestras que ni se ejecutaron."""
    strace = tmp_path / "strace.log"
    strace.write_text(STRACE_MIRAI, encoding="utf-8")
    res = parse_artifacts(str(strace), None, None)
    assert iocs_de(res, "hash") == set()


# --------------------------------------------------------------------------- bytes NUL

def test_los_bytes_nul_se_limpian_de_todo_lo_que_va_a_la_base():
    """PostgreSQL rechaza el NUL en columnas de texto y aborta la transacción COMPLETA:
    un solo byte en una traza de 250.000 syscalls perdía el informe entero."""
    res = ParseResult()
    res.syscalls.append({"seq": 1, "ts": "x", "name": "sendto", "args": '"\x00\x00bin\x00"', "result": "4"})
    res.fs_events.append({"ts": "x", "op": "CREATE", "path": "/tmp/a\x00b"})
    res.network_flows.append({"proto": "dns", "src": "1.1.1.1", "dst": "2.2.2.2",
                              "dport": 53, "packets": 1, "bytes": 10, "info": "ma\x00lo.example"})
    res.add_ioc("domain", "ma\x00lo.example", "pcap")
    res.limpiar_nul()

    volcado = repr(res.syscalls + res.fs_events + res.network_flows + list(res.iocs))
    assert "\\x00" not in volcado
    assert ("domain", "malo.example") in res.iocs


def test_limpiar_nul_no_toca_los_valores_no_textuales():
    res = ParseResult()
    res.network_flows.append({"proto": "tcp", "dport": 4444, "packets": 8, "info": None})
    res.limpiar_nul()
    assert res.network_flows[0]["dport"] == 4444
    assert res.network_flows[0]["info"] is None


def test_una_traza_real_produce_el_juego_de_iocs_esperado(tmp_path):
    strace = tmp_path / "strace.log"
    strace.write_text(STRACE_MIRAI, encoding="utf-8")
    res = parse_artifacts(str(strace), None, None)
    assert iocs_de(res, "ip") == {"8.8.8.8", "64.89.163.215"}
    assert iocs_de(res, "port") == {"53", "666"}
    assert iocs_de(res, "file") == {"/tmp/marcador.txt"}


def test_artefactos_ausentes_no_rompen_el_parseo():
    res = parse_artifacts(None, None, None)
    assert res.syscalls == [] and res.iocs == {}
    res = parse_artifacts("/no/existe/strace.log", None, "/no/existe/fs.log")
    assert res.syscalls == []
