"""Motor y sesiones SQLAlchemy async (asyncpg).

La lógica de persistencia real (guardar muestras/IoCs) llega en CP-3; aquí solo se deja
el motor listo para que la API tenga conexión async a PostgreSQL.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Dependencia FastAPI para obtener una sesión async (se usa a partir de CP-3)."""
    async with AsyncSessionLocal() as session:
        yield session
