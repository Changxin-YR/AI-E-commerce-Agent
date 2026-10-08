"""add controlled test mail delivery

Revision ID: f219af0a01cf
Revises: 3b35be067576
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "f219af0a01cf"
down_revision: str | None = "3b35be067576"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_mail_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("sender", sa.String(length=254), nullable=False),
        sa.Column("recipient", sa.String(length=254), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("verification_hash", sa.String(length=64), nullable=False),
        sa.Column("verification_attempts", sa.Integer(), nullable=False),
        sa.Column("verification_expires_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("verified_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("revoked_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("receipt_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_test_mail_channels_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name=op.f("fk_test_mail_channels_shop_id_shops")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_mail_channels")),
    )
    op.create_index(
        op.f("ix_test_mail_channels_owner_id"), "test_mail_channels", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_test_mail_channels_shop_id"), "test_mail_channels", ["shop_id"], unique=False
    )
    op.create_table(
        "outbound_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("dispatch_key", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("source_status", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("dispatch_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("receipt_id", sa.String(length=36), nullable=True),
        sa.Column("provider_event", sa.String(length=32), nullable=False),
        sa.Column("checked_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("received_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("receipt_evidence", sa.String(length=500), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["test_mail_channels.id"],
            name=op.f("fk_outbound_messages_channel_id_test_mail_channels"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_outbound_messages_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["operation_runs.id"],
            name=op.f("fk_outbound_messages_run_id_operation_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name=op.f("fk_outbound_messages_shop_id_shops")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbound_messages")),
        sa.UniqueConstraint("dedupe_key", name="uq_outbound_effect"),
        sa.UniqueConstraint("dispatch_key", name=op.f("uq_outbound_messages_dispatch_key")),
    )
    op.create_index(
        op.f("ix_outbound_messages_owner_id"), "outbound_messages", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_outbound_messages_run_id"), "outbound_messages", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_outbound_messages_shop_id"), "outbound_messages", ["shop_id"], unique=False
    )
    op.create_table(
        "outbound_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("message_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("expires_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("used_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("revoked_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["outbound_messages.id"],
            name=op.f("fk_outbound_approvals_message_id_outbound_messages"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_outbound_approvals_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name=op.f("fk_outbound_approvals_shop_id_shops")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbound_approvals")),
    )
    op.create_index(
        op.f("ix_outbound_approvals_message_id"), "outbound_approvals", ["message_id"], unique=False
    )
    op.create_index(
        op.f("ix_outbound_approvals_owner_id"), "outbound_approvals", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_outbound_approvals_shop_id"), "outbound_approvals", ["shop_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("outbound_approvals")
    op.drop_table("outbound_messages")
    op.drop_table("test_mail_channels")
