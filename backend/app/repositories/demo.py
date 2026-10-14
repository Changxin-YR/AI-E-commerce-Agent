from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import AuditEvent


class DemoRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def initialized(self, owner: int, action: str, resource_id: int) -> bool:
        return (
            self.session.scalar(
                select(AuditEvent.id)
                .where(
                    AuditEvent.actor_id == owner,
                    AuditEvent.action == action,
                    AuditEvent.resource_id == str(resource_id),
                )
                .limit(1)
            )
            is not None
        )
