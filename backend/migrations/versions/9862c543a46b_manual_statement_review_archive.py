"""manual statement review archive

Revision ID: 9862c543a46b
Revises: 2d826d48220b
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "9862c543a46b"
down_revision: str | None = "2d826d48220b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "statement_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("data_identity", sa.String(length=16), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_statement_reviews_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name=op.f("fk_statement_reviews_shop_id_shops")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_statement_reviews")),
    )
    op.create_index(
        op.f("ix_statement_reviews_owner_id"), "statement_reviews", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_statement_reviews_shop_id"), "statement_reviews", ["shop_id"], unique=False
    )
    op.create_table(
        "statement_review_expenses",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            name=op.f("fk_statement_review_expenses_expense_id_expenses"),
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["statement_reviews.id"],
            name=op.f("fk_statement_review_expenses_review_id_statement_reviews"),
        ),
        sa.PrimaryKeyConstraint(
            "review_id", "expense_id", name=op.f("pk_statement_review_expenses")
        ),
    )
    op.create_index(
        op.f("ix_statement_review_expenses_expense_id"),
        "statement_review_expenses",
        ["expense_id"],
        unique=False,
    )
    op.create_table(
        "statement_review_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("snapshot", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_statement_review_revisions_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["statement_reviews.id"],
            name=op.f("fk_statement_review_revisions_review_id_statement_reviews"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_statement_review_revisions")),
        sa.UniqueConstraint("owner_id", "request_id", name="uq_statement_review_request"),
        sa.UniqueConstraint("review_id", "version", name="uq_statement_review_version"),
    )
    op.create_index(
        op.f("ix_statement_review_revisions_owner_id"),
        "statement_review_revisions",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_statement_review_revisions_review_id"),
        "statement_review_revisions",
        ["review_id"],
        unique=False,
    )
    op.create_table(
        "statement_review_rules",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["statement_reviews.id"],
            name=op.f("fk_statement_review_rules_review_id_statement_reviews"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["fee_rules.id"], name=op.f("fk_statement_review_rules_rule_id_fee_rules")
        ),
        sa.PrimaryKeyConstraint("review_id", "rule_id", name=op.f("pk_statement_review_rules")),
    )
    op.create_index(
        op.f("ix_statement_review_rules_rule_id"),
        "statement_review_rules",
        ["rule_id"],
        unique=False,
    )
    op.create_table(
        "statement_review_sources",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["import_batches.id"],
            name=op.f("fk_statement_review_sources_batch_id_import_batches"),
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["statement_reviews.id"],
            name=op.f("fk_statement_review_sources_review_id_statement_reviews"),
        ),
        sa.PrimaryKeyConstraint("review_id", "batch_id", name=op.f("pk_statement_review_sources")),
    )
    op.create_index(
        op.f("ix_statement_review_sources_batch_id"),
        "statement_review_sources",
        ["batch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("statement_review_sources")
    op.drop_table("statement_review_rules")
    op.drop_table("statement_review_revisions")
    op.drop_table("statement_review_expenses")
    op.drop_table("statement_reviews")
