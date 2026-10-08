"""version analysis todo transitions

Revision ID: 86df84dc129a
Revises: 728544d1186c
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "86df84dc129a"
down_revision: str | None = "728544d1186c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_todos", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("analysis_todos", "version")
