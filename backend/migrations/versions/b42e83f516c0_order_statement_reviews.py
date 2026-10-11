"""Distinguish versioned fee and order statement reviews."""

import sqlalchemy as sa
from alembic import op

revision = "b42e83f516c0"
down_revision = "a31e72d405bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "statement_reviews",
        sa.Column("kind", sa.String(16), nullable=False, server_default="fees"),
    )


def downgrade() -> None:
    count = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM statement_reviews WHERE kind <> 'fees'")
    )
    if count:
        raise RuntimeError(
            "Order review records require an explicit export/removal before downgrade"
        )
    op.drop_column("statement_reviews", "kind")
