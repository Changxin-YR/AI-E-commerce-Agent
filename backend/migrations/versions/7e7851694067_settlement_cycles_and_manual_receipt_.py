"""settlement cycles and manual receipt evidence

Revision ID: 7e7851694067
Revises: 9862c543a46b
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "7e7851694067"
down_revision: str | None = "9862c543a46b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("data_identity", sa.String(length=16), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("statement_key", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_settlements_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name=op.f("fk_settlements_shop_id_shops")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settlements")),
        sa.UniqueConstraint(
            "owner_id",
            "shop_id",
            "data_identity",
            "channel",
            "statement_key",
            name="uq_settlement_statement",
        ),
    )
    op.create_index(op.f("ix_settlements_owner_id"), "settlements", ["owner_id"], unique=False)
    op.create_index(op.f("ix_settlements_shop_id"), "settlements", ["shop_id"], unique=False)
    op.create_table(
        "settlement_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("settlement_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("snapshot", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_settlement_revisions_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["settlement_id"],
            ["settlements.id"],
            name=op.f("fk_settlement_revisions_settlement_id_settlements"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settlement_revisions")),
        sa.UniqueConstraint("owner_id", "request_id", name="uq_settlement_request"),
        sa.UniqueConstraint("settlement_id", "version", name="uq_settlement_version"),
    )
    op.create_index(
        op.f("ix_settlement_revisions_owner_id"), "settlement_revisions", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_settlement_revisions_settlement_id"),
        "settlement_revisions",
        ["settlement_id"],
        unique=False,
    )
    op.create_table(
        "settlement_sources",
        sa.Column("settlement_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["import_batches.id"],
            name=op.f("fk_settlement_sources_batch_id_import_batches"),
        ),
        sa.ForeignKeyConstraint(
            ["settlement_id"],
            ["settlements.id"],
            name=op.f("fk_settlement_sources_settlement_id_settlements"),
        ),
        sa.PrimaryKeyConstraint("settlement_id", "batch_id", name=op.f("pk_settlement_sources")),
    )
    op.create_index(
        op.f("ix_settlement_sources_batch_id"), "settlement_sources", ["batch_id"], unique=False
    )
    op.create_table(
        "settlement_receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("settlement_id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("data_identity", sa.String(length=16), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("receipt_key", sa.String(length=64), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("received_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_settlement_receipts_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["settlement_revisions.id"],
            name=op.f("fk_settlement_receipts_revision_id_settlement_revisions"),
        ),
        sa.ForeignKeyConstraint(
            ["settlement_id"],
            ["settlements.id"],
            name=op.f("fk_settlement_receipts_settlement_id_settlements"),
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name=op.f("fk_settlement_receipts_shop_id_shops")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settlement_receipts")),
        sa.UniqueConstraint(
            "owner_id",
            "shop_id",
            "data_identity",
            "channel",
            "receipt_key",
            name="uq_settlement_receipt",
        ),
        sa.UniqueConstraint("revision_id", "position", name="uq_settlement_receipt_position"),
    )
    op.create_index(
        op.f("ix_settlement_receipts_owner_id"), "settlement_receipts", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_settlement_receipts_revision_id"),
        "settlement_receipts",
        ["revision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_settlement_receipts_settlement_id"),
        "settlement_receipts",
        ["settlement_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_settlement_receipts_shop_id"), "settlement_receipts", ["shop_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("settlement_receipts")
    op.drop_table("settlement_sources")
    op.drop_table("settlement_revisions")
    op.drop_table("settlements")
