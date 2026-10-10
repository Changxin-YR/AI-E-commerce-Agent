"""Evidence-based follow-up of the original operation task."""

import sqlalchemy as sa
from alembic import op

revision = "c84a06e31bd2"
down_revision = "b37e820ca491"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operation_tasks", sa.Column("review", sa.JSON(none_as_null=True), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT 1 FROM operation_tasks WHERE review IS NOT NULL LIMIT 1")
    ) or connection.scalar(
        sa.text(
            "SELECT 1 FROM operation_task_events "
            "WHERE action IN ('record_evidence', 'wait_source', 'recheck') LIMIT 1"
        )
    ):
        raise RuntimeError("存在事项复核或审计历史；请备份并保留当前结构，不能通过降级删除复核依据")
    op.drop_column("operation_tasks", "review")
