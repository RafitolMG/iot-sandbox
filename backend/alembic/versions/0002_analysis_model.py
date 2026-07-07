"""analysis model: syscall_event, network_flow, fs_event, ioc + sample columns

Revision ID: 0002_analysis_model
Revises: 0001_initial
Create Date: 2026-07-07

CP-3: completa el modelo de datos del análisis dinámico. Añade a `sample` las
columnas `size_bytes`, `error` y `finished_at`, y crea las cuatro tablas hijas
(syscall_event, network_flow, fs_event, ioc) con FK ON DELETE CASCADE.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_analysis_model"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- sample: columnas que faltaban ------------------------------------
    op.add_column("sample", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("sample", sa.Column("error", sa.Text(), nullable=True))
    op.add_column(
        "sample", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
    )

    # --- syscall_event ----------------------------------------------------
    op.create_table(
        "syscall_event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sample_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("ts", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("args", sa.Text(), nullable=True),
        sa.Column("result", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["sample_id"], ["sample.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_syscall_event_sample_id", "syscall_event", ["sample_id"])
    op.create_index("ix_syscall_event_name", "syscall_event", ["name"])

    # --- network_flow -----------------------------------------------------
    op.create_table(
        "network_flow",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sample_id", sa.Integer(), nullable=False),
        sa.Column("proto", sa.String(length=16), nullable=False),
        sa.Column("src", sa.String(length=64), nullable=True),
        sa.Column("dst", sa.String(length=64), nullable=True),
        sa.Column("dport", sa.Integer(), nullable=True),
        sa.Column("packets", sa.Integer(), nullable=True),
        sa.Column("bytes", sa.BigInteger(), nullable=True),
        sa.Column("info", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["sample_id"], ["sample.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_network_flow_sample_id", "network_flow", ["sample_id"])

    # --- fs_event ---------------------------------------------------------
    op.create_table(
        "fs_event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sample_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.String(length=32), nullable=True),
        sa.Column("op", sa.String(length=64), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["sample_id"], ["sample.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_fs_event_sample_id", "fs_event", ["sample_id"])

    # --- ioc (deduplicado por muestra) ------------------------------------
    op.create_table(
        "ioc",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sample_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("value", sa.String(length=1024), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["sample_id"], ["sample.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "sample_id", "type", "value", name="uq_ioc_sample_type_value"
        ),
    )
    op.create_index("ix_ioc_sample_id", "ioc", ["sample_id"])


def downgrade() -> None:
    op.drop_index("ix_ioc_sample_id", table_name="ioc")
    op.drop_table("ioc")
    op.drop_index("ix_fs_event_sample_id", table_name="fs_event")
    op.drop_table("fs_event")
    op.drop_index("ix_network_flow_sample_id", table_name="network_flow")
    op.drop_table("network_flow")
    op.drop_index("ix_syscall_event_name", table_name="syscall_event")
    op.drop_index("ix_syscall_event_sample_id", table_name="syscall_event")
    op.drop_table("syscall_event")
    op.drop_column("sample", "finished_at")
    op.drop_column("sample", "error")
    op.drop_column("sample", "size_bytes")
