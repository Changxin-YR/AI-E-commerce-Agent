from app.core.errors import ConflictError, NotFoundError
from app.models.business_rules import BusinessRuleRevision
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.business_rules import RuleChange, RuleRevision, RuleScope, RuleValues
from app.schemas.operations import OperationScope
from app.services.profit_calculation import utc_text


class BusinessRulesService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow, self.repo = uow, uow.business_rules

    def _shop(self, owner: int, shop: int) -> None:
        self.uow.identity.lock_user(owner)
        if self.uow.identity.get_shop(owner, shop, lock=True) is None:
            raise NotFoundError()

    def _output(self, row: BusinessRuleRevision) -> RuleRevision:
        return RuleRevision(
            version=row.id,
            previous_version=row.previous_id,
            restored_from=row.restored_from_id,
            shop_id=row.shop_id,
            channel=row.channel,
            data_identity=row.data_identity,
            action=row.action,
            active=row.action in {"save", "restore"},
            values=RuleValues(
                max_age_hours=row.max_age_hours,
                min_quantity=row.min_quantity,
                max_margin_percent=row.max_margin_percent,
                advertising_daily_budget=row.advertising_daily_budget,
                currency=row.currency,
                notes=row.notes,
                basis=row.basis,
            ),
            created_at=utc_text(row.created_at),
        )

    def current(self, owner: int, shop: int, scope: RuleScope) -> RuleRevision:
        self._shop(owner, shop)
        rows = self.repo.revisions(owner, shop, scope.channel, scope.data_identity, limit=1)
        if rows:
            return self._output(rows[0])
        return RuleRevision(
            version=0,
            previous_version=0,
            restored_from=None,
            shop_id=shop,
            channel=scope.channel,
            data_identity=scope.data_identity,
            action="default",
            active=False,
            values=RuleValues(),
            created_at=None,
        )

    def history(
        self, owner: int, shop: int, scope: RuleScope, before: int | None
    ) -> list[RuleRevision]:
        self._shop(owner, shop)
        return [
            self._output(row)
            for row in self.repo.revisions(owner, shop, scope.channel, scope.data_identity, before)
        ]

    def get(self, owner: int, shop: int, version: int) -> RuleRevision:
        self._shop(owner, shop)
        row = self.repo.find(owner, shop, version)
        if row is None:
            raise NotFoundError()
        return self._output(row)

    def change(self, owner: int, shop: int, data: RuleChange) -> RuleRevision:
        current = self.current(
            owner, shop, RuleScope(channel=data.channel, data_identity=data.data_identity)
        )
        if current.version != data.expected_version:
            raise ConflictError("经营规则已变化，请刷新核对后再保存")
        values = data.values or RuleValues()
        if data.restore_version:
            prior = self.get(owner, shop, data.restore_version)
            if (
                prior.channel != data.channel
                or prior.data_identity != data.data_identity
                or not prior.active
            ):
                raise ConflictError("仅能恢复同渠道、同数据身份的有效规则历史")
            values = prior.values
        row = BusinessRuleRevision(
            owner_id=owner,
            shop_id=shop,
            channel=data.channel,
            data_identity=data.data_identity,
            action=data.action,
            previous_id=current.version,
            restored_from_id=data.restore_version,
            **values.model_dump(exclude={"notes", "automation"}),
            notes=values.notes.model_dump(),
        )
        self.repo.add(row)
        self.uow.record_event(
            owner,
            f"business_rules.{data.action}",
            "business_rule_revision",
            row.id,
            {
                "previous_version": current.version,
                "channel": data.channel,
                "data_identity": data.data_identity,
            },
        )
        output = self._output(row)
        self.uow.commit()
        return output

    def validate_scope(self, owner: int, shop: int, scope: OperationScope) -> None:
        current = self.current(
            owner, shop, RuleScope(channel=scope.channel, data_identity=scope.data_identity)
        )
        if current.version != scope.rule_revision_id:
            raise ConflictError("经营规则版本已变化，请刷新规则并重新检查")
        if current.active and (
            scope.max_age_hours != current.values.max_age_hours
            or scope.min_quantity != current.values.min_quantity
            or scope.max_margin_percent != current.values.max_margin_percent
        ):
            raise ConflictError("检查阈值须符合当前经营规则，请刷新规则")

    def is_current(self, owner: int, shop: int, channel: str, identity: str, version: int) -> bool:
        rows = self.repo.revisions(owner, shop, channel, identity, limit=1)
        return version == (rows[0].id if rows else 0)
