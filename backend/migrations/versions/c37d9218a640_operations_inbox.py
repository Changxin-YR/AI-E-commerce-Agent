"""Persist operations checks, evidence, and task dispositions.

Revision ID: c37d9218a640
Revises: 61cb82ef096a
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "c37d9218a640"
down_revision = "61cb82ef096a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("source_status", sa.String(16), nullable=False),
        sa.Column("snapshot", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("valid_until", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.UniqueConstraint("owner_id", "request_id", name="uq_operation_request"),
    )
    op.create_table(
        "operation_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("dedupe_key", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("data_identity", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("source_status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("due_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("valid_until", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.UniqueConstraint("owner_id", "dedupe_key", name="uq_operation_task"),
    )
    for table in ("operation_runs", "operation_tasks"):
        for column in ("owner_id", "shop_id"):
            op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_table(
        "operation_run_sources",
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("operation_runs.id"), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), primary_key=True),
    )
    op.create_table(
        "operation_task_sources",
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("operation_tasks.id"), primary_key=True),
        sa.Column("row_id", sa.Integer(), sa.ForeignKey("import_rows.id"), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), nullable=False),
    )
    op.create_index("ix_operation_task_sources_batch_id", "operation_task_sources", ["batch_id"])
    op.create_table(
        "operation_task_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("operation_tasks.id"), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("from_status", sa.String(24), nullable=False),
        sa.Column("to_status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("details", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
    )
    op.create_index("ix_operation_task_events_task_id", "operation_task_events", ["task_id"])


def downgrade() -> None:
    for table in (
        "operation_task_events",
        "operation_task_sources",
        "operation_run_sources",
        "operation_tasks",
        "operation_runs",
    ):
        op.drop_table(table)
