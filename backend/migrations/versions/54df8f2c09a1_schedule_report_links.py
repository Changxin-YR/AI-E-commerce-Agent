"""Link scheduled occurrences to persisted operating reports.

Revision ID: 54df8f2c09a1
Revises: a364d8b4b6bf
"""

import sqlalchemy as sa
from alembic import op

revision = "54df8f2c09a1"
down_revision = "a364d8b4b6bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schedule_occurrences",
        sa.Column("task", sa.String(16), nullable=False, server_default="operations"),
    )
    op.alter_column(
        "schedule_occurrences", "task", existing_type=sa.String(16), server_default=None
    )
    op.add_column("schedule_occurrences", sa.Column("report_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_schedule_occurrence_report",
        "schedule_occurrences",
        "overview_reports",
        ["report_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_schedule_occurrence_report", "schedule_occurrences", type_="foreignkey")
    op.drop_column("schedule_occurrences", "report_id")
    op.drop_column("schedule_occurrences", "task")
