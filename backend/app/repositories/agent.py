from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.agent import AgentExecution, AgentPolicySource, AgentSource, AgentStep
from app.models.listings import ListingSource, ListingVersion


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, item: AgentExecution | AgentStep) -> None:
        self.session.add(item)
        self.session.flush()

    def get(self, owner: int, shop: int, execution_id: int) -> AgentExecution | None:
        return self.session.scalar(
            select(AgentExecution)
            .where(
                AgentExecution.owner_id == owner,
                AgentExecution.shop_id == shop,
                AgentExecution.id == execution_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def by_request(self, owner: int, request: str) -> AgentExecution | None:
        return self.session.scalar(
            select(AgentExecution)
            .where(
                AgentExecution.owner_id == owner,
                AgentExecution.request_id == request,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def executions(self, owner: int, shop: int) -> list[AgentExecution]:
        return list(
            self.session.scalars(
                select(AgentExecution)
                .where(
                    AgentExecution.owner_id == owner,
                    AgentExecution.shop_id == shop,
                )
                .order_by(AgentExecution.id.desc())
                .limit(50)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def steps(self, execution_id: int) -> list[AgentStep]:
        return list(
            self.session.scalars(
                select(AgentStep)
                .where(
                    AgentStep.execution_id == execution_id,
                )
                .order_by(AgentStep.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def sources(self, execution_id: int, batches: set[int], policies: set[int]) -> None:
        existing = set(
            self.session.scalars(
                select(AgentSource.batch_id)
                .where(
                    AgentSource.execution_id == execution_id,
                )
                .with_for_update()
            )
        )
        self.session.add_all(
            [AgentSource(execution_id=execution_id, batch_id=b) for b in batches - existing]
        )
        current = set(
            self.session.scalars(
                select(AgentPolicySource.policy_id)
                .where(
                    AgentPolicySource.execution_id == execution_id,
                )
                .with_for_update()
            )
        )
        self.session.add_all(
            [AgentPolicySource(execution_id=execution_id, policy_id=p) for p in policies - current]
        )

    def invalidate(self, owner: int, shop: int) -> None:
        self.session.execute(
            update(AgentExecution)
            .where(
                AgentExecution.owner_id == owner,
                AgentExecution.shop_id == shop,
                AgentExecution.source_status == "current",
            )
            .values(source_status="stale", version=AgentExecution.version + 1)
        )

    def listing_sources(self, execution_id: int, listing: int, owner: int, shop: int) -> None:
        batches = set(
            self.session.scalars(
                select(ListingSource.batch_id)
                .join(ListingVersion)
                .where(
                    ListingVersion.id == listing,
                    ListingVersion.owner_id == owner,
                    ListingVersion.shop_id == shop,
                )
                .with_for_update()
            )
        )
        self.sources(execution_id, batches, set())

    def expire(self, owner: int, shop: int, now: datetime) -> None:
        self.session.execute(
            update(AgentExecution)
            .where(
                AgentExecution.owner_id == owner,
                AgentExecution.shop_id == shop,
                AgentExecution.source_status == "current",
                AgentExecution.valid_until <= now,
            )
            .values(source_status="stale", version=AgentExecution.version + 1)
        )

    def purge_batch(self, owner: int, shop: int, batch: int) -> None:
        ids = list(
            self.session.scalars(
                select(AgentExecution.id)
                .join(AgentSource)
                .where(
                    AgentExecution.owner_id == owner,
                    AgentExecution.shop_id == shop,
                    AgentSource.batch_id == batch,
                )
                .with_for_update()
            )
        )
        self._purge(ids)

    def purge_policy(self, owner: int, shop: int, policy: int) -> None:
        ids = list(
            self.session.scalars(
                select(AgentExecution.id)
                .join(AgentPolicySource)
                .where(
                    AgentExecution.owner_id == owner,
                    AgentExecution.shop_id == shop,
                    AgentPolicySource.policy_id == policy,
                )
                .with_for_update()
            )
        )
        self._purge(ids)

    def _purge(self, ids: list[int]) -> None:
        if not ids:
            return
        self.session.execute(
            update(AgentExecution)
            .where(AgentExecution.id.in_(ids))
            .values(
                input=None,
                result=None,
                source_status="cleared",
                status="blocked",
                reason="source_cleared",
                valid_until=None,
                version=AgentExecution.version + 1,
            )
        )
        self.session.execute(
            update(AgentStep)
            .where(AgentStep.execution_id.in_(ids))
            .values(
                input=None,
                output=None,
            )
        )
        self.session.execute(delete(AgentSource).where(AgentSource.execution_id.in_(ids)))
        self.session.execute(
            delete(AgentPolicySource).where(AgentPolicySource.execution_id.in_(ids))
        )
