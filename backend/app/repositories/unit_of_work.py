from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.identity import AuditEvent
from app.repositories.analytics import AnalyticsRepository
from app.repositories.identity import IdentityRepository
from app.repositories.imports import ImportRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.listings import ListingRepository
from app.repositories.support import SupportRepository


class UnitOfWork:
    """One request owns one session; business services choose the commit boundary."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.identity = IdentityRepository(session)
        self.imports = ImportRepository(session)
        self.inventory = InventoryRepository(session)
        self.analytics = AnalyticsRepository(session)
        self.listings = ListingRepository(session)
        self.support = SupportRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def record_event(
        self,
        actor_id: int,
        action: str,
        resource_type: str,
        resource_id: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            AuditEvent(
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id),
                details=details or {},
            )
        )

    def ping(self) -> None:
        self.session.execute(text("SELECT 1"))
