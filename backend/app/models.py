"""Modelo de datos (SQLAlchemy 2.0 declarativo).

CP-1 solo define la tabla `sample` (mínima). El resto del modelo (syscall_event,
network_flow, fs_event, ioc) se añade en CP-3 — ver docs/ARCHITECTURE.md.
"""
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa compartida (metadata para Alembic)."""


class Sample(Base):
    """Una muestra subida para análisis dinámico.

    Campos según el borrador de docs/ARCHITECTURE.md; se refinará en CP-3
    (finished_at, relaciones con eventos/IoCs, etc.).
    """

    __tablename__ = "sample"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    arch: Mapped[str] = mapped_column(String(32), default="arm")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
