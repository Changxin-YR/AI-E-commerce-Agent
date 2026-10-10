import hashlib
import json
from datetime import datetime

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.identity import Shop
from app.models.imports import CustomerMessage, InventorySnapshot, OrderLine, Product
from app.models.operations import OperationRun, OperationTask, OperationTaskEvent
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.operations import (
    CheckPreview,
    Finding,
    OperationContext,
    OperationScope,
    RunInput,
    RunOutput,
    RunSnapshot,
    TaskDestination,
    TaskEventOutput,
    TaskInput,
    TaskOutput,
    TaskPage,
    TaskQuery,
)
from app.services.business_rules import BusinessRulesService
from app.services.import_groups import require_import_coverage
from app.services.listings import digest
from app.services.operation_checks import CheckResult, check_data
from app.services.profit_calculation import utc_text


def task_key(shop: int, finding: Finding, scope: OperationScope) -> str:
    rule: dict[str, str | int] = {"version": 1}
    if scope.rule_revision_id:
        rule["business_rule_revision"] = scope.rule_revision_id
    if finding.kind == "low_inventory":
        rule["max_age_hours"] = scope.max_age_hours
    if finding.kind == "low_margin":
        rule.update(
            start=scope.start_at.isoformat(),
            end=scope.end_at.isoformat(),
            currency=scope.currency,
            min_quantity=scope.min_quantity,
            max_margin=str(scope.max_margin_percent.normalize()),
        )
    data = [
        shop,
        scope.channel,
        scope.data_identity,
        finding.kind,
        rule,
        sorted(s.row_id for s in finding.sources),
    ]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class OperationsService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.operations

    def _shop(self, owner: int, shop_id: int) -> Shop:
        self.uow.identity.lock_user(owner)
        shop = self.uow.identity.get_shop(owner, shop_id, lock=True)
        if shop is None:
            raise NotFoundError()
        return shop

    def _run_output(self, run: OperationRun, detail: bool = True) -> RunOutput:
        scope = OperationScope.model_validate(run.scope)
        rule_current = BusinessRulesService(self.uow).is_current(
            run.owner_id, run.shop_id, scope.channel, scope.data_identity, scope.rule_revision_id
        )
        return RunOutput(
            id=run.id,
            shop_id=run.shop_id,
            scope=OperationScope.model_validate(run.scope),
            source_revision=run.source_revision,
            source_status="stale"
            if run.source_status == "current" and not rule_current
            else run.source_status,
            created_at=utc_text(run.created_at),
            valid_until=utc_text(run.valid_until) if run.valid_until else None,
            snapshot=RunSnapshot.model_validate(run.snapshot) if detail and run.snapshot else None,
        )

    def _task_output(self, task: OperationTask, detail: bool = True) -> TaskOutput:
        rule_current = self._task_rule_current(task)
        return TaskOutput(
            id=task.id,
            shop_id=task.shop_id,
            data_identity=task.data_identity,
            channel=task.channel,
            destinations=self._destinations(task)
            if detail and rule_current and task.source_status == "current"
            else [],
            owner_id=task.owner_id,
            kind=task.kind,
            status=task.status,
            source_status="stale"
            if task.source_status == "current" and not rule_current
            else task.source_status,
            version=task.version,
            snapshot=Finding.model_validate(task.snapshot) if task.snapshot else None,
            note=task.note,
            due_at=utc_text(task.due_at) if task.due_at else None,
            created_at=utc_text(task.created_at),
            history=[
                TaskEventOutput(
                    action=e.action,
                    from_status=e.from_status,
                    to_status=e.to_status,
                    version=e.version,
                    created_at=utc_text(e.created_at),
                    note=e.details.get("note") if e.details else None,
                    due_at=e.details.get("due_at") if e.details else None,
                )
                for e in self.repo.history(task.id)
            ]
            if detail
            else [],
        )

    def _destinations(self, task: OperationTask) -> list[TaskDestination]:
        if not task.snapshot:
            return []
        finding = Finding.model_validate(task.snapshot)
        query = {
            "shop": str(task.shop_id),
            "identity": task.data_identity,
            "channel": task.channel,
            "return_task": str(task.id),
        }
        if finding.scope:
            query.update(
                {
                    key: str(value)
                    for key, value in finding.scope.model_dump(mode="json").items()
                    if key
                    in {
                        "start_at",
                        "end_at",
                        "timezone",
                        "currency",
                        "max_age_hours",
                        "min_quantity",
                        "max_margin_percent",
                    }
                }
            )
        links: list[TaskDestination] = []
        if task.kind == "low_inventory":
            links.append(
                TaskDestination(
                    label="核对当前库存",
                    path="/inventory",
                    query={
                        **query,
                        "sku": finding.object_label,
                    },
                )
            )
        if task.kind == "low_margin":
            links.append(
                TaskDestination(
                    label="查看同范围经营分析",
                    path="/analytics",
                    query={
                        **query,
                        "start_at": finding.facts["订单起点(含)"],
                        "end_at": finding.facts["订单终点(不含)"],
                        "currency": finding.facts["币种"],
                        "sku": finding.object_label,
                    },
                )
            )
            product_id = self.repo.current_object_id(
                Product, task, [ref.row_id for ref in finding.sources]
            )
            if product_id is not None:
                links.append(
                    TaskDestination(
                        label="维护此商品 Listing",
                        path="/listings",
                        query={
                            **query,
                            "product": str(product_id),
                        },
                    )
                )
        if task.kind == "message_review":
            message_id = self.repo.current_object_id(
                CustomerMessage, task, [ref.row_id for ref in finding.sources]
            )
            if message_id is not None:
                links.append(
                    TaskDestination(
                        label="处理此客户消息",
                        path="/support",
                        query={
                            **query,
                            "message": str(message_id),
                        },
                    )
                )
        if finding.sources:
            links.append(
                TaskDestination(
                    label="查看来源与补充导入",
                    path="/imports",
                    query={
                        **query,
                        "batch": str(finding.sources[0].batch_id),
                    },
                )
            )
        return links

    def _task_rule_current(self, task: OperationTask) -> bool:
        return BusinessRulesService(self.uow).is_current(
            task.owner_id,
            task.shop_id,
            task.channel,
            task.data_identity,
            int((task.snapshot or {}).get("rule_revision_id", 0)),
        )

    def _event(self, task: OperationTask, action: str, previous: str) -> None:
        self.repo.add(
            OperationTaskEvent(
                task_id=task.id,
                action=action,
                from_status=previous,
                to_status=task.status,
                version=task.version,
                details={
                    "note": task.note,
                    "due_at": utc_text(task.due_at) if task.due_at else None,
                },
            )
        )
        self.uow.record_event(
            task.owner_id,
            f"operations.{action}",
            "operation_task",
            task.id,
            {"version": task.version, "status": task.status},
        )

    def _check(self, owner: int, shop: Shop, scope: OperationScope, now: datetime) -> CheckResult:
        BusinessRulesService(self.uow).validate_scope(owner, shop.id, scope)
        shop_id = shop.id
        # All evidence is bounded and read under the same owner lock as imports.
        orders = self.repo.records(
            OrderLine,
            owner,
            shop_id,
            scope.data_identity,
            scope.channel,
            scope.start_at.replace(tzinfo=None),
            scope.end_at.replace(tzinfo=None),
        )
        products = self.repo.records(Product, owner, shop_id, scope.data_identity)
        inventory = self.repo.records(
            InventorySnapshot, owner, shop_id, scope.data_identity, scope.channel
        )
        messages = self.repo.records(
            CustomerMessage, owner, shop_id, scope.data_identity, scope.channel
        )
        if max(len(orders), len(products), len(inventory), len(messages)) > 10000:
            raise BusinessError(
                "range_too_large", "单项检查超过 10000 行，请缩小范围；本次未保存", 422
            )
        require_import_coverage(
            self.uow,
            owner,
            shop.id,
            scope.data_identity,
            {"orders", "products", "inventory", "messages"},
            scope.channel,
        )
        result = check_data(orders, products, inventory, messages, scope, shop.data_revision, now)
        for finding in result.findings:
            finding.rule_revision_id = scope.rule_revision_id
        if len(result.findings) > 500:
            raise BusinessError(
                "too_many_findings", "核对候选超过 500 项，请缩小数据范围；本次未保存", 422
            )
        return result

    def preview(self, owner: int, shop_id: int, scope: OperationScope) -> CheckPreview:
        shop = self._shop(owner, shop_id)
        result = self._check(owner, shop, scope, utc_now())
        return CheckPreview(
            source_revision=shop.data_revision,
            branches=result.branches,
            findings=result.findings,
            sources=result.sources,
            valid_until=utc_text(result.valid_until) if result.valid_until else None,
        )

    def model_context(self, owner: int, shop_id: int, scope: OperationScope) -> OperationContext:
        preview = self.preview(owner, shop_id, scope)
        return OperationContext(
            preview=preview, preview_hash=digest(preview.model_dump(mode="json"))
        )

    def run(self, owner: int, shop_id: int, data: RunInput) -> RunOutput:
        shop = self._shop(owner, shop_id)
        scope = data.scope
        now = utc_now()
        existing = self.repo.run_by_request(owner, str(data.request_id))
        if existing:
            if (
                existing.shop_id != shop_id
                or OperationScope.model_validate(existing.scope) != scope
            ):
                raise ConflictError("请求标识已用于其他范围，请重新启动")
            self.repo.expire(owner, shop_id, now)
            output = self._run_output(existing)
            self.uow.commit()
            return output
        result = self._check(owner, shop, scope, now)
        if data.expected_preview_hash:
            current = CheckPreview(
                source_revision=shop.data_revision,
                branches=result.branches,
                findings=result.findings,
                sources=result.sources,
                valid_until=utc_text(result.valid_until) if result.valid_until else None,
            )
            if digest(current.model_dump(mode="json")) != data.expected_preview_hash:
                raise ConflictError("运营检查与已审阅候选不同，请重新运行")
        self.repo.expire(owner, shop_id, now)
        ids: list[int] = []
        created = 0
        for finding in result.findings:
            key = task_key(shop_id, finding, scope)
            task = self.repo.task_by_key(owner, key)
            if task is None:
                task = OperationTask(
                    owner_id=owner,
                    shop_id=shop_id,
                    dedupe_key=key,
                    kind=finding.kind,
                    data_identity=scope.data_identity,
                    channel=scope.channel,
                    snapshot=finding.model_dump(mode="json"),
                    valid_until=datetime.fromisoformat(finding.valid_until).replace(tzinfo=None)
                    if finding.valid_until
                    else None,
                )
                self.repo.add(task)
                self.repo.task_sources(task.id, {s.row_id: s.batch_id for s in finding.sources})
                self._event(task, "proposed", "none")
                created += 1
            elif task.source_status == "stale":
                # Rechecking exactly the same evidence never resets a seller's disposition.
                task.source_status = "current"
                task.version += 1
                self._event(task, "revalidated", task.status)
            ids.append(task.id)
        # One reference per batch in the summary; task detail contains every used row.
        batches = {s.batch_id: s for s in result.sources}
        export_times = [
            datetime.fromisoformat(s.exported_at) for s in batches.values() if s.exported_at
        ]
        unknown = sum(s.exported_at is None for s in batches.values())
        as_of = (
            f"来源文件导出时间 {min(export_times).isoformat()} 至 {max(export_times).isoformat()}；"
            if export_times
            else ""
        )
        as_of += (
            f"{unknown} 个批次导出时间未知。库存另按快照时间核对；非实时扫描。"
            if batches
            else "无已导入数据。"
        )
        snapshot = RunSnapshot(
            branches=result.branches,
            task_ids=ids,
            sources=list(batches.values()),
            data_as_of=as_of,
            created_candidates=created,
            reused_candidates=len(ids) - created,
        )
        run = OperationRun(
            owner_id=owner,
            shop_id=shop_id,
            request_id=str(data.request_id),
            scope=scope.model_dump(mode="json"),
            source_revision=shop.data_revision,
            snapshot=snapshot.model_dump(mode="json"),
            valid_until=result.valid_until,
        )
        self.repo.add(run)
        self.repo.run_sources(run.id, set(batches))
        self.uow.record_event(
            owner,
            "operations.checked",
            "operation_run",
            run.id,
            {"revision": shop.data_revision, "created": created, "reused": len(ids) - created},
        )
        output = self._run_output(run)
        self.uow.commit()
        return output

    def runs(self, owner: int, shop: int, scope: TaskQuery) -> list[RunOutput]:
        self._shop(owner, shop)
        self.repo.expire(owner, shop, utc_now())
        output = [
            self._run_output(r, False)
            for r in self.repo.runs(owner, shop, scope.data_identity, scope.channel)
        ]
        self.uow.commit()
        return output

    def get_run(self, owner: int, shop: int, run_id: int) -> RunOutput:
        self._shop(owner, shop)
        self.repo.expire(owner, shop, utc_now())
        run = self.repo.run(owner, shop, run_id)
        if run is None:
            raise NotFoundError()
        output = self._run_output(run)
        self.uow.commit()
        return output

    def tasks(self, owner: int, shop: int, scope: TaskQuery) -> TaskPage:
        self._shop(owner, shop)
        self.repo.expire(owner, shop, utc_now())
        tasks = self.repo.tasks(owner, shop, scope.data_identity, scope.channel, scope.offset)
        output = TaskPage(
            items=[self._task_output(t, False) for t in tasks[:50]], has_more=len(tasks) > 50
        )
        self.uow.commit()
        return output

    def get_task(self, owner: int, shop: int, task_id: int) -> TaskOutput:
        self._shop(owner, shop)
        self.repo.expire(owner, shop, utc_now())
        task = self.repo.task(owner, shop, task_id)
        if task is None:
            raise NotFoundError()
        output = self._task_output(task)
        self.uow.commit()
        return output

    def change_task(self, owner: int, shop: int, task_id: int, data: TaskInput) -> TaskOutput:
        self._shop(owner, shop)
        now = utc_now()
        self.repo.expire(owner, shop, now)
        task = self.repo.task(owner, shop, task_id)
        if task is None:
            raise NotFoundError()
        if data.action not in {"reject", "ignore"} and not self._task_rule_current(task):
            raise ConflictError("经营规则已变化，请重新检查后处理")
        if task.source_status == "cleared" or (
            task.source_status != "current" and data.action not in {"reject", "ignore"}
        ):
            raise ConflictError("来源已变化、过期或清除，请重新巡检后处理")
        targets = {
            "approve": "open",
            "reject": "rejected",
            "ignore": "ignored",
            "defer": "deferred",
            "complete": "completed",
            "reopen": "open",
            "edit": task.status,
        }
        allowed = {
            "approve": {"pending_approval"},
            "reject": {"pending_approval"},
            "ignore": {"pending_approval", "open", "deferred"},
            "defer": {"open", "deferred"},
            "complete": {"open", "deferred"},
            "reopen": {"completed", "ignored", "rejected", "deferred"},
            "edit": {"pending_approval", "open", "deferred", "completed", "ignored", "rejected"},
        }
        due = data.due_at.replace(tzinfo=None) if data.due_at else None
        if data.action == "defer" and (due is None or due <= now):
            raise BusinessError("invalid_due", "延期须设置未来截止时间", 422)
        if task.status == targets[data.action] and task.note == data.note and task.due_at == due:
            output = self._task_output(task)
            self.uow.commit()
            return output
        if task.version != data.version:
            raise ConflictError("待办已被其他操作更新，请刷新后重试")
        if task.status not in allowed[data.action]:
            raise ConflictError("当前状态不支持此操作")
        previous = task.status
        task.status, task.note, task.due_at = targets[data.action], data.note, due
        task.version += 1
        self._event(task, data.action, previous)
        output = self._task_output(task)
        self.uow.commit()
        return output
