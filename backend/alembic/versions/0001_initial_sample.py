"""initial: tabla sample

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-07

CP-1: crea la tabla mínima `sample`. El resto del modelo (syscall_event,
network_flow, fs_event, ioc) se añade en CP-3 (ver docs/ARCHITECTURE.md).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sample",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("arch", sa.String(length=32), nullable=False, server_default="arm"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_sample_sha256", "sample", ["sha256"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_sample_sha256", table_name="sample")
    op.drop_table("sample")
