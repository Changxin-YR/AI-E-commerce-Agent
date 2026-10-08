from datetime import timedelta
from typing import Any

from app.core.errors import ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.agent import AgentExecution
from app.models.authorizations import AuthorizationUse, InternalAuthorization
from app.models.identity import Shop
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import StartAgent
from app.schemas.authorizations import (
    AuthorizationOutput,
    AuthorizationPage,
    AuthorizationUseOutput,
    CreateAuthorization,
)
from app.schemas.operations import OperationScope, TaskInput
from app.services.business_rules import BusinessRulesService
from app.services.listings import digest
from app.services.operations import OperationsService, task_key
from app.services.profit_calculation import utc_text


class AuthorizationsService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow, self.repo = uow, uow.authorizations

    def _shop(self, owner: int, shop_id: int) -> Shop:
        self.uow.identity.lock_user(owner)
        shop = self.uow.identity.get_shop(owner, shop_id, lock=True)
        if shop is None:
            raise NotFoundError()
        return shop

    def _get(self, owner: int, shop: int, grant_id: int) -> InternalAuthorization:
        grant = self.repo.get(owner, shop, grant_id)
        if grant is None:
            raise NotFoundError()
        return grant

    def status(self, grant: InternalAuthorization, shop: Shop) -> str:
        now = utc_now()
        if grant.revoked_at:
            return "revoked"
        if grant.expires_at <= now:
            return "expired"
        if grant.source_revision != shop.data_revision or (
            grant.source_valid_until and grant.source_valid_until <= now
        ):
            return "source_changed"
        scope = OperationScope.model_validate(grant.scope)
        if not BusinessRulesService(self.uow).is_current(
            grant.owner_id,
            grant.shop_id,
            scope.channel,
            scope.data_identity,
            scope.rule_revision_id,
        ):
            return "rules_changed"
        if grant.used_count >= grant.max_uses:
            return "exhausted"
        return "active"

    def _output(self, grant: InternalAuthorization, shop: Shop) -> AuthorizationOutput:
        return AuthorizationOutput(
            id=grant.id,
            shop_id=grant.shop_id,
            version=grant.version,
            origin_execution_id=grant.origin_execution_id,
            scope=OperationScope.model_validate(grant.scope),
            source_revision=grant.source_revision,
            candidate_count=grant.candidate_count,
            max_uses=grant.max_uses,
            used_count=grant.used_count,
            status=self.status(grant, shop),
            expires_at=utc_text(grant.expires_at),
            source_valid_until=utc_text(grant.source_valid_until)
            if grant.source_valid_until
            else None,
            revoked_at=utc_text(grant.revoked_at) if grant.revoked_at else None,
            created_at=utc_text(grant.created_at),
            uses=[
                AuthorizationUseOutput(
                    id=use.id,
                    execution_id=use.execution_id,
                    operation_run_id=use.operation_run_id,
                    changes=use.changes,
                    reused_count=use.reused_count,
                    created_at=utc_text(use.created_at),
                    reverted_at=utc_text(use.reverted_at) if use.reverted_at else None,
                )
                for use in self.repo.uses(grant.id)
            ],
        )

    def create(self, owner: int, shop_id: int, data: CreateAuthorization) -> AuthorizationOutput:
        shop = self._shop(owner, shop_id)
        key = digest([shop_id, data.model_dump(mode="json")])
        prior = self.repo.by_request(owner, str(data.request_id))
        if prior:
            if prior.request_hash != key:
                raise ConflictError("请求标识已用于其他授权")
            output = self._output(prior, shop)
            self.uow.commit()
            return output
        self.uow.agent.expire(owner, shop_id, utc_now())
        run = self.uow.agent.get(owner, shop_id, data.execution_id)
        if run is None:
            raise NotFoundError()
        if (
            run.version != data.expected_version
            or run.template != "daily"
            or run.status != "waiting_approval"
            or run.next_node != "propose_tasks"
            or run.source_status != "current"
            or not run.input
            or not run.result
            or run.source_revision != shop.data_revision
        ):
            raise ConflictError("请从当前来源的待审批异常预览创建授权")
        scope = StartAgent.model_validate(run.input).scope
        preview = OperationsService(self.uow).preview(owner, shop_id, scope)
        if not preview.findings or digest(preview.model_dump(mode="json")) != digest(run.result):
            raise ConflictError("异常预览已变化，请重新检查")
        grant = InternalAuthorization(
            owner_id=owner,
            shop_id=shop_id,
            request_id=str(data.request_id),
            request_hash=key,
            origin_execution_id=run.id,
            scope=scope.model_dump(mode="json"),
            source_revision=shop.data_revision,
            content_hash=digest(run.result),
            candidate_count=len(preview.findings),
            max_uses=data.max_uses,
            expires_at=utc_now() + timedelta(hours=data.valid_hours),
            source_valid_until=run.valid_until,
        )
        self.repo.add(grant)
        self.uow.record_event(
            owner,
            "authorization.created",
            "internal_authorization",
            grant.id,
            {"max_uses": grant.max_uses, "origin_execution_id": run.id},
        )
        output = self._output(grant, shop)
        self.uow.commit()
        return output

    def list(self, owner: int, shop_id: int, before: int | None) -> AuthorizationPage:
        shop = self._shop(owner, shop_id)
        rows = self.repo.grants(owner, shop_id, before)
        output = AuthorizationPage(
            items=[self._output(g, shop) for g in rows[:50]],
            next_before_id=rows[49].id if len(rows) > 50 else None,
        )
        self.uow.commit()
        return output

    def get(self, owner: int, shop_id: int, grant_id: int) -> AuthorizationOutput:
        shop = self._shop(owner, shop_id)
        output = self._output(self._get(owner, shop_id, grant_id), shop)
        self.uow.commit()
        return output

    def revoke(self, owner: int, shop_id: int, grant_id: int, version: int) -> AuthorizationOutput:
        shop = self._shop(owner, shop_id)
        grant = self._get(owner, shop_id, grant_id)
        if not grant.revoked_at:
            if grant.version != version:
                raise ConflictError("授权已被使用或更新，请刷新后撤销")
            grant.revoked_at = utc_now()
            grant.version += 1
            self.uow.record_event(
                owner, "authorization.revoked", "internal_authorization", grant.id
            )
        output = self._output(grant, shop)
        self.uow.commit()
        return output

    def validate(
        self, run: AgentExecution, grant_id: int, *, check_content: bool
    ) -> InternalAuthorization:
        shop = self._shop(run.owner_id, run.shop_id)
        grant = self._get(run.owner_id, run.shop_id, grant_id)
        data = StartAgent.model_validate(run.input)
        if (
            grant.skill != "propose_tasks"
            or data.template != "daily"
            or self.status(grant, shop) != "active"
            or run.source_status != "current"
            or run.source_revision != grant.source_revision
            or data.scope != OperationScope.model_validate(grant.scope)
        ):
            raise ConflictError("预授权不适用于当前范围，或已撤销、过期、用尽，请审阅后单次批准")
        if check_content and (
            run.next_node != "propose_tasks" or digest(run.result) != grant.content_hash
        ):
            raise ConflictError("当前候选内容与授权预览不一致，请重新检查")
        return grant

    def prepare(self, run: AgentExecution) -> tuple[InternalAuthorization, set[int]]:
        if run.authorization_id is None:
            raise ConflictError("未绑定预授权")
        grant = self.validate(run, run.authorization_id, check_content=True)
        preview = OperationsService(self.uow).preview(
            run.owner_id, run.shop_id, OperationScope.model_validate(grant.scope)
        )
        if digest(preview.model_dump(mode="json")) != grant.content_hash:
            raise ConflictError("执行前的异常内容已变化，请重新检查")
        # Remember which candidates already existed. Their disposition belongs to the seller.
        existing = set()
        for finding in preview.findings:
            task = self.uow.operations.task_by_key(
                run.owner_id,
                task_key(run.shop_id, finding, OperationScope.model_validate(grant.scope)),
            )
            if task:
                existing.add(task.id)
        return grant, existing

    def consume(
        self,
        run: AgentExecution,
        grant: InternalAuthorization,
        existing: set[int],
        result: dict[str, Any],
    ) -> None:
        shop = self._shop(run.owner_id, run.shop_id)
        if self.status(grant, shop) != "active":
            raise ConflictError("保存期间授权或来源已到期，本次候选和额度均未提交")
        if self.repo.for_execution(run.id):
            raise ConflictError("该执行已消耗授权，请刷新读取已保存结果")
        changes: list[dict[str, Any]] = []
        ids = result["snapshot"]["task_ids"]
        for task_id in ids:
            if task_id in existing:
                continue
            task = self.uow.operations.task(run.owner_id, run.shop_id, task_id)
            if task is None or task.status != "pending_approval":
                raise ConflictError("写入结果不符合内部候选约定")
            changes.append(
                {
                    "task_id": task.id,
                    "before": "none",
                    "after": task.status,
                    "version": task.version,
                }
            )
        self.repo.add(
            AuthorizationUse(
                authorization_id=grant.id,
                execution_id=run.id,
                operation_run_id=result["id"],
                changes=changes,
                reused_count=len(ids) - len(changes),
            )
        )
        grant.used_count += 1
        grant.version += 1
        self.uow.record_event(
            run.owner_id,
            "authorization.consumed",
            "internal_authorization",
            grant.id,
            {"execution_id": run.id, "used_count": grant.used_count},
        )

    def revert(self, owner: int, shop_id: int, grant_id: int, use_id: int) -> AuthorizationOutput:
        shop = self._shop(owner, shop_id)
        grant = self._get(owner, shop_id, grant_id)
        use = next((u for u in self.repo.uses(grant.id) if u.id == use_id), None)
        if use is None:
            raise NotFoundError()
        if not use.reverted_at:
            # Validate every row before changing any, within one composed transaction.
            self.uow.operations.expire(owner, shop_id, utc_now())
            with self.uow.session.begin_nested(), self.uow.defer_commits():
                for change in use.changes:
                    task = self.uow.operations.task(owner, shop_id, change["task_id"])
                    if (
                        task is None
                        or task.version != change["version"]
                        or task.status != "pending_approval"
                        or task.source_status == "cleared"
                    ):
                        raise ConflictError(
                            "候选已被处理、编辑或来源失效，整批撤回未执行；请逐项核对"
                        )
                for change in use.changes:
                    OperationsService(self.uow).change_task(
                        owner,
                        shop_id,
                        change["task_id"],
                        TaskInput(action="reject", version=change["version"]),
                    )
                use.reverted_at = utc_now()
                self.uow.record_event(
                    owner,
                    "authorization.candidates_reverted",
                    "authorization_use",
                    use.id,
                    {"count": len(use.changes)},
                )
        output = self._output(grant, shop)
        self.uow.commit()
        return output
