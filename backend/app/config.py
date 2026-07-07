"""Configuración de la API (pydantic-settings).

Lee la configuración de variables de entorno (inyectadas por docker-compose). Los nombres
de campo se mapean de forma case-insensitive: p. ej. DATABASE_URL -> database_url.
"""
from pydantic import field_validator
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

    # Arquitecturas soportadas (con perfil + rootfs construido) — CP-6.
    # Cada una tiene un perfil en emulation/profiles/<arch>.env. Se usa como gate del
    # endpoint POST /samples (autodetección ELF o `arch` explícito). Overridable por env
    # SUPPORTED_ARCHES="arm,mips,mipsel,x86_64" (lista separada por comas).
    supported_arches: tuple[str, ...] = ("arm", "mips", "mipsel", "x86_64")

    @field_validator("supported_arches", mode="before")
    @classmethod
    def _split_arches(cls, v):
        """Permite override por env como cadena separada por comas: "arm,mips"."""
        if isinstance(v, str):
            return tuple(a.strip().lower() for a in v.split(",") if a.strip())
        return v


settings = Settings()
