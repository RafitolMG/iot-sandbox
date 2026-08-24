"""Los módulos bajo prueba viven en carpetas de servicio, no en un paquete instalable.

Se ejecutan dentro del contenedor del worker (`docker compose run --rm worker pytest`),
que es donde están las dependencias. Ver README del repo.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for ruta in (REPO / "worker", REPO / "backend" / "app"):
    sys.path.insert(0, str(ruta))
