import hashlib

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.models.fee_rules import FeeRule, FeeRuleRevision
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.expenses import ExpenseControl
from app.schemas.fee_rules import (
    FeeRuleChange,
    FeeRuleContent,
    FeeRuleDraft,
    FeeRuleHistory,
    FeeRulePage,
    FeeRulePreview,
    FeeRuleSaved,
    FeeRuleWrite,
)
from app.services.fee_mapping import map_fees
from app.services.product_quality import digest
from app.services.profit_calculation import utc_text
from app.services.statements import StatementService


def match_key(name: str) -> str:
    return hashlib.sha256(name.strip().encode("utf-8")).hexdigest()


class FeeRuleService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.fee_rules

    def _shop(self, owner: int, shop: int) -> None:
        self.uow.identity.lock_user(owner)
        if self.uow.identity.get_shop(owner, shop, lock=True) is None:
            raise NotFoundError()

    def _rule(self, owner: int, shop: int, rule_id: int) -> FeeRule:
        rule = self.repo.get(owner, shop, rule_id)
        if rule is None:
            raise NotFoundError()
        return rule

    def _output(self, rule: FeeRule, full: bool = True) -> FeeRuleSaved:
        return FeeRuleSaved(
            id=rule.id,
            shop_id=rule.shop_id,
            data_identity=rule.data_identity,
            channel=rule.channel,
            status=rule.status,
            version=rule.version,
            content=FeeRuleContent.model_validate(rule.content) if rule.content else None,
            created_at=utc_text(rule.created_at),
            history=[
                FeeRuleHistory(
                    version=r.version,
                    action=r.action,
                    created_at=utc_text(r.created_at),
                    content=FeeRuleContent.model_validate(r.content) if r.content else None,
                )
                for r in self.repo.revisions(rule)
            ]
            if full
            else [],
        )

    def _preview(self, owner: int, shop: int, data: FeeRuleDraft) -> FeeRulePreview:
        self._shop(owner, shop)
        existing = self._rule(owner, shop, data.rule_id) if data.rule_id else None
        if existing:
            if (
                existing.status != "active"
                or existing.version != data.version
                or existing.data_identity != data.scope.data_identity
                or existing.channel != data.scope.channel
            ):
                raise ConflictError("规则版本或范围已变化，请重新读取。")
            if len(self.repo.revisions(existing)) >= 100:
                raise BusinessError(
                    "revision_limit", "每条规则最多 100 次创建/修订，仍可撤销或清除。", 422
                )
            if existing.content == data.content.model_dump(mode="json"):
                raise ConflictError("规则内容没有变化。")
        elif data.version != 0:
            raise ConflictError("新规则版本必须为零。")
        rules = self.repo.active(owner, shop, data.scope.data_identity, data.scope.channel)
        if any(
            r.id != data.rule_id and r.match_key == match_key(data.content.fee_name) for r in rules
        ):
            raise ConflictError("该范围已有相同完整收费名的有效规则，请修订原规则。")
        if len(rules) > 200 or (not existing and len(rules) >= 200):
            raise BusinessError("rule_limit", "每个店铺/身份/渠道最多 200 条有效规则。", 422)
        # The enclosing transaction keeps all locks through the final rule write.
        with self.uow.defer_commits():
            result = StatementService(self.uow).reconcile(owner, shop, data.scope)
        proposed = FeeRule(
            id=data.rule_id or 0,
            version=data.version + 1,
            content=data.content.model_dump(mode="json"),
        )
        after = map_fees(
            result.statements,
            result.comparisons,
            [r for r in rules if r.id != data.rule_id] + [proposed],
        )
        before_by_id = {m.statement_id: m for m in result.mappings}
        lines = {line.id: line for line in result.statements}
        changes = [
            FeeRuleChange(
                statement_id=m.statement_id,
                fee_name=lines[m.statement_id].fee_name,
                source=lines[m.statement_id].source,
                before=before_by_id[m.statement_id],
                after=m,
            )
            for m in after
            if before_by_id[m.statement_id] != m
        ]
        return FeeRulePreview(
            preview_hash=digest(
                {
                    "contract": "fee-name-exact-v1",
                    "shop": shop,
                    "draft": data.model_dump(mode="json"),
                    "result": result.model_dump(mode="json", exclude={"calculated_at"}),
                    "rules": [
                        {"id": r.id, "version": r.version, "content": r.content} for r in rules
                    ],
                }
            ),
            source_revision=result.source_revision,
            calculated_at=result.calculated_at,
            previous=FeeRuleContent.model_validate(existing.content) if existing else None,
            proposed=data.content,
            changes=changes,
            statement_count=len(result.statements),
            scope=data.scope,
        )

    def preview(self, owner: int, shop: int, data: FeeRuleDraft) -> FeeRulePreview:
        output = self._preview(owner, shop, data)
        self.uow.commit()
        return output

    def _replay(
        self, owner: int, shop: int, request: str, request_hash: str
    ) -> FeeRuleSaved | None:
        previous = self.repo.by_request(owner, request)
        if not previous:
            return None
        if previous.request_hash != request_hash:
            raise ConflictError("请求标识已用于另一项规则操作。")
        return self._output(self._rule(owner, shop, previous.rule_id))

    def write(self, owner: int, shop: int, data: FeeRuleWrite) -> FeeRuleSaved:
        self._shop(owner, shop)
        request_hash = digest(
            {
                "shop": shop,
                "action": "write",
                **data.model_dump(mode="json", exclude={"request_id"}),
            }
        )
        replay = self._replay(owner, shop, str(data.request_id), request_hash)
        if replay:
            self.uow.commit()
            return replay
        draft = FeeRuleDraft.model_validate(
            data.model_dump(exclude={"request_id", "confirm", "preview_hash"})
        )
        current = self._preview(owner, shop, draft)
        if current.preview_hash != data.preview_hash:
            raise ConflictError("规则、账单来源或人工费用已变化，请重新预览并确认。")
        if data.rule_id:
            rule = self._rule(owner, shop, data.rule_id)
            rule.version += 1
        else:
            rule = FeeRule(
                owner_id=owner,
                shop_id=shop,
                data_identity=data.scope.data_identity,
                channel=data.scope.channel,
                version=1,
                status="active",
            )
        rule.content = data.content.model_dump(mode="json")
        rule.match_key = match_key(data.content.fee_name)
        if not data.rule_id:
            self.repo.add(rule)
        action = "update" if data.rule_id else "create"
        self.repo.revise(
            FeeRuleRevision(
                rule_id=rule.id,
                owner_id=owner,
                version=rule.version,
                request_id=str(data.request_id),
                request_hash=request_hash,
                action=action,
                content=rule.content,
            )
        )
        self.uow.record_event(
            owner, f"fee_rule.{action}", "fee_rule", rule.id, {"version": rule.version}
        )
        output = self._output(rule)
        self.uow.commit()
        return output

    def page(
        self, owner: int, shop: int, identity: str, channel: str, before: int | None
    ) -> FeeRulePage:
        self._shop(owner, shop)
        rules = self.repo.page(owner, shop, identity, channel, before)
        output = FeeRulePage(
            items=[self._output(r, False) for r in rules[:20]],
            next_cursor=rules[19].id if len(rules) > 20 else None,
        )
        self.uow.commit()
        return output

    def get(self, owner: int, shop: int, rule: int) -> FeeRuleSaved:
        self._shop(owner, shop)
        output = self._output(self._rule(owner, shop, rule))
        self.uow.commit()
        return output

    def control(
        self, owner: int, shop: int, rule_id: int, action: str, data: ExpenseControl
    ) -> FeeRuleSaved:
        self._shop(owner, shop)
        request_hash = digest(
            {
                "shop": shop,
                "rule": rule_id,
                "action": action,
                **data.model_dump(mode="json", exclude={"request_id"}),
            }
        )
        replay = self._replay(owner, shop, str(data.request_id), request_hash)
        if replay:
            self.uow.commit()
            return replay
        rule = self._rule(owner, shop, rule_id)
        if rule.version != data.version:
            raise ConflictError("规则版本已变化，请刷新。")
        if rule.status == "cleared" or (action == "withdraw" and rule.status == "withdrawn"):
            output = self._output(rule)
            self.uow.commit()
            return output
        if action == "clear":
            self.repo.clear(rule)
        else:
            rule.status, rule.match_key = "withdrawn", None
        rule.version += 1
        self.repo.revise(
            FeeRuleRevision(
                rule_id=rule.id,
                owner_id=owner,
                version=rule.version,
                request_id=str(data.request_id),
                request_hash=request_hash,
                action=action,
                content=None,
            )
        )
        self.uow.record_event(
            owner, f"fee_rule.{action}", "fee_rule", rule.id, {"version": rule.version}
        )
        output = self._output(rule)
        self.uow.commit()
        return output
