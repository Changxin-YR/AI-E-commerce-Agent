"""Add isolated mobile session metadata to existing indexed sessions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "a31e72d405bf"
down_revision = "d93f6b210ac4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "login_sessions",
        sa.Column("client_type", sa.String(16), nullable=False, server_default="web"),
    )
    op.add_column("login_sessions", sa.Column("device_session_id", sa.String(32), nullable=True))
    op.add_column("login_sessions", sa.Column("issued_at", mysql.DATETIME(fsp=6), nullable=True))
    op.add_column("login_sessions", sa.Column("last_used_at", mysql.DATETIME(fsp=6), nullable=True))
    op.create_unique_constraint(
        "uq_login_sessions_device_session_id", "login_sessions", ["device_session_id"]
    )


def downgrade() -> None:
    # Mobile tokens must cease working when the transport distinction is removed.
    op.execute("DELETE FROM login_sessions WHERE client_type <> 'web'")
    op.drop_constraint("uq_login_sessions_device_session_id", "login_sessions", type_="unique")
    for column in ("last_used_at", "issued_at", "device_session_id", "client_type"):
        op.drop_column("login_sessions", column)
