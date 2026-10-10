"""Bounded file import groups and recoverable parts.

Revision ID: a12c4b907e61
Revises: 92c7ea53bd10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "a12c4b907e61"
down_revision = "92c7ea53bd10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source_channel", sa.String(20), nullable=False),
        sa.Column("data_identity", sa.String(20), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
    )
    for field in ("owner_id", "shop_id", "request_key"):
        op.create_index(f"ix_import_groups_{field}", "import_groups", [field])
    op.add_column("import_batches", sa.Column("group_id", sa.Integer(), nullable=True))
    op.add_column("import_batches", sa.Column("group_part", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_import_batches_group", "import_batches", "import_groups", ["group_id"], ["id"]
    )
    op.create_index("ix_import_batches_group_id", "import_batches", ["group_id"])


def downgrade() -> None:
    active = op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM import_groups WHERE status = 'active'")
    )
    if active:
        raise RuntimeError("存在活动导入组；请先在当前版本核对并撤销整组，再降级以保留覆盖保护")
    op.drop_constraint("fk_import_batches_group", "import_batches", type_="foreignkey")
    op.drop_index("ix_import_batches_group_id", table_name="import_batches")
    op.drop_column("import_batches", "group_part")
    op.drop_column("import_batches", "group_id")
    op.drop_table("import_groups")
