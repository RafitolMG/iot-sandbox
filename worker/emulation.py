"""Lanzamiento de la emulación desde el worker (Docker-out-of-Docker) — ADR-017.

El worker NO ejecuta QEMU en su propio contenedor: reutiliza VERBATIM la imagen de
emulación de CP-2 (`iot-sandbox/emulation:dev`, ADR-016) lanzándola vía el socket de
Docker del host (montado en el worker). La muestra NO confiable se detona dentro de
QEMU, dos capas de aislamiento por debajo del socket; el worker solo orquesta.

Intercambio de datos (todo por Docker, sin traducir rutas a mano):
  - /project        (bind, ro)  -> scripts + kernel/rootfs de `_build/images` (host).
  - /data/samples   (vol, ro)   -> binario subido; se pasa SAMPLE_BIN=<...>/<sha256>.
  - /data/artifacts (vol, rw)   -> los 3 artefactos; el worker los lee de su propio
                                   montaje del MISMO volumen nombrado.

El worker descubre esas tres referencias inspeccionando SUS PROPIOS montajes (así no
hay que codificar la ruta del repo del host ni los nombres de volumen de compose);
admite override por variables de entorno HOST_PROJECT_DIR / SAMPLE_VOLUME /
ARTIFACTS_VOLUME.
"""
from __future__ import annotations

import os

import docker

IMAGE = os.environ.get("EMULATION_IMAGE", "iot-sandbox/emulation:dev")
PROJECT_DEST = "/project"
SAMPLES_DEST = "/data/samples"
ARTIFACTS_DEST = "/data/artifacts"
# Script GENÉRICO dirigido por el registro de perfiles (CP-6, ADR-020): recibe la ISA como
# primer argumento y carga emulation/profiles/<arch>.env.
RUNNER = "emulation/run_emulation.sh"
# Red de detonación con INetSim (CP-5, ADR-022). El nombre real lo pone compose con el
# prefijo del proyecto (p.ej. `iot-sandbox_sandbox_sim`), así que se busca por sufijo entre
# las redes del propio worker en vez de codificarlo.
SIM_NETWORK_SUFFIX = "sandbox_sim"


def _client() -> docker.DockerClient:
    return docker.from_env()


def _self_mounts(client: docker.DockerClient) -> list[dict]:
    cid = os.environ.get("HOSTNAME", "")
    if not cid:
        return []
    try:
        info = client.api.inspect_container(cid)
    except Exception:
        return []
    return info.get("Mounts", []) or []


def resolve_sim_network(client: docker.DockerClient) -> str | None:
    """Nombre de la red Docker donde vive INetSim, o None si el worker no está en ella."""
    override = os.environ.get("SANDBOX_SIM_NETWORK")
    if override:
        return override
    cid = os.environ.get("HOSTNAME", "")
    if not cid:
        return None
    try:
        info = client.api.inspect_container(cid)
    except Exception:
        return None
    networks = (info.get("NetworkSettings", {}) or {}).get("Networks", {}) or {}
    for name in networks:
        if name.endswith(SIM_NETWORK_SUFFIX):
            return name
    return None


def resolve_wiring(client: docker.DockerClient) -> tuple[str | None, str | None, str | None]:
    """Devuelve (host_project_dir, sample_volume, artifacts_volume).

    Prioriza variables de entorno; si faltan, las deriva de los montajes del propio
    contenedor worker (bind de /project y volúmenes de /data/samples y /data/artifacts).
    """
    host_project = os.environ.get("HOST_PROJECT_DIR") or None
    sample_vol = os.environ.get("SAMPLE_VOLUME") or None
    artifacts_vol = os.environ.get("ARTIFACTS_VOLUME") or None

    if not (host_project and sample_vol and artifacts_vol):
        for mt in _self_mounts(client):
            dest = mt.get("Destination")
            if dest == PROJECT_DEST and not host_project:
                host_project = mt.get("Source")
            elif dest == SAMPLES_DEST and not sample_vol:
                sample_vol = mt.get("Name") or mt.get("Source")
            elif dest == ARTIFACTS_DEST and not artifacts_vol:
                artifacts_vol = mt.get("Name") or mt.get("Source")
    return host_project, sample_vol, artifacts_vol


def run_emulation(
    sample_id: int,
    sha256: str,
    arch: str = "arm",
    timeout_s: int = 180,
    net_restrict: bool = False,
    net_sim: bool = False,
    sim_ip: str = "",
    sim_dns_ip: str = "",
    live_trace: bool = False,
) -> dict:
    """Detona la muestra en la sandbox de la ISA `arch` (DooD) y deja los artefactos en un volumen.

    Selecciona el perfil de QEMU/kernel/rootfs pasando `arch` como primer argumento al
    script genérico `emulation/run_emulation.sh` (CP-6, ADR-020). Devuelve
    {"exit_code", "out_dir" (ruta local del worker), "logs"}. `out_dir` apunta al montaje
    que el worker tiene del volumen de artefactos, listo para parsear.
    """
    client = _client()
    host_project, sample_vol, artifacts_vol = resolve_wiring(client)
    if not host_project:
        raise RuntimeError(
            "no se pudo resolver el bind /project del worker (HOST_PROJECT_DIR); "
            "revisa el montaje del repo y del socket de Docker en el servicio worker"
        )
    if not sample_vol:
        raise RuntimeError("no se pudo resolver el volumen de muestras (/data/samples)")
    if not artifacts_vol:
        raise RuntimeError("no se pudo resolver el volumen de artefactos (/data/artifacts)")

    out_in = f"{ARTIFACTS_DEST}/{sample_id}"      # ruta DENTRO del contenedor de emulación
    volumes = {
        host_project: {"bind": PROJECT_DEST, "mode": "ro"},
        sample_vol: {"bind": SAMPLES_DEST, "mode": "ro"},
        artifacts_vol: {"bind": ARTIFACTS_DEST, "mode": "rw"},
    }
    environment = {
        "IN_SANDBOX": "1",                        # salta la re-ejecución en Docker de run_emulation.sh
        "SAMPLE_BIN": f"{SAMPLES_DEST}/{sha256}",  # binario a inyectar en el rootfs (debugfs)
        "SANDBOX_NET_RESTRICT": "1" if net_restrict else "0",
        # Traza en vivo por el segundo puerto serie (CP-8). Ralentiza al invitado, así que
        # se deja apagada en las tandas de evaluación.
        "SANDBOX_LIVE_TRACE": "1" if live_trace else "0",
        "QEMU_AUDIO_DRV": "none",
    }

    # Red de la detonación. Con simulación (CP-5) el contenedor va a la red de INetSim, que
    # es `internal: true`, y necesita NET_ADMIN para instalar el DNAT del egress. Sin ella se
    # mantiene el bridge por defecto de CP-2..CP-4.
    run_kwargs: dict = {"network_mode": "bridge"}
    sim_network = resolve_sim_network(client) if net_sim else None
    if net_sim and sim_network and sim_ip:
        environment["SANDBOX_NET_SIM"] = "1"
        environment["SANDBOX_SIM_IP"] = sim_ip
        environment["SANDBOX_SIM_DNS_IP"] = sim_dns_ip or sim_ip
        run_kwargs = {"network": sim_network, "cap_add": ["NET_ADMIN"]}
    elif net_sim:
        # Mejor detonar sin simulación que no detonar, pero que quede en el log del análisis.
        print(
            "WARN: simulación de red pedida pero no resuelta "
            f"(red={sim_network!r}, ip={sim_ip!r}); se detona con SLIRP normal",
            flush=True,
        )

    container = client.containers.run(
        IMAGE,
        command=["bash", RUNNER, arch, out_in, str(timeout_s)],
        environment=environment,
        volumes=volumes,
        working_dir=PROJECT_DEST,
        user="0:0",                               # root: escribe en el volumen de artefactos
        detach=True,
        **run_kwargs,
    )
    exit_code = -1
    logs = ""
    try:
        result = container.wait(timeout=timeout_s + 120)
        exit_code = int(result.get("StatusCode", -1))
        logs = container.logs().decode("utf-8", "replace")
    finally:
        try:
            container.remove(force=True)
        except Exception:
            pass

    # El worker lee los artefactos de su PROPIO montaje del volumen de artefactos.
    return {"exit_code": exit_code, "out_dir": f"{ARTIFACTS_DEST}/{sample_id}", "logs": logs}
