"""versioned manual fee mapping rules

Revision ID: 2d826d48220b
Revises: d32312391696
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "2d826d48220b"
down_revision: str | None = "d32312391696"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fee_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("data_identity", sa.String(length=16), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("match_key", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_fee_rules_owner_id_users")
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], name=op.f("fk_fee_rules_shop_id_shops")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fee_rules")),
        sa.UniqueConstraint(
            "shop_id", "data_identity", "channel", "match_key", name="uq_fee_rule_match"
        ),
    )
    op.create_index(op.f("ix_fee_rules_owner_id"), "fee_rules", ["owner_id"], unique=False)
    op.create_index(op.f("ix_fee_rules_shop_id"), "fee_rules", ["shop_id"], unique=False)
    op.create_table(
        "fee_rule_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("content", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_fee_rule_revisions_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["fee_rules.id"], name=op.f("fk_fee_rule_revisions_rule_id_fee_rules")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fee_rule_revisions")),
        sa.UniqueConstraint("owner_id", "request_id", name="uq_fee_rule_request"),
        sa.UniqueConstraint("rule_id", "version", name="uq_fee_rule_version"),
    )
    op.create_index(
        op.f("ix_fee_rule_revisions_owner_id"), "fee_rule_revisions", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_fee_rule_revisions_rule_id"), "fee_rule_revisions", ["rule_id"], unique=False
    )


def downgrade() -> None:
    # MySQL keeps indexes supporting foreign keys until the dependent table is dropped.
    op.drop_table("fee_rule_revisions")
    op.drop_table("fee_rules")
