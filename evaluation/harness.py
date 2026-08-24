#!/usr/bin/env python3
"""Arnés de evaluación de la sandbox (CP-7).

Tres subcomandos:

    inventario <dir>   Qué hay en la carpeta —ISA, hash, familia— SIN detonar nada.
    lote <dir>         Sube cada muestra a la API, espera el informe y saca las tablas.
    comparar A B       Cruza dos ejecuciones (p. ej. con y sin simulación de red).

Sin dependencias externas: solo biblioteca estándar, como `archdetect`. Se ejecuta desde
el host, con el stack levantado (`docker compose up -d`).

La familia de cada muestra no se puede deducir del binario: la anotas tú en un
`manifest.csv` que `inventario --escribir-manifest` te deja preparado con los hashes ya
rellenos. Si no hay manifest, se intenta adivinar por el nombre del fichero.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend" / "app"))
from archdetect import detect_arch_from_bytes, is_elf  # noqa: E402

API_DEFAULT = "http://localhost:8000"
MANIFEST = "manifest.csv"
MANIFEST_COLS = ["sha256", "familia", "fuente", "primera_aparicion", "notas"]

# Familias que se reconocen en el nombre del fichero cuando no hay manifest.
FAMILIAS = ["mirai", "gafgyt", "bashlite", "mozi", "tsunami", "kaiten", "hajime",
            "dark_nexus", "hide_n_seek", "benigno"]

# ISAs con perfil de emulación; el resto se detecta pero no se puede detonar.
ISAS_SOPORTADAS = {"arm", "mips", "mipsel", "x86_64"}


@dataclass
class Muestra:
    ruta: Path
    sha256: str
    tam: int
    isa: str | None
    familia: str
    es_elf: bool = True
    # Resultados de la detonación (se rellenan en `lote`)
    sample_id: int | None = None
    estado: str = ""
    isa_detectada: str = ""
    segundos: float = 0.0
    deduplicada: bool = False
    error: str = ""
    syscalls: int = 0
    flujos: int = 0
    fs: int = 0
    iocs: int = 0
    iocs_por_tipo: Counter = field(default_factory=Counter)
    c2: str = ""
    # `estado == done` solo dice que la tubería terminó. Esto dice si la muestra llegó a
    # EJECUTARSE en el invitado: hay ELF corruptos y binarios OABI cuyo execve falla, y
    # contarlos como análisis correctos inflaría la tasa de éxito.
    ejecuto: bool = False

    @property
    def detonable(self) -> bool:
        return self.isa in ISAS_SOPORTADAS


# --------------------------------------------------------------------------- inventario

def _familia_por_nombre(nombre: str) -> str:
    n = nombre.lower()
    for f in FAMILIAS:
        if f in n:
            return f
    return "?"


def _leer_manifest(directorio: Path) -> dict[str, dict]:
    ruta = directorio / MANIFEST
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8", newline="") as fh:
        return {fila["sha256"]: fila for fila in csv.DictReader(fh) if fila.get("sha256")}


def inventariar(directorio: Path, recursivo: bool = False) -> list[Muestra]:
    patron = "**/*" if recursivo else "*"
    manifest = _leer_manifest(directorio)
    muestras = []
    for ruta in sorted(directorio.glob(patron)):
        if not ruta.is_file() or ruta.name == MANIFEST or ruta.name.startswith("."):
            continue
        datos = ruta.read_bytes()
        sha = hashlib.sha256(datos).hexdigest()
        familia = (manifest.get(sha, {}).get("familia") or "").strip() or _familia_por_nombre(ruta.name)
        muestras.append(Muestra(
            ruta=ruta,
            sha256=sha,
            tam=len(datos),
            isa=detect_arch_from_bytes(datos[:64]),
            es_elf=is_elf(datos[:64]),
            familia=familia,
        ))
    return muestras


def _tabla_cruzada(muestras: list[Muestra]) -> str:
    """Familias en filas, ISAs en columnas: de un vistazo se ve qué falta por conseguir."""
    isas = sorted({m.isa or ("elf-?" if m.es_elf else "no-ELF") for m in muestras})
    familias = sorted({m.familia for m in muestras})
    ancho = max([len(f) for f in familias] + [8])
    lineas = ["  " + "familia".ljust(ancho) + "".join(i.rjust(9) for i in isas) + "total".rjust(8)]
    for fam in familias:
        fila = [len([m for m in muestras if m.familia == fam and (m.isa or ("elf-?" if m.es_elf else "no-ELF")) == i]) for i in isas]
        lineas.append("  " + fam.ljust(ancho) + "".join(str(c).rjust(9) for c in fila)
                      + str(sum(fila)).rjust(8))
    totales = [len([m for m in muestras if (m.isa or ("elf-?" if m.es_elf else "no-ELF")) == i]) for i in isas]
    lineas.append("  " + "TOTAL".ljust(ancho) + "".join(str(c).rjust(9) for c in totales)
                  + str(len(muestras)).rjust(8))
    return "\n".join(lineas)


def cmd_inventario(args) -> int:
    directorio = Path(args.directorio).expanduser().resolve()
    if not directorio.is_dir():
        print(f"error: {directorio} no es un directorio", file=sys.stderr)
        return 1

    muestras = inventariar(directorio, args.recursivo)
    if not muestras:
        print(f"No hay ficheros en {directorio}")
        return 1

    print(f"\n{len(muestras)} ficheros en {directorio}\n")
    print(f"  {'fichero':<40} {'ISA':<10} {'familia':<12} {'tamaño':>10}  sha256")
    print("  " + "-" * 104)
    for m in muestras:
        isa = m.isa or ("ELF ¿?" if m.es_elf else "NO ES ELF")
        marca = " " if m.detonable else "!"
        print(f"{marca} {m.ruta.name[:39]:<40} {isa:<10} {m.familia:<12} "
              f"{m.tam:>10,}  {m.sha256[:32]}…")

    print(f"\nReparto:\n{_tabla_cruzada(muestras)}")

    problemas = [m for m in muestras if not m.detonable]
    if problemas:
        print(f"\n! {len(problemas)} no se pueden detonar (marcadas arriba):")
        for m in problemas:
            detalle = (f"{m.isa} — ISA sin perfil en la sandbox" if m.isa
                       else ("ELF con e_machine desconocido" if m.es_elf else "no es un ELF"))
            print(f"    {m.ruta.name[:24]}…: {detalle}")

    sin_familia = [m for m in muestras if m.familia == "?"]
    if sin_familia:
        print(f"\n! {len(sin_familia)} sin familia asignada. Anótala en {MANIFEST} "
              f"(--escribir-manifest te lo prepara) o incluye el nombre de la familia "
              f"en el del fichero.")

    if args.escribir_manifest:
        _escribir_manifest(directorio, muestras)
    return 0


def _escribir_manifest(directorio: Path, muestras: list[Muestra]) -> None:
    """Crea o completa el manifest sin pisar lo que ya hubieras escrito a mano."""
    ruta = directorio / MANIFEST
    previo = _leer_manifest(directorio)
    nuevas = 0
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLS)
        w.writeheader()
        for m in muestras:
            fila = previo.get(m.sha256)
            if fila is None:
                nuevas += 1
                fila = {"sha256": m.sha256, "familia": "", "fuente": "MalwareBazaar",
                        "primera_aparicion": "", "notas": m.ruta.name}
            w.writerow({c: fila.get(c, "") for c in MANIFEST_COLS})
    print(f"\n{ruta}: {nuevas} filas nuevas, {len(muestras) - nuevas} conservadas. "
          f"Rellena la columna 'familia'.")


# --------------------------------------------------------------------------- API

def _post_muestra(api: str, ruta: Path, datos: bytes) -> dict:
    borde = "----iotsandbox" + secrets.token_hex(16)
    cuerpo = (
        f"--{borde}\r\nContent-Disposition: form-data; name=\"arch\"\r\n\r\nauto\r\n"
        f"--{borde}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{ruta.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
    ).encode() + datos + f"\r\n--{borde}--\r\n".encode()

    req = urllib.request.Request(
        f"{api}/samples", data=cuerpo, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={borde}"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _get_informe(api: str, sample_id: int) -> dict:
    with urllib.request.urlopen(f"{api}/samples/{sample_id}", timeout=60) as r:
        return json.loads(r.read())


def _detonar(api: str, m: Muestra, espera_max: int, sondeo: int) -> None:
    datos = m.ruta.read_bytes()
    t0 = time.monotonic()
    try:
        aceptada = _post_muestra(api, m.ruta, datos)
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:200]
        m.estado, m.error = "rechazada", f"HTTP {e.code}: {detalle}"
        return
    except OSError as e:
        m.estado, m.error = "error", f"no se pudo subir: {e}"
        return

    m.sample_id = aceptada.get("sample_id")
    m.deduplicada = bool(aceptada.get("deduplicated"))

    while True:
        try:
            informe = _get_informe(api, m.sample_id)
        except OSError as e:
            m.estado, m.error = "error", f"no se pudo leer el informe: {e}"
            return
        m.estado = informe.get("status", "")
        if m.estado in ("done", "failed"):
            break
        if time.monotonic() - t0 > espera_max:
            m.estado, m.error = "colgada", f"sin terminar tras {espera_max}s"
            return
        time.sleep(sondeo)

    m.segundos = round(time.monotonic() - t0, 1)
    m.isa_detectada = informe.get("arch") or ""
    m.error = (informe.get("error") or "").split("\n")[0][:160]
    # De `counts`, NO de len(): la API acota los eventos que serializa para no devolver
    # decenas de megas, pero `counts` sigue trayendo los totales reales.
    cuentas = informe.get("counts") or {}
    m.syscalls = int(cuentas.get("syscalls", len(informe.get("syscalls") or [])))
    m.flujos = int(cuentas.get("network_flows", len(informe.get("network_flows") or [])))
    m.fs = int(cuentas.get("fs_events", len(informe.get("fs_events") or [])))
    iocs = informe.get("iocs") or []
    m.iocs = len(iocs)
    m.iocs_por_tipo = Counter(i["type"] for i in iocs)
    # ¿Llegó a ejecutarse? El execve es el primer syscall de la traza.
    m.ejecuto = any(s.get("name") == "execve" and (s.get("result") or "").strip() == "0"
                    for s in (informe.get("syscalls") or [])[:3])

    # El C2 sale del FLUJO saliente con más tráfico, no de emparejar el primer IoC de tipo
    # ip con el primero de tipo port: son valores de syscalls distintas y juntarlos inventa
    # destinos que nunca existieron (p. ej. la IP del C2 con el puerto 53 del resolutor).
    flujos = informe.get("network_flows") or []
    salientes = [f for f in flujos
                 if f.get("dst") and not str(f["dst"]).startswith(("10.0.2.", "192.0.2."))]
    if salientes:
        mejor = max(salientes, key=lambda f: f.get("packets") or 0)
        m.c2 = f"{mejor['dst']}:{mejor['dport']}" if mejor.get("dport") else str(mejor["dst"])
    else:
        dominios = [i["value"] for i in iocs if i["type"] == "domain"]
        m.c2 = dominios[0] if dominios else ""


# --------------------------------------------------------------------------- recoger

def _rellenar_desde_informe(m: Muestra, informe: dict) -> None:
    """Vuelca en `m` las métricas de un informe de la API (compartido por `lote` y `recoger`)."""
    m.sample_id = informe.get("id")
    # Duración real según la base de datos, para no perderla al recuperar una tanda vieja.
    ini, fin = informe.get("created_at"), informe.get("finished_at")
    if ini and fin:
        try:
            m.segundos = round((datetime.fromisoformat(fin) - datetime.fromisoformat(ini))
                               .total_seconds(), 1)
        except ValueError:
            pass
    m.estado = informe.get("status", "")
    m.isa_detectada = informe.get("arch") or ""
    m.error = (informe.get("error") or "").split("\n")[0][:160]
    # De `counts`, NO de len(): la API acota los eventos que serializa para no devolver
    # decenas de megas, pero `counts` sigue trayendo los totales reales.
    cuentas = informe.get("counts") or {}
    m.syscalls = int(cuentas.get("syscalls", len(informe.get("syscalls") or [])))
    m.flujos = int(cuentas.get("network_flows", len(informe.get("network_flows") or [])))
    m.fs = int(cuentas.get("fs_events", len(informe.get("fs_events") or [])))
    iocs = informe.get("iocs") or []
    m.iocs = len(iocs)
    m.iocs_por_tipo = Counter(i["type"] for i in iocs)
    m.ejecuto = any(s.get("name") == "execve" and (s.get("result") or "").strip() == "0"
                    for s in (informe.get("syscalls") or [])[:3])
    flujos = informe.get("network_flows") or []
    salientes = [f for f in flujos
                 if f.get("dst") and not str(f["dst"]).startswith(("10.0.2.", "192.0.2."))]
    if salientes:
        mejor = max(salientes, key=lambda f: f.get("packets") or 0)
        m.c2 = f"{mejor['dst']}:{mejor['dport']}" if mejor.get("dport") else str(mejor["dst"])
    else:
        dominios = [i["value"] for i in iocs if i["type"] == "domain"]
        m.c2 = dominios[0] if dominios else ""


def cmd_recoger(args) -> int:
    """Rehace los resultados leyendo de la API lo ya analizado, SIN volver a detonar.

    Sirve para recuperar una tanda interrumpida o para volver a calcular métricas después
    de tocar el arnés, que si no obligaría a repetir horas de detonaciones.
    """
    directorio = Path(args.directorio).expanduser().resolve()
    muestras = inventariar(directorio, args.recursivo)
    try:
        with urllib.request.urlopen(f"{args.api}/samples?limit=500", timeout=30) as r:
            por_hash = {s["sha256"]: s["id"] for s in json.loads(r.read())}
    except OSError as e:
        print(f"error: la API no responde en {args.api} ({e})", file=sys.stderr)
        return 1

    recogidas = []
    for m in muestras:
        sid = por_hash.get(m.sha256)
        if sid is None:
            continue
        try:
            _rellenar_desde_informe(m, _get_informe(args.api, sid))
        except OSError as e:
            print(f"  {m.sha256[:12]}: no se pudo leer ({e})", file=sys.stderr)
            continue
        recogidas.append(m)

    if not recogidas:
        print("Ninguna de las muestras de esa carpeta está analizada en la API.", file=sys.stderr)
        return 1

    salida = Path(args.salida).expanduser().resolve()
    salida.mkdir(parents=True, exist_ok=True)
    _escribir_csv(salida / "resultados.csv", recogidas)
    (salida / "resultados.md").write_text(_markdown(recogidas, args.etiqueta), encoding="utf-8")
    print(f"{len(recogidas)}/{len(muestras)} recuperadas de la API")
    print(f"  {salida / 'resultados.csv'}\n  {salida / 'resultados.md'}")
    return 0


# --------------------------------------------------------------------------- informes

def _pct(parte: int, total: int) -> str:
    return f"{100 * parte / total:.0f}%" if total else "—"


def _agregado(titulo: str, clave, muestras: list[Muestra]) -> str:
    grupos = defaultdict(list)
    for m in muestras:
        grupos[clave(m)].append(m)
    filas = [f"| {titulo} | n | Ejecutan | syscalls | flujos | fs | IoCs |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for g in sorted(grupos):
        ms = grupos[g]
        ok = [m for m in ms if m.estado == "done" and m.ejecuto]
        med = lambda f: f"{sum(f(m) for m in ok) / len(ok):.1f}" if ok else "—"  # noqa: E731
        filas.append(f"| {g} | {len(ms)} | {_pct(len(ok), len(ms))} | {med(lambda m: m.syscalls)} "
                     f"| {med(lambda m: m.flujos)} | {med(lambda m: m.fs)} | {med(lambda m: m.iocs)} |")
    return "\n".join(filas)


def _markdown(muestras: list[Muestra], etiqueta: str) -> str:
    completadas = [m for m in muestras if m.estado == "done"]
    ok = [m for m in completadas if m.ejecuto]      # las que de verdad corrieron
    tipos = ["ip", "domain", "port", "file", "hash"]

    partes = [
        f"# Evaluación de la sandbox — {etiqueta}",
        "",
        f"- Muestras procesadas: **{len(muestras)}**",
        f"- Análisis completados sin error: **{len(completadas)}** "
        f"({_pct(len(completadas), len(muestras))})",
        f"- Muestras que llegaron a **ejecutarse** en el invitado: **{len(ok)}** "
        f"({_pct(len(ok), len(muestras))})",
        f"- Tiempo medio por muestra: **{sum(m.segundos for m in ok) / len(ok):.0f} s**"
        if ok else "- Tiempo medio por muestra: —",
        "",
        "## Por familia",
        "",
        _agregado("Familia", lambda m: m.familia, muestras),
        "",
        "## Por arquitectura",
        "",
        _agregado("ISA", lambda m: m.isa_detectada or m.isa or "?", muestras),
        "",
        "## Cobertura de IoCs",
        "",
        "Muestras completadas en las que se extrajo al menos un indicador de cada tipo.",
        "",
        "| Tipo de IoC | Muestras | Cobertura |",
        "|---|---:|---:|",
    ]
    for t in tipos:
        n = len([m for m in ok if m.iocs_por_tipo.get(t)])
        partes.append(f"| {t} | {n} | {_pct(n, len(ok))} |")

    partes += ["", "## Detalle por muestra", "",
               "| # | sha256 | Familia | ISA | Ejecuta | s | syscalls | flujos | fs | IoCs | C2 |",
               "|---|---|---|---|---|---:|---:|---:|---:|---:|---|"]
    for i, m in enumerate(muestras, 1):
        estado = ("sí" if m.ejecuto else "**no**") if m.estado == "done" else m.estado
        partes.append(f"| {i} | `{m.sha256[:12]}` | {m.familia} | {m.isa_detectada or m.isa or '?'} "
                      f"| {estado} | {m.segundos:.0f} | {m.syscalls} | {m.flujos} | {m.fs} "
                      f"| {m.iocs} | {m.c2 or '—'} |")

    fallidas = [m for m in muestras if m.estado != "done" or not m.ejecuto]
    if fallidas:
        partes += ["", "## Muestras que no se ejecutaron", "",
                   "El sistema las inyectó correctamente; fue el invitado quien no pudo "
                   "ejecutarlas (ELF corruptos, ABI antigua) o la tubería falló.", "",
                   "| sha256 | Familia | ISA | Estado | syscalls | Motivo |", "|---|---|---|---|---:|---|"]
        for m in fallidas:
            motivo = m.error or ("execve falló en el invitado" if m.estado == "done" else "—")
            partes.append(f"| `{m.sha256[:12]}` | {m.familia} | {m.isa_detectada or m.isa or '?'} "
                          f"| {m.estado} | {m.syscalls} | {motivo} |")

    return "\n".join(partes) + "\n"


CSV_COLS = ["sha256", "fichero", "familia", "isa", "isa_detectada", "estado", "ejecuto", "deduplicada",
            "segundos", "syscalls", "flujos", "fs_events", "iocs", "ioc_ip", "ioc_domain",
            "ioc_port", "ioc_file", "ioc_hash", "c2", "error"]


def _escribir_csv(ruta: Path, muestras: list[Muestra]) -> None:
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLS)
        w.writeheader()
        for m in muestras:
            w.writerow({
                "sha256": m.sha256, "fichero": m.ruta.name, "familia": m.familia,
                "isa": m.isa or "", "isa_detectada": m.isa_detectada, "estado": m.estado,
                "ejecuto": int(m.ejecuto), "deduplicada": int(m.deduplicada), "segundos": m.segundos,
                "syscalls": m.syscalls, "flujos": m.flujos, "fs_events": m.fs, "iocs": m.iocs,
                "ioc_ip": m.iocs_por_tipo.get("ip", 0), "ioc_domain": m.iocs_por_tipo.get("domain", 0),
                "ioc_port": m.iocs_por_tipo.get("port", 0), "ioc_file": m.iocs_por_tipo.get("file", 0),
                "ioc_hash": m.iocs_por_tipo.get("hash", 0), "c2": m.c2, "error": m.error,
            })


def cmd_lote(args) -> int:
    directorio = Path(args.directorio).expanduser().resolve()
    if not directorio.is_dir():
        print(f"error: {directorio} no es un directorio", file=sys.stderr)
        return 1

    try:
        with urllib.request.urlopen(f"{args.api}/health", timeout=10) as r:
            json.loads(r.read())
    except OSError as e:
        print(f"error: la API no responde en {args.api} ({e}).\n"
              f"Levanta el stack:  docker compose up -d", file=sys.stderr)
        return 1

    muestras = inventariar(directorio, args.recursivo)
    detonables = [m for m in muestras if m.detonable]
    descartadas = len(muestras) - len(detonables)
    if not detonables:
        print("No hay ninguna muestra detonable en la carpeta.", file=sys.stderr)
        return 1
    if args.limite:
        detonables = detonables[:args.limite]

    salida = Path(args.salida).expanduser().resolve()
    salida.mkdir(parents=True, exist_ok=True)

    print(f"\n{len(detonables)} muestras a detonar"
          f"{f' ({descartadas} descartadas por ISA)' if descartadas else ''}"
          f" — API {args.api}, espera máx. {args.espera}s\n")

    t0 = time.monotonic()
    for i, m in enumerate(detonables, 1):
        print(f"[{i:>3}/{len(detonables)}] {m.ruta.name[:38]:<40} {m.familia:<10} {m.isa:<7} ",
              end="", flush=True)
        _detonar(args.api, m, args.espera, args.sondeo)
        aviso = " (dedup)" if m.deduplicada else ""
        if m.estado == "done":
            print(f"OK{aviso}  {m.segundos:>4.0f}s  {m.syscalls} sys / {m.flujos} net / "
                  f"{m.fs} fs / {m.iocs} IoCs")
        else:
            print(f"{m.estado.upper()}{aviso}  {m.error[:60]}")

    csv_out = salida / "resultados.csv"
    md_out = salida / "resultados.md"
    _escribir_csv(csv_out, detonables)
    md_out.write_text(_markdown(detonables, args.etiqueta), encoding="utf-8")

    ok = len([m for m in detonables if m.estado == "done"])
    print(f"\n{ok}/{len(detonables)} completadas en {(time.monotonic() - t0) / 60:.1f} min")
    print(f"  {csv_out}\n  {md_out}")
    return 0


# --------------------------------------------------------------------------- recoger

def _rellenar_desde_informe(m: Muestra, informe: dict) -> None:
    """Vuelca en `m` las métricas de un informe de la API (compartido por `lote` y `recoger`)."""
    m.sample_id = informe.get("id")
    # Duración real según la base de datos, para no perderla al recuperar una tanda vieja.
    ini, fin = informe.get("created_at"), informe.get("finished_at")
    if ini and fin:
        try:
            m.segundos = round((datetime.fromisoformat(fin) - datetime.fromisoformat(ini))
                               .total_seconds(), 1)
        except ValueError:
            pass
    m.estado = informe.get("status", "")
    m.isa_detectada = informe.get("arch") or ""
    m.error = (informe.get("error") or "").split("\n")[0][:160]
    # De `counts`, NO de len(): la API acota los eventos que serializa para no devolver
    # decenas de megas, pero `counts` sigue trayendo los totales reales.
    cuentas = informe.get("counts") or {}
    m.syscalls = int(cuentas.get("syscalls", len(informe.get("syscalls") or [])))
    m.flujos = int(cuentas.get("network_flows", len(informe.get("network_flows") or [])))
    m.fs = int(cuentas.get("fs_events", len(informe.get("fs_events") or [])))
    iocs = informe.get("iocs") or []
    m.iocs = len(iocs)
    m.iocs_por_tipo = Counter(i["type"] for i in iocs)
    m.ejecuto = any(s.get("name") == "execve" and (s.get("result") or "").strip() == "0"
                    for s in (informe.get("syscalls") or [])[:3])
    flujos = informe.get("network_flows") or []
    salientes = [f for f in flujos
                 if f.get("dst") and not str(f["dst"]).startswith(("10.0.2.", "192.0.2."))]
    if salientes:
        mejor = max(salientes, key=lambda f: f.get("packets") or 0)
        m.c2 = f"{mejor['dst']}:{mejor['dport']}" if mejor.get("dport") else str(mejor["dst"])
    else:
        dominios = [i["value"] for i in iocs if i["type"] == "domain"]
        m.c2 = dominios[0] if dominios else ""


def cmd_recoger(args) -> int:
    """Rehace los resultados leyendo de la API lo ya analizado, SIN volver a detonar.

    Sirve para recuperar una tanda interrumpida o para volver a calcular métricas después
    de tocar el arnés, que si no obligaría a repetir horas de detonaciones.
    """
    directorio = Path(args.directorio).expanduser().resolve()
    muestras = inventariar(directorio, args.recursivo)
    try:
        with urllib.request.urlopen(f"{args.api}/samples?limit=500", timeout=30) as r:
            por_hash = {s["sha256"]: s["id"] for s in json.loads(r.read())}
    except OSError as e:
        print(f"error: la API no responde en {args.api} ({e})", file=sys.stderr)
        return 1

    recogidas = []
    for m in muestras:
        sid = por_hash.get(m.sha256)
        if sid is None:
            continue
        try:
            _rellenar_desde_informe(m, _get_informe(args.api, sid))
        except OSError as e:
            print(f"  {m.sha256[:12]}: no se pudo leer ({e})", file=sys.stderr)
            continue
        recogidas.append(m)

    if not recogidas:
        print("Ninguna de las muestras de esa carpeta está analizada en la API.", file=sys.stderr)
        return 1

    salida = Path(args.salida).expanduser().resolve()
    salida.mkdir(parents=True, exist_ok=True)
    _escribir_csv(salida / "resultados.csv", recogidas)
    (salida / "resultados.md").write_text(_markdown(recogidas, args.etiqueta), encoding="utf-8")
    print(f"{len(recogidas)}/{len(muestras)} recuperadas de la API")
    print(f"  {salida / 'resultados.csv'}\n  {salida / 'resultados.md'}")
    return 0


# --------------------------------------------------------------------------- informe

def _muestras_desde_csv(ruta: Path) -> list[Muestra]:
    """Reconstruye las muestras desde un resultados.csv para volver a maquetar el informe."""
    muestras = []
    with ruta.open(encoding="utf-8", newline="") as fh:
        for f in csv.DictReader(fh):
            m = Muestra(ruta=Path(f["fichero"]), sha256=f["sha256"], tam=0,
                        isa=f["isa"] or None, familia=f["familia"])
            m.estado = f["estado"]
            m.isa_detectada = f["isa_detectada"]
            m.segundos = float(f["segundos"] or 0)
            m.deduplicada = f["deduplicada"] == "1"
            m.ejecuto = f.get("ejecuto") == "1"
            m.error = f["error"]
            m.syscalls, m.flujos = int(f["syscalls"]), int(f["flujos"])
            m.fs, m.iocs = int(f["fs_events"]), int(f["iocs"])
            m.iocs_por_tipo = Counter({t: int(f[f"ioc_{t}"])
                                       for t in ("ip", "domain", "port", "file", "hash")
                                       if int(f[f"ioc_{t}"])})
            m.c2 = f["c2"]
            muestras.append(m)
    return muestras


def cmd_informe(args) -> int:
    """Vuelve a generar el Markdown desde uno o varios CSV (para fusionar reintentos)."""
    muestras: dict[str, Muestra] = {}
    for ruta in args.csv:
        for m in _muestras_desde_csv(Path(ruta).expanduser()):
            muestras[m.sha256] = m          # el último CSV gana: así se pisan los reintentos
    ordenadas = sorted(muestras.values(), key=lambda m: m.sha256)
    salida = Path(args.salida).expanduser()
    salida.write_text(_markdown(ordenadas, args.etiqueta), encoding="utf-8")
    print(f"{len(ordenadas)} muestras -> {salida}")
    return 0


# --------------------------------------------------------------------------- comparar

def cmd_comparar(args) -> int:
    def cargar(ruta: str) -> dict[str, dict]:
        with Path(ruta).expanduser().open(encoding="utf-8", newline="") as fh:
            return {f["sha256"]: f for f in csv.DictReader(fh)}

    a, b = cargar(args.csv_a), cargar(args.csv_b)
    comunes = sorted(set(a) & set(b))
    if not comunes:
        print("Los dos CSV no comparten ninguna muestra.", file=sys.stderr)
        return 1

    num = ["syscalls", "flujos", "fs_events", "iocs"]
    filas = [f"# Comparativa — {args.nombre_a} vs {args.nombre_b}", "",
             f"{len(comunes)} muestras presentes en ambas ejecuciones.", "",
             "| sha256 | Familia | ISA | " +
             " | ".join(f"{c} {args.nombre_a} / {args.nombre_b}" for c in num) + " |",
             "|---|---|---|" + "---|" * len(num)]
    for sha in comunes:
        fa, fb = a[sha], b[sha]
        celdas = " | ".join(f"{fa[c]} / {fb[c]}" for c in num)
        filas.append(f"| `{sha[:12]}` | {fa['familia']} | {fa['isa_detectada'] or fa['isa']} | {celdas} |")

    filas += ["", "## Medias", "", "| Métrica | " + args.nombre_a + " | " + args.nombre_b + " | Δ |",
              "|---|---:|---:|---:|"]
    for c in num:
        ma = sum(float(a[s][c]) for s in comunes) / len(comunes)
        mb = sum(float(b[s][c]) for s in comunes) / len(comunes)
        filas.append(f"| {c} | {ma:.1f} | {mb:.1f} | {mb - ma:+.1f} |")

    texto = "\n".join(filas) + "\n"
    if args.salida:
        Path(args.salida).expanduser().write_text(texto, encoding="utf-8")
        print(f"escrito {args.salida}")
    else:
        print(texto)
    return 0


# --------------------------------------------------------------------------- main

def main() -> int:
    p = argparse.ArgumentParser(
        description="Arnés de evaluación de la sandbox (CP-7).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""ejemplos:
  %(prog)s inventario ~/muestras --escribir-manifest
  %(prog)s lote ~/muestras --salida resultados/con-simulacion
  %(prog)s comparar resultados/con-simulacion/resultados.csv \\
                    resultados/sin-simulacion/resultados.csv \\
                    --nombre-a "con INetSim" --nombre-b "sin INetSim"
""")
    sub = p.add_subparsers(dest="cmd", required=True)

    inv = sub.add_parser("inventario", help="qué hay en la carpeta, sin detonar nada")
    inv.add_argument("directorio")
    inv.add_argument("--recursivo", action="store_true")
    inv.add_argument("--escribir-manifest", action="store_true", dest="escribir_manifest",
                     help=f"crea/completa {MANIFEST} con los hashes para que anotes la familia")
    inv.set_defaults(func=cmd_inventario)

    lote = sub.add_parser("lote", help="detona toda la carpeta y saca las tablas")
    lote.add_argument("directorio")
    lote.add_argument("--api", default=API_DEFAULT)
    lote.add_argument("--salida", default="resultados")
    lote.add_argument("--etiqueta", default="ejecución sin etiquetar",
                      help="título del informe (p. ej. 'con simulación de red')")
    lote.add_argument("--espera", type=int, default=600,
                      help="segundos máximos por muestra; debe superar EMULATION_TIMEOUT (600)")
    lote.add_argument("--sondeo", type=int, default=5, help="cada cuánto se consulta el estado (5)")
    lote.add_argument("--limite", type=int, help="detona solo las N primeras (para probar)")
    lote.add_argument("--recursivo", action="store_true")
    lote.set_defaults(func=cmd_lote)

    rec = sub.add_parser("recoger", help="rehace los resultados desde la API, sin detonar")
    rec.add_argument("directorio")
    rec.add_argument("--api", default=API_DEFAULT)
    rec.add_argument("--salida", default="resultados")
    rec.add_argument("--etiqueta", default="ejecución sin etiquetar")
    rec.add_argument("--recursivo", action="store_true")
    rec.set_defaults(func=cmd_recoger)

    inf = sub.add_parser("informe", help="rehace el Markdown desde uno o varios CSV")
    inf.add_argument("csv", nargs="+", help="CSV a fusionar; el último gana en caso de repetido")
    inf.add_argument("--salida", default="resultados.md")
    inf.add_argument("--etiqueta", default="ejecución sin etiquetar")
    inf.set_defaults(func=cmd_informe)

    cmp_ = sub.add_parser("comparar", help="cruza dos ejecuciones (p. ej. con y sin simulación)")
    cmp_.add_argument("csv_a")
    cmp_.add_argument("csv_b")
    cmp_.add_argument("--nombre-a", default="A", dest="nombre_a")
    cmp_.add_argument("--nombre-b", default="B", dest="nombre_b")
    cmp_.add_argument("--salida")
    cmp_.set_defaults(func=cmd_comparar)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
