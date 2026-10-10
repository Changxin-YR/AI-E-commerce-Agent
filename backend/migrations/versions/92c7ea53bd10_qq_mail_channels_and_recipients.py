"""Record mail provider and per-message recipient.

Revision ID: 92c7ea53bd10
Revises: 7e7851694067
"""

import sqlalchemy as sa
from alembic import op

revision = "92c7ea53bd10"
down_revision = "7e7851694067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_mail_channels",
        sa.Column("provider", sa.String(16), nullable=False, server_default="resend"),
    )
    # Historical messages resolve their recipient from the original channel.
    op.add_column("outbound_messages", sa.Column("recipient", sa.String(254), nullable=True))


def downgrade() -> None:
    op.drop_column("outbound_messages", "recipient")
    op.drop_column("test_mail_channels", "provider")
