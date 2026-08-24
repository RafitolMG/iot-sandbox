# evaluation/ — Arnés de evaluación (CP-7)

Herramienta para detonar un conjunto de muestras contra la sandbox y sacar las tablas que
van al capítulo 4 de la memoria (§4.3 Evaluación). Solo biblioteca estándar; se ejecuta
desde el host con el stack levantado.

Las muestras **no se versionan**: viven en una carpeta tuya fuera del repo.

## 1. Inventario — qué tienes, sin detonar nada

```bash
python3 evaluation/harness.py inventario ~/muestras --escribir-manifest
```

Lee solo la cabecera ELF de cada fichero (no ejecuta nada) y muestra ISA, hash, tamaño y
familia, más una tabla cruzada familia × ISA para ver de un vistazo qué te falta por
conseguir. Marca con `!` lo que no se puede detonar: ficheros que no son ELF y arquitecturas
sin perfil (aarch64, i386).

La familia no se puede deducir del binario. Con `--escribir-manifest` se genera un
`manifest.csv` junto a las muestras con los hashes ya rellenos para que anotes la columna
`familia` (y, si quieres, `fuente` y `primera_aparicion`, que es lo que se cita en la
memoria en lugar del binario). Si no hay manifest, se intenta adivinar la familia por el
nombre del fichero (`mirai_arm_01.bin` → mirai).

## 2. Lote — detonar y medir

```bash
docker compose up -d
python3 evaluation/harness.py lote ~/muestras \
    --salida resultados/con-simulacion \
    --etiqueta "con simulación de red"
```

Sube cada muestra por la API, espera el informe y escribe dos ficheros:

- `resultados.csv` — una fila por muestra, para tratar los datos por tu cuenta.
- `resultados.md` — tablas listas para pegar: resumen global, agregados **por familia** y
  **por arquitectura**, cobertura de IoCs por tipo y detalle muestra a muestra.

Va en serie, que es como trabaja el worker (una detonación a la vez). Opciones útiles:
`--limite N` para probar con unas pocas, `--espera` (segundos máximos por muestra; súbelo si
subes `EMULATION_TIMEOUT`) y `--api` si la API no está en localhost:8000.

**Sobre los tiempos:** el binario benigno de prueba termina solo y la detonación acaba en
~15 s, pero el malware real no termina nunca — se queda en su bucle y la detonación agota la
ventana completa de `EMULATION_TIMEOUT` (180 s por defecto). Está comprobado que los
artefactos sobreviven a ese cierre forzado, así que no hay nada que arreglar; simplemente
calcula: 40 muestras × 180 s ≈ 2 h. Con `EMULATION_TIMEOUT=120` bajas a ~80 min. La ventana
elegida es un parámetro metodológico y conviene declararlo en la memoria.

## 3. Comparar — el A/B de la simulación de red

Para medir qué aporta CP-5 sobre malware real hay que pasar el mismo conjunto dos veces,
con y sin simulación, y cruzar los resultados:

```bash
# Pasada 1 — con simulación (por defecto)
docker compose up -d
python3 evaluation/harness.py lote ~/muestras --salida resultados/con-sim \
    --etiqueta "con simulación de red"

# Pasada 2 — sin simulación
docker compose down -v                      # OJO: -v borra la base de datos y los artefactos
SANDBOX_NET_SIM=0 docker compose up -d
python3 evaluation/harness.py lote ~/muestras --salida resultados/sin-sim \
    --etiqueta "sin simulación de red"

python3 evaluation/harness.py comparar \
    resultados/con-sim/resultados.csv resultados/sin-sim/resultados.csv \
    --nombre-a "con INetSim" --nombre-b "sin INetSim" \
    --salida resultados/comparativa.md
```

El `docker compose down -v` de en medio **no es opcional**: la API deduplica por SHA-256
(índice único en `sample.sha256`), así que sin base limpia la segunda pasada devolvería los
informes de la primera en lugar de volver a detonar. Borra también los artefactos de las
detonaciones anteriores, así que guarda antes lo que quieras conservar.

> Si esto llega a molestar, la alternativa de fondo es separar en el modelo de datos la
> *muestra* (el binario) del *análisis* (cada ejecución), permitiendo N análisis por hash.
> Es un cambio de esquema que toca ADR-018 y necesita migración: decisión pendiente, no se
> ha hecho.

## Seguridad

Nada de esto ejecuta las muestras en el host: solo se leen sus bytes para calcular el hash y
la ISA, y se envían por HTTP a la API. La detonación ocurre dentro de QEMU, en la red aislada
de CP-5. No hagas `chmod +x` sobre las muestras ni las abras fuera de la sandbox.
