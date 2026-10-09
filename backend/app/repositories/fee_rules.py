from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fee_rules import FeeRule, FeeRuleRevision


class FeeRuleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def scope_revision(self, owner: int, shop: int, identity: str, channel: str) -> int:
        # Include withdrawn/cleared rules so restoring a rule set cannot restore an old preview.
        return (
            self.session.scalar(
                select(FeeRuleRevision.id)
                .join(FeeRule, FeeRuleRevision.rule_id == FeeRule.id)
                .where(
                    FeeRule.owner_id == owner,
                    FeeRule.shop_id == shop,
                    FeeRule.data_identity == identity,
                    FeeRule.channel == channel,
                    FeeRuleRevision.owner_id == owner,
                )
                .order_by(FeeRuleRevision.id.desc())
                .limit(1)
                .with_for_update()
            )
            or 0
        )

    def get(self, owner: int, shop: int, rule: int) -> FeeRule | None:
        return self.session.scalar(
            select(FeeRule)
            .where(FeeRule.owner_id == owner, FeeRule.shop_id == shop, FeeRule.id == rule)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def active(self, owner: int, shop: int, identity: str, channel: str) -> list[FeeRule]:
        return list(
            self.session.scalars(
                select(FeeRule)
                .where(
                    FeeRule.owner_id == owner,
                    FeeRule.shop_id == shop,
                    FeeRule.data_identity == identity,
                    FeeRule.channel == channel,
                    FeeRule.status == "active",
                )
                .order_by(FeeRule.id)
                .limit(201)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def page(
        self, owner: int, shop: int, identity: str, channel: str, before: int | None
    ) -> list[FeeRule]:
        statement = select(FeeRule).where(
            FeeRule.owner_id == owner,
            FeeRule.shop_id == shop,
            FeeRule.data_identity == identity,
            FeeRule.channel == channel,
        )
        if before is not None:
            statement = statement.where(FeeRule.id < before)
        return list(
            self.session.scalars(
                statement.order_by(FeeRule.id.desc())
                .limit(21)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def revisions(self, rule: FeeRule) -> list[FeeRuleRevision]:
        return list(
            self.session.scalars(
                select(FeeRuleRevision)
                .where(
                    FeeRuleRevision.owner_id == rule.owner_id,
                    FeeRuleRevision.rule_id == rule.id,
                )
                .order_by(FeeRuleRevision.version.desc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def by_request(self, owner: int, request: str) -> FeeRuleRevision | None:
        return self.session.scalar(
            select(FeeRuleRevision)
            .where(
                FeeRuleRevision.owner_id == owner,
                FeeRuleRevision.request_id == request,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def add(self, rule: FeeRule) -> None:
        self.session.add(rule)
        self.session.flush()

    def revise(self, revision: FeeRuleRevision) -> None:
        self.session.add(revision)
        self.session.flush()

    def clear(self, rule: FeeRule) -> None:
        for revision in self.revisions(rule):
            revision.content = None
        rule.content = None
        rule.match_key = None
        rule.status = "cleared"
