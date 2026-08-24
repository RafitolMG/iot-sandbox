# docker/inetsim.Dockerfile — Simulador de servicios de red de la sandbox (CP-5, ADR-022).
#
# INetSim 1.3.2 (Debian 13 "trixie", misma base que el resto del stack). Contesta DNS, HTTP,
# HTTPS y un puñado de servicios más para que la muestra crea que hay Internet al otro lado.
FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        inetsim \
        # HTTPS y el resto de servicios TLS de INetSim (Recommends del paquete).
        libio-socket-ssl-perl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY docker/inetsim/inetsim.conf /etc/inetsim/inetsim.conf

RUN mkdir -p /var/log/inetsim /var/lib/inetsim/report \
    && chown -R inetsim:inetsim /var/log/inetsim /var/lib/inetsim

# Arranca como root para poder abrir los puertos privilegiados (80, 443…) y baja a
# `inetsim` para servirlos (service_run_as_user).
CMD ["/usr/bin/inetsim", \
     "--config=/etc/inetsim/inetsim.conf", \
     "--log-dir=/var/log/inetsim", \
     "--data-dir=/var/lib/inetsim", \
     "--report-dir=/var/lib/inetsim/report", \
     "--pidfile=/tmp/inetsim.pid"]
