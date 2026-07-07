"""Configuración de la API (pydantic-settings).

Lee la configuración de variables de entorno (inyectadas por docker-compose). Los nombres
de campo se mapean de forma case-insensitive: p. ej. DATABASE_URL -> database_url.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL (driver async asyncpg). Ver ADR-010.
    database_url: str = "postgresql+asyncpg://sandbox:sandbox@db:5432/sandbox"

    # Broker/cola. La imagen es Valkey 8 (ADR-011), pero el protocolo sigue siendo redis://.
    redis_url: str = "redis://valkey:6379/0"

    # Celery: broker (cola de tareas) y backend de resultados (índices de DB distintos).
    celery_broker_url: str = "redis://valkey:6379/0"
    celery_result_backend: str = "redis://valkey:6379/1"

    # Almacenamiento de muestras subidas (binarios NO confiables). Volumen `sample_storage`
    # montado en la API (rw) y en el worker (ro). Cada muestra se guarda como <sha256>.
    sample_storage_dir: str = "/data/samples"

    # Tamaño máximo de subida (bytes). 64 MiB por defecto (binarios IoT son pequeños).
    max_upload_bytes: int = 64 * 1024 * 1024

    # Arquitecturas soportadas (CP-3 solo ARM; MIPS/x86_64 en CP-6).
    supported_arches: tuple[str, ...] = ("arm",)


settings = Settings()
