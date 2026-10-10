"""Bind human review to reply versions and retain reported channel actions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "d93f6b210ac4"
down_revision = "c84a06e31bd2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reply_drafts", sa.Column("reviewed_version", sa.Integer(), nullable=True))
    op.add_column("reply_drafts", sa.Column("reviewed_at", mysql.DATETIME(fsp=6), nullable=True))
    op.add_column("reply_drafts", sa.Column("reviewed_language", sa.String(10), nullable=True))
    op.create_table(
        "reply_manual_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("reply_drafts.id"), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("occurred_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("recorded_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("payload", sa.JSON(none_as_null=True), nullable=True),
        sa.UniqueConstraint("draft_id", "request_key", name="uq_reply_manual_request"),
    )
    for column in ("owner_id", "shop_id", "draft_id"):
        op.create_index(f"ix_reply_manual_actions_{column}", "reply_manual_actions", [column])


def downgrade() -> None:
    connection = op.get_bind()
    if (
        connection.scalar(sa.text("SELECT 1 FROM reply_manual_actions LIMIT 1"))
        or connection.scalar(
            sa.text("SELECT 1 FROM reply_drafts WHERE reviewed_version IS NOT NULL LIMIT 1")
        )
        or connection.scalar(
            sa.text("SELECT 1 FROM audit_events WHERE action = 'support.reply_reviewed' LIMIT 1")
        )
    ):
        raise RuntimeError("存在客服审阅或人工证据历史，请备份并保留当前结构，不能降级删除")
    op.drop_table("reply_manual_actions")
    op.drop_column("reply_drafts", "reviewed_language")
    op.drop_column("reply_drafts", "reviewed_at")
    op.drop_column("reply_drafts", "reviewed_version")
