from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business_rules import BusinessRuleRevision


class BusinessRulesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def revisions(
        self,
        owner: int,
        shop: int,
        channel: str,
        identity: str,
        before: int | None = None,
        limit: int = 50,
    ) -> list[BusinessRuleRevision]:
        statement = select(BusinessRuleRevision).where(
            BusinessRuleRevision.owner_id == owner,
            BusinessRuleRevision.shop_id == shop,
            BusinessRuleRevision.channel == channel,
            BusinessRuleRevision.data_identity == identity,
        )
        if before is not None:
            statement = statement.where(BusinessRuleRevision.id < before)
        return list(
            self.session.scalars(
                statement.order_by(BusinessRuleRevision.id.desc())
                .limit(limit)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def find(self, owner: int, shop: int, revision: int) -> BusinessRuleRevision | None:
        return self.session.scalar(
            select(BusinessRuleRevision)
            .where(
                BusinessRuleRevision.owner_id == owner,
                BusinessRuleRevision.shop_id == shop,
                BusinessRuleRevision.id == revision,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def add(self, revision: BusinessRuleRevision) -> None:
        self.session.add(revision)
        self.session.flush()
