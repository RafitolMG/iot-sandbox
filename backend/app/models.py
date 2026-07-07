"""Modelo de datos (SQLAlchemy 2.0 declarativo) — completo en CP-3.

Modelo relacional de una muestra y su análisis dinámico:

    sample 1───* syscall_event   (trazas de strace)
           1───* network_flow    (flujos IP agregados del pcap)
           1───* fs_event        (eventos de inotify)
           1───* ioc             (indicadores extraídos, deduplicados por muestra)

Todas las tablas hijas referencian `sample.id` con ON DELETE CASCADE. La DDL la
gestiona Alembic (revisión 0002); esta clase declarativa es la fuente de verdad del
esquema para la API y para `alembic --autogenerate`.
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarativa compartida (metadata para Alembic)."""


class Sample(Base):
    """Una muestra subida para análisis dinámico."""

    __tablename__ = "sample"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    arch: Mapped[str] = mapped_column(String(32), default="arm")
    # queued -> running -> done | failed
    status: Mapped[str] = mapped_column(String(32), default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    syscall_events: Mapped[list["SyscallEvent"]] = relationship(
        back_populates="sample", cascade="all, delete-orphan", passive_deletes=True
    )
    network_flows: Mapped[list["NetworkFlow"]] = relationship(
        back_populates="sample", cascade="all, delete-orphan", passive_deletes=True
    )
    fs_events: Mapped[list["FsEvent"]] = relationship(
        back_populates="sample", cascade="all, delete-orphan", passive_deletes=True
    )
    iocs: Mapped[list["Ioc"]] = relationship(
        back_populates="sample", cascade="all, delete-orphan", passive_deletes=True
    )


class SyscallEvent(Base):
    """Una llamada al sistema observada en `strace.log`."""

    __tablename__ = "syscall_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(
        ForeignKey("sample.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)          # orden de aparición
    ts: Mapped[str | None] = mapped_column(String(32), nullable=True)   # HH:MM:SS.ffffff
    name: Mapped[str] = mapped_column(String(64), index=True)
    args: Mapped[str | None] = mapped_column(Text, nullable=True)       # argumentos resumidos
    result: Mapped[str | None] = mapped_column(String(128), nullable=True)  # valor de retorno

    sample: Mapped["Sample"] = relationship(back_populates="syscall_events")


class NetworkFlow(Base):
    """Un flujo de red agregado (por 4-tupla) extraído de `capture.pcap`."""

    __tablename__ = "network_flow"

    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(
        ForeignKey("sample.id", ondelete="CASCADE"), index=True
    )
    proto: Mapped[str] = mapped_column(String(16))     # tcp | udp | dns | icmp
    src: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dst: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dport: Mapped[int | None] = mapped_column(Integer, nullable=True)
    packets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    info: Mapped[str | None] = mapped_column(Text, nullable=True)       # p.ej. dominio DNS

    sample: Mapped["Sample"] = relationship(back_populates="network_flows")


class FsEvent(Base):
    """Un evento de sistema de ficheros observado por inotify (`fs_events.log`)."""

    __tablename__ = "fs_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(
        ForeignKey("sample.id", ondelete="CASCADE"), index=True
    )
    ts: Mapped[str | None] = mapped_column(String(32), nullable=True)
    op: Mapped[str] = mapped_column(String(64))        # CREATE, MODIFY, ATTRIB, ...
    path: Mapped[str] = mapped_column(Text)

    sample: Mapped["Sample"] = relationship(back_populates="fs_events")


class Ioc(Base):
    """Indicador de compromiso deduplicado por muestra."""

    __tablename__ = "ioc"
    __table_args__ = (
        UniqueConstraint("sample_id", "type", "value", name="uq_ioc_sample_type_value"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(
        ForeignKey("sample.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(16))      # ip | domain | file | port | hash
    value: Mapped[str] = mapped_column(String(1024))
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)  # strace|pcap|fs

    sample: Mapped["Sample"] = relationship(back_populates="iocs")
