"""Capa de persistencia del worker (SQLAlchemy Core, SÍNCRONA).

Las tareas Celery son síncronas, así que el worker usa un engine SÍNCRONO (psycopg 3)
en lugar del asyncpg de la API. La DDL la posee Alembic (lado API, ADR-015); aquí solo
se declaran las tablas como objetos Core para INSERT/UPDATE, manteniendo el desacoplo
API↔worker (comparten broker + base de datos, no código).

La `DATABASE_URL` que inyecta compose usa el driver async (`postgresql+asyncpg://`);
se reescribe al driver sync (`postgresql+psycopg://`) para este proceso.
"""
import os

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
)

_ASYNC_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://sandbox:sandbox@db:5432/sandbox"
)
# asyncpg -> psycopg (sync). Si ya viniera sync, se deja tal cual.
SYNC_URL = _ASYNC_URL.replace("+asyncpg", "+psycopg")

engine = create_engine(SYNC_URL, future=True, pool_pre_ping=True)

metadata = MetaData()

sample = Table(
    "sample", metadata,
    Column("id", Integer, primary_key=True),
    Column("filename", String(512)),
    Column("sha256", String(64)),
    Column("size_bytes", BigInteger),
    Column("arch", String(32)),
    Column("status", String(32)),
    Column("error", Text),
    Column("created_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
)

syscall_event = Table(
    "syscall_event", metadata,
    Column("id", Integer, primary_key=True),
    Column("sample_id", Integer),
    Column("seq", Integer),
    Column("ts", String(32)),
    Column("name", String(64)),
    Column("args", Text),
    Column("result", String(128)),
)

network_flow = Table(
    "network_flow", metadata,
    Column("id", Integer, primary_key=True),
    Column("sample_id", Integer),
    Column("proto", String(16)),
    Column("src", String(64)),
    Column("dst", String(64)),
    Column("dport", Integer),
    Column("packets", Integer),
    Column("bytes", BigInteger),
    Column("info", Text),
)

fs_event = Table(
    "fs_event", metadata,
    Column("id", Integer, primary_key=True),
    Column("sample_id", Integer),
    Column("ts", String(32)),
    Column("op", String(64)),
    Column("path", Text),
)

ioc = Table(
    "ioc", metadata,
    Column("id", Integer, primary_key=True),
    Column("sample_id", Integer),
    Column("type", String(16)),
    Column("value", String(1024)),
    Column("source", String(32)),
    UniqueConstraint("sample_id", "type", "value", name="uq_ioc_sample_type_value"),
)
