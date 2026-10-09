"""Distinguish file imports and human product edits in source evidence.

Revision ID: d6f920a41b85
Revises: c5e81a209d74
"""

import sqlalchemy as sa
from alembic import op

revision = "d6f920a41b85"
down_revision = "c5e81a209d74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("origin", sa.String(20), server_default="file_import", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("import_batches", "origin")
