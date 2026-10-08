"""add cross shop overview reports

Revision ID: 728544d1186c
Revises: f219af0a01cf
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision: str = "728544d1186c"
down_revision: str | None = "f219af0a01cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "overview_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("snapshot", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("valid_until", DATETIME(fsp=6), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_overview_reports_owner_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_overview_reports")),
        sa.UniqueConstraint("owner_id", "request_id", name="uq_overview_request"),
    )
    op.create_index(
        op.f("ix_overview_reports_owner_id"), "overview_reports", ["owner_id"], unique=False
    )
    op.create_table(
        "overview_shops",
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["overview_reports.id"],
            name=op.f("fk_overview_shops_report_id_overview_reports"),
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name=op.f("fk_overview_shops_shop_id_shops")
        ),
        sa.PrimaryKeyConstraint("report_id", "shop_id", name=op.f("pk_overview_shops")),
    )
    op.create_index(op.f("ix_overview_shops_shop_id"), "overview_shops", ["shop_id"], unique=False)
    op.create_table(
        "overview_sources",
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["import_batches.id"],
            name=op.f("fk_overview_sources_batch_id_import_batches"),
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["overview_reports.id"],
            name=op.f("fk_overview_sources_report_id_overview_reports"),
        ),
        sa.PrimaryKeyConstraint("report_id", "batch_id", name=op.f("pk_overview_sources")),
    )
    op.create_index(
        op.f("ix_overview_sources_batch_id"), "overview_sources", ["batch_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("overview_sources")
    op.drop_table("overview_shops")
    op.drop_table("overview_reports")
