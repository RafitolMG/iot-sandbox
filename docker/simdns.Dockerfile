# docker/simdns.Dockerfile — DNS comodín de la sandbox (CP-5, ADR-022).
#
# Va en su propio contenedor y no junto a INetSim por una razón concreta: INetSim lleva su
# propia contabilidad de procesos hijo y, con un dnsmasq colgando del mismo PID 1, se queda
# colgado en "Forking services..." sin arrancar ningún servicio (comprobado). Un proceso por
# contenedor y listo.
FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        dnsmasq \
    && rm -rf /var/lib/apt/lists/*

COPY docker/simdns/dnsmasq.conf /etc/dnsmasq.conf

CMD ["dnsmasq", "--keep-in-foreground", "--conf-file=/etc/dnsmasq.conf"]
