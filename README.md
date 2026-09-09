# IoT Malware Dynamic Analysis Sandbox

Sandbox de análisis dinámico para malware IoT. Ejecuta el binario dentro de QEMU en modo
full-system —ARM, MIPS, MIPSEL o x86_64, detectando la arquitectura por la cabecera ELF—,
captura lo que hace (syscalls, red, ficheros) y extrae indicadores de compromiso. Se opera
desde el navegador y se levanta con Docker Compose.

Es la parte práctica de un TFM en Ciberseguridad (UNIR): *Diseño e implementación de un
sistema automatizado de análisis dinámico de malware para entornos IoT multi-arquitectura*.

## Seguridad

Esto ejecuta malware real. La muestra se detona siempre dentro del invitado QEMU, nunca en
el host ni en el contenedor que lo lanza, y sobre una red sin salida a Internet. El binario
no se ejecuta, no se marca ejecutable y no se abre fuera del invitado: se inyecta en la
imagen del rootfs con `debugfs`, sin montarla.

## Cómo se levanta

```bash
docker compose up --build
```

Cuando todo esté `healthy`, la web está en http://localhost:5173. Se sube un binario, se ve
pasar de *En cola* a *Analizando* y a *Completado*, y al pinchar aparece el informe con los
IoCs y las pestañas de red, syscalls y ficheros.

Antes de la primera detonación hay que construir el kernel y el rootfs de cada arquitectura:

```bash
emulation/build_rootfs.sh arm      # y mips, mipsel, x86_64
```

Son unos 17 minutos por arquitectura, una sola vez. No están versionados porque pesan gigas.
Se pueden construir varias a la vez, comparten la caché de descargas. Sin ellos los servicios
levantan igual, pero el análisis falla.

| Servicio | Qué es | Puerto |
|---|---|---|
| frontend | SPA Vue 3 servida por nginx | 5173 |
| api | FastAPI | 8000 |
| db | PostgreSQL 16 | 5432 |
| valkey | broker de Celery | 6379 |
| worker | Celery, lanza QEMU por el socket de Docker | — |
| inetsim | servicios de red simulados | — |
| simdns | dnsmasq, resuelve cualquier dominio | — |

nginx proxya `/api` hacia la API, así que el navegador solo usa el 5173 y no hay CORS de por
medio. `inetsim` y `simdns` no publican nada: viven en la red de detonación, que es
`internal`, y allí es donde se redirige todo el tráfico del invitado. El pcap se captura
dentro de QEMU, así que conserva la IP y el puerto que la muestra pidió de verdad.

## Tests

```bash
docker compose run --rm --no-deps -w /project worker pytest -p no:cacheprovider
```

Cubren la detección de arquitectura y el parseo de artefactos, que es donde han salido los
fallos: bytes NUL en las trazas que tumbaban el análisis entero, confundir «no es un ELF»
con «ELF de una arquitectura que no conozco», y qué direcciones son del propio banco de
pruebas y no de la muestra. Van dentro del contenedor del worker porque ahí están las
dependencias.

## Traza en vivo

Con `SANDBOX_LIVE_TRACE=1` el invitado va sacando el strace por un segundo puerto serie y
aparece en `trace.live` mientras la muestra corre, en vez de esperar a que termine. Ojo: eso
ralentiza al invitado, así que no conviene usarlo en tandas de evaluación porque falsea los
recuentos.

## Licencia

MIT, ver [LICENSE](LICENSE). QEMU, INetSim, dnsmasq y Buildroot son GPL y se usan como
programas aparte dentro de sus contenedores: aquí solo hay configuración y Dockerfiles
propios, nada de su código.
