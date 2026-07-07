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


settings = Settings()
