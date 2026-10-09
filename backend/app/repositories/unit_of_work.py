from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.identity import AuditEvent
from app.repositories.agent import AgentRepository
from app.repositories.analytics import AnalyticsRepository
from app.repositories.authorizations import AuthorizationsRepository
from app.repositories.business_rules import BusinessRulesRepository
from app.repositories.expenses import ExpenseRepository
from app.repositories.identity import IdentityRepository
from app.repositories.imports import ImportRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.listings import ListingRepository
from app.repositories.operations import OperationsRepository
from app.repositories.outbound import OutboundRepository
from app.repositories.overview import OverviewRepository
from app.repositories.product_edits import ProductEditRepository
from app.repositories.product_quality import ProductQualityRepository
from app.repositories.profit import ProfitRepository
from app.repositories.schedules import SchedulesRepository
from app.repositories.support import SupportRepository
from app.repositories.workbench import WorkbenchRepository


class UnitOfWork:
    """One request owns one session; business services choose the commit boundary."""

    def __init__(self, session: Session) -> None:
        self._defer_commits = 0
        self.session = session
        self.agent = AgentRepository(session)
        self.authorizations = AuthorizationsRepository(session)
        self.business_rules = BusinessRulesRepository(session)
        self.expenses = ExpenseRepository(session)
        self.identity = IdentityRepository(session)
        self.imports = ImportRepository(session)
        self.inventory = InventoryRepository(session)
        self.operations = OperationsRepository(session)
        self.outbound = OutboundRepository(session)
        self.overview = OverviewRepository(session)
        self.analytics = AnalyticsRepository(session)
        self.listings = ListingRepository(session)
        self.support = SupportRepository(session)
        self.profit = ProfitRepository(session)
        self.product_quality = ProductQualityRepository(session)
        self.product_edits = ProductEditRepository(session)
        self.schedules = SchedulesRepository(session)
        self.workbench = WorkbenchRepository(session)

    def commit(self) -> None:
        if not self._defer_commits:
            self.session.commit()
        else:
            self.session.flush()

    @property
    def commits_deferred(self) -> bool:
        return self._defer_commits > 0

    @contextmanager
    def defer_commits(self) -> Iterator[None]:
        """Compose controlled services and their execution record in one transaction."""
        self._defer_commits += 1
        try:
            yield
        finally:
            self._defer_commits -= 1

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
