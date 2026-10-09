from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from time import monotonic
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.agent import AgentExecution, AgentStep
from app.models.identity import Shop
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import (
    AgentAction,
    AgentOutput,
    Budget,
    ModelStatus,
    SkillDefinition,
    StartAgent,
    StepOutput,
)
from app.schemas.analytics import AnalysisResult
from app.schemas.support import SupportPreparation, SupportSelection
from app.services.agent_model import DecisionModel, GenerationReply, ModelReply
from app.services.agent_skills import (
    CONTRACTS,
    ControlledSkills,
    ListingPreparation,
    evidence,
    require_skill,
)
from app.services.analysis_explanation import (
    QuestionDecision,
    compose,
    explanation_request,
    question_request,
)
from app.services.analytics import AnalyticsService
from app.services.authorizations import AuthorizationsService
from app.services.business_rules import BusinessRulesService
from app.services.listing_composition import compose_listing, listing_request
from app.services.listings import ListingService, digest
from app.services.operations import OperationsService
from app.services.profit_calculation import utc_text
from app.services.support import SupportService
from app.services.support_composition import compose_support, support_request

FIRST_NODE = {
    "daily": "data_check",
    "analysis": "metrics",
    "listing": "product_context",
    "support": "message_context",
    "natural": "plan",
    "question": "question_plan",
    "listing_model": "product_context",
    "support_model": "support_context",
}
TERMINAL = {"succeeded", "cancelled", "rejected", "blocked", "result_unknown", "circuit_open"}


@dataclass(frozen=True)
class ModelLease:
    owner: int
    shop: int
    run_id: int
    token: str
    version: int
    step_id: int
    reserve: Decimal


class AgentService:
    def __init__(self, uow: UnitOfWork, model: DecisionModel) -> None:
        self.uow, self.repo, self.model = uow, uow.agent, model

    def _shop(self, owner: int, shop_id: int) -> Shop:
        self.uow.identity.lock_user(owner)
        shop = self.uow.identity.get_shop(owner, shop_id, lock=True)
        if shop is None:
            raise NotFoundError()
        return shop

    def catalog(self, owner: int, shop: int) -> list[SkillDefinition]:
        self._shop(owner, shop)
        return [require_skill(name) for name in CONTRACTS]

    def model_status(self, owner: int, shop: int) -> ModelStatus:
        self._shop(owner, shop)
        return self.model.status()

    def _load(self, owner: int, shop: int, run_id: int) -> AgentExecution:
        self._shop(owner, shop)
        self.repo.expire(owner, shop, utc_now())
        run = self.repo.get(owner, shop, run_id)
        if run is None:
            raise NotFoundError()
        if run.input and run.source_status == "current":
            scope = StartAgent.model_validate(run.input).scope
            if not BusinessRulesService(self.uow).is_current(
                owner, shop, scope.channel, scope.data_identity, scope.rule_revision_id
            ):
                run.source_status = "stale"
                run.version += 1
                self._event(run, "business_rules_changed", run.status)
        if (
            run.template == "support_model"
            and run.input
            and run.result
            and run.source_status == "current"
            and run.next_node in {"compose_support", "support_candidate"}
        ):
            try:
                prepared = SupportPreparation.model_validate(
                    run.result.get("preparation", run.result)
                )
                self._current_support(run, prepared)
            except BusinessError:
                run.source_status = "stale"
                run.version += 1
                self._event(run, "source_changed", run.status)
        if (
            run.authorization_id
            and run.next_node == "propose_tasks"
            and run.status == "ready"
            and run.input
        ):
            try:
                AuthorizationsService(self.uow).validate(
                    run, run.authorization_id, check_content=True
                )
            except BusinessError:
                run.status, run.reason = "waiting_approval", "authorization_unavailable"
                run.version += 1
                self._event(run, run.reason, run.status)
        if run.lease_token and run.lease_until and run.lease_until <= utc_now():
            run.lease_token = None
            if run.status == "running":
                run.status, run.reason = "result_unknown", "model_lease_expired"
            run.version += 1
            self._event(run, "lease_expired", "result_unknown")
        return run

    def _output(self, run: AgentExecution, detail: bool = True) -> AgentOutput:
        return AgentOutput(
            id=run.id,
            authorization_id=run.authorization_id,
            shop_id=run.shop_id,
            template=run.template,
            status=run.status,
            reason=run.reason,
            version=run.version,
            next_node=run.next_node,
            source_status=run.source_status,
            source_revision=run.source_revision,
            input=StartAgent.model_validate(run.input) if detail and run.input else None,
            result=run.result if detail else None,
            steps_used=run.steps_used,
            elapsed_ms=run.elapsed_ms,
            budget=Budget.model_validate(run.budget),
            spent_usd=run.spent_usd,
            reserved_usd=run.reserved_usd,
            model_status=run.model_status,
            created_at=utc_text(run.created_at),
            steps=[
                StepOutput(
                    id=s.id,
                    node=s.node,
                    skill=s.skill,
                    skill_version=s.skill_version,
                    status=s.status,
                    reason=s.reason,
                    next_node=s.next_node,
                    input=s.input,
                    output=s.output,
                    duration_ms=s.duration_ms,
                    created_at=utc_text(s.created_at),
                )
                for s in self.repo.steps(run.id)
            ]
            if detail
            else [],
        )

    def _finish(self, run: AgentExecution) -> AgentOutput:
        self.uow.session.flush()
        output = self._output(run)
        self.uow.commit()
        return output

    def _event(self, run: AgentExecution, action: str, status: str) -> None:
        self.repo.add(
            AgentStep(
                execution_id=run.id,
                node=run.next_node,
                skill="",
                status=status,
                reason=action,
                next_node=run.next_node,
                input=None,
                output=None,
            )
        )
        self.uow.record_event(
            run.owner_id,
            f"agent.{action}",
            "agent_execution",
            run.id,
            {"version": run.version, "status": status},
        )

    def start(self, owner: int, shop_id: int, data: StartAgent) -> AgentOutput:
        shop = self._shop(owner, shop_id)
        canonical = data.model_dump(mode="json")
        if canonical["authorization_id"] is None:
            canonical.pop("authorization_id")  # Preserve hashes for existing unbound requests.
        if not canonical["allow_analysis_data"]:
            canonical.pop("allow_analysis_data")  # Preserve earlier request hashes.
        if not canonical["allow_listing_data"]:
            canonical.pop("allow_listing_data")
        if canonical["expected_product_source_row_id"] is None:
            canonical.pop("expected_product_source_row_id")
        if not canonical["allow_support_data"]:
            canonical.pop("allow_support_data")
        if canonical["support_context"] is None:
            canonical.pop("support_context")
        key = digest([shop_id, canonical])
        prior = self.repo.by_request(owner, str(data.request_id))
        if prior:
            if prior.request_hash != key:
                raise ConflictError("请求标识已用于其他任务，请使用新标识")
            return self._finish(self._load(owner, shop_id, prior.id))
        BusinessRulesService(self.uow).validate_scope(owner, shop_id, data.scope)
        run = AgentExecution(
            owner_id=owner,
            shop_id=shop_id,
            request_id=str(data.request_id),
            request_hash=key,
            template=data.template,
            next_node=FIRST_NODE[data.template],
            source_revision=shop.data_revision,
            authorization_id=data.authorization_id,
            input=canonical,
            result=None,
            budget=data.budget.model_dump(mode="json"),
        )
        self.repo.add(run)
        if data.authorization_id:
            AuthorizationsService(self.uow).validate(
                run, data.authorization_id, check_content=False
            )
        self._event(run, "started", "ready")
        return self._finish(run)

    def get(self, owner: int, shop: int, run_id: int) -> AgentOutput:
        return self._finish(self._load(owner, shop, run_id))

    def list(self, owner: int, shop: int) -> list[AgentOutput]:
        self._shop(owner, shop)
        self.repo.expire(owner, shop, utc_now())
        output = [
            self._output(self._load(owner, shop, r.id), False)
            for r in self.repo.executions(owner, shop)
        ]
        self.uow.commit()
        return output

    def act(self, owner: int, shop: int, run_id: int, data: AgentAction) -> AgentOutput:
        run = self._load(owner, shop, run_id)
        if (
            (data.action == "pause" and run.status == "paused")
            or (data.action == "cancel" and run.status == "cancelled")
            or (data.action == "reject" and run.status == "rejected")
        ):
            return self._finish(run)
        if run.version != data.version:
            raise ConflictError("任务已变化，请刷新后重试")
        if data.action == "advance":
            if run.status != "ready":
                return self._finish(run)
            return self._advance(run)
        if run.status in TERMINAL:
            raise ConflictError("任务已结束或被阻断，请核对原因后新建任务")
        if data.action == "use_authorization":
            if run.status != "waiting_approval" or not data.authorization_id:
                raise ConflictError("请从待审批候选选择有效预授权")
            AuthorizationsService(self.uow).validate(run, data.authorization_id, check_content=True)
            run.authorization_id = data.authorization_id
            run.status = "ready"
        elif data.action in {"approve", "reject"}:
            if run.status != "waiting_approval":
                raise ConflictError("当前没有待审批节点")
            if data.action == "approve" and run.source_status != "current":
                raise ConflictError("来源已变化，不能批准旧预览")
            run.status = "ready" if data.action == "approve" else "rejected"
            # Explicit single-node approval is independent of any earlier grant.
            run.authorization_id = None
        elif data.action == "pause":
            if run.status not in {"ready", "running"}:
                raise ConflictError("当前状态不能暂停")
            run.status = "paused"
        elif data.action == "cancel":
            run.status = "cancelled"
        elif data.action == "resume":
            self._resume(run, data)
        run.reason = data.action
        run.version += 1
        self._event(run, data.action, run.status)
        return self._finish(run)

    def _resume(self, run: AgentExecution, data: AgentAction) -> None:
        if run.status not in {"paused", "waiting_configuration"}:
            raise ConflictError("当前任务不能恢复")
        if run.lease_token or run.reserved_usd:
            raise ConflictError("模型仍在执行或费用未确认，不能再次调用")
        if run.source_status != "current":
            raise ConflictError("来源已变化，请从当前数据新建任务")
        if data.budget:
            old = Budget.model_validate(run.budget)
            if (
                data.budget.max_steps < old.max_steps
                or data.budget.max_seconds < old.max_seconds
                or data.budget.max_cost_usd < old.max_cost_usd
            ):
                raise ConflictError("恢复预算不能低于原预算")
            run.budget = data.budget.model_dump(mode="json")
        run.status = "ready"

    def _budget_reason(self, run: AgentExecution) -> str:
        budget = Budget.model_validate(run.budget)
        if run.steps_used >= budget.max_steps:
            return "step_budget"
        if run.elapsed_ms >= budget.max_seconds * 1000:
            return "time_budget"
        if run.spent_usd > budget.max_cost_usd:
            return "cost_budget"
        return ""

    def _advance(self, run: AgentExecution) -> AgentOutput:
        if run.source_status != "current" or not run.input:
            run.status, run.reason = "blocked", "source_changed"
        elif reason := self._budget_reason(run):
            run.status, run.reason = "paused", reason
        else:
            if run.next_node == "plan":
                return self._plan(run)
            if run.next_node in {
                "question_plan",
                "explain_analysis",
                "compose_listing",
                "compose_support",
            }:
                return self._generate_content(run)
            return self._local(run)
        run.version += 1
        self._event(run, run.reason, run.status)
        return self._finish(run)

    def _approved(self, run: AgentExecution) -> bool:
        return any(
            s.node == run.next_node and s.reason == "approve" for s in self.repo.steps(run.id)
        )

    def _local(self, run: AgentExecution) -> AgentOutput:
        owner, shop, run_id, version = run.owner_id, run.shop_id, run.id, run.version
        node = run.next_node
        start = monotonic()
        inputs: dict[str, Any] | None = None
        result: dict[str, Any] | None = None
        failure: str | None = None
        try:
            with self.uow.session.begin_nested(), self.uow.defer_commits():
                if node == "verify":
                    result = self._verify(run)
                else:
                    require_skill(node)
                    data = StartAgent.model_validate(run.input)
                    skills = ControlledSkills(self.uow, owner, shop)
                    inputs = skills.inputs(node, data, run.result or {})
                    prepared = None
                    if node == "propose_tasks" and run.authorization_id:
                        prepared = AuthorizationsService(self.uow).prepare(run)
                    result = skills.call(
                        node, inputs, approved=prepared is not None or self._approved(run)
                    )
                    self._check_scope(node, data, result)
                    if prepared is not None:
                        AuthorizationsService(self.uow).consume(run, *prepared, result)
                self._dependencies(run, node, result)
                self._choose_next(run, node, result)
        except BusinessError as error:
            failure = error.code
            run.status, run.reason = "blocked", error.code
        except OperationalError as error:
            # Roll back a failed DB transaction before recording the attempt; don't retry writes.
            self.uow.session.rollback()
            run = self._load(owner, shop, run_id)
            if run.version != version or run.status != "ready":
                return self._finish(run)
            failure = "temporary_read_failure"
            spec = require_skill(node) if node != "verify" else None
            attempts = (
                sum(s.node == node and s.status == "failed" for s in self.repo.steps(run.id)) + 1
            )
            transient = (
                error.orig is not None
                and bool(error.orig.args)
                and error.orig.args[0] in {1205, 1213, 2006, 2013}
            )
            safe = (
                transient
                and spec is not None
                and not spec.side_effects
                and attempts < spec.max_attempts
            )
            run.status = "ready" if safe else "circuit_open"
            run.reason = failure if run.status == "ready" else "read_circuit_open"
        elapsed = max(1, int((monotonic() - start) * 1000))
        run.steps_used += 1
        run.elapsed_ms += elapsed
        run.version += 1
        self.repo.add(
            AgentStep(
                execution_id=run.id,
                node=node,
                skill=node if node != "verify" else "",
                status="failed" if failure else "completed",
                reason=failure or run.reason,
                next_node=run.next_node,
                input=inputs if not failure else None,
                output=result if not failure else None,
                duration_ms=elapsed,
            )
        )
        return self._finish(run)

    def _check_scope(self, node: str, data: StartAgent, result: dict[str, Any]) -> None:
        if node == "support_context":
            message = result["snapshot"]["message"]
            if (
                message["source"]["data_identity"] != data.scope.data_identity
                or message["channel"] != data.scope.channel
            ):
                raise BusinessError("scope_mismatch", "消息不属于所选身份或渠道", 403)
        if (
            node == "product_context"
            and result["product"]["source"]["data_identity"] != data.scope.data_identity
        ):
            raise BusinessError("scope_mismatch", "商品不属于所选数据身份", 403)
        if (
            node == "product_context"
            and data.template == "listing_model"
            and result["product"]["source"]["row_id"] != data.expected_product_source_row_id
        ):
            raise ConflictError("商品事实与本次同意发送的版本不同，请刷新后重新确认")
        if node == "message_context" and (
            result["message"]["source"]["data_identity"] != data.scope.data_identity
            or result["message"]["channel"] != data.scope.channel
        ):
            raise BusinessError("scope_mismatch", "消息不属于所选身份或渠道", 403)

    def _dependencies(self, run: AgentExecution, node: str, result: dict[str, Any]) -> None:
        batches, policies = evidence(result)
        self.repo.sources(run.id, batches, policies)
        if node in {"listing_draft", "listing_candidate", "product_context"}:
            listing_id = result.get("active_id") if node == "product_context" else result.get("id")
            if listing_id:
                self.repo.listing_sources(run.id, int(listing_id), run.owner_id, run.shop_id)
        if result.get("valid_until"):
            run.valid_until = datetime.fromisoformat(result["valid_until"]).replace(tzinfo=None)
        if node == "support_context":
            dates = [
                p["data"]["valid_until"]
                for p in result["snapshot"]["policies"]
                if p.get("data") and p["data"].get("valid_until")
            ]
            if dates:
                run.valid_until = min(datetime.fromisoformat(d).replace(tzinfo=None) for d in dates)

    def _choose_next(self, run: AgentExecution, node: str, result: dict[str, Any]) -> None:
        run.result, run.reason = result, ""
        if node == "data_check":
            if result["findings"]:
                run.next_node, run.status, run.reason = (
                    "propose_tasks",
                    "waiting_approval",
                    "findings_found",
                )
                if run.authorization_id:
                    try:
                        AuthorizationsService(self.uow).validate(
                            run, run.authorization_id, check_content=True
                        )
                        run.status, run.reason = "ready", "preauthorization_ready"
                    except BusinessError:
                        run.reason = "authorization_unavailable"
            else:
                run.next_node, run.status, run.reason = "end", "succeeded", "no_findings"
        elif node == "product_context":
            if result["product"]["facts"].strip():
                run.next_node, run.status = (
                    ("compose_listing", "ready")
                    if run.template == "listing_model"
                    else ("listing_draft", "waiting_approval")
                )
            else:
                run.status, run.reason = "waiting_input", "missing_product_facts"
        elif node == "message_context":
            run.next_node, run.status = "support_draft", "waiting_approval"
        elif node == "support_context":
            run.next_node, run.status = "compose_support", "ready"
        elif node == "metrics" and run.template == "question":
            run.next_node, run.status = "explain_analysis", "ready"
        elif node in {
            "propose_tasks",
            "listing_draft",
            "listing_candidate",
            "support_draft",
            "support_candidate",
            "analysis_todo",
        }:
            run.next_node, run.status = "verify", "ready"
            if node == "propose_tasks" and run.authorization_id:
                run.reason = "preauthorization_used"
        else:
            run.next_node, run.status = "end", "succeeded"

    def _verify(self, run: AgentExecution) -> dict[str, Any]:
        prior = run.result or {}
        last_skill = next(s.skill for s in reversed(self.repo.steps(run.id)) if s.skill)
        record_id = int(prior["id"])
        if last_skill == "analysis_todo":
            analysis = AnalyticsService(self.uow).get_saved(run.owner_id, run.shop_id, record_id)
            if analysis.status != "current" or analysis.todo is None:
                raise ConflictError("核验时分析来源或待办已变化")
            return {
                "record_type": "analysis",
                "record_id": record_id,
                "todo_id": analysis.todo.id,
                "status": analysis.todo.status,
                "external_status": "not_submitted",
            }
        if last_skill == "propose_tasks":
            result = OperationsService(self.uow).get_run(run.owner_id, run.shop_id, record_id)
            if result.source_status != "current":
                raise ConflictError("核验时来源已变化")
            return {
                "record_type": "operations",
                "record_id": record_id,
                "task_ids": result.snapshot.task_ids if result.snapshot else [],
                "status": "pending_individual_review",
                "external_status": "not_submitted",
            }
        if last_skill in {"listing_draft", "listing_candidate"}:
            listing = ListingService(self.uow).get(run.owner_id, run.shop_id, record_id)
            if listing.source_status != "current":
                raise ConflictError("核验时草稿来源已变化")
            return {
                "record_type": "listing",
                "record_id": record_id,
                "status": listing.status,
                "external_status": listing.external_status,
            }
        reply = SupportService(self.uow).get(run.owner_id, run.shop_id, record_id)
        if reply.source_status != "current":
            raise ConflictError("核验时消息或政策来源已变化")
        return {
            "record_type": "support",
            "record_id": record_id,
            "status": reply.status,
            "external_status": reply.external_status,
        }

    def _plan(self, run: AgentExecution) -> AgentOutput:
        data = StartAgent.model_validate(run.input)
        if not data.goal:
            run.status, run.reason = "blocked", "missing_goal"
            run.version += 1
            self._event(run, run.reason, run.status)
            return self._finish(run)
        status = self.model.status()
        if not data.allow_model or status.status != "configured":
            run.status = "waiting_configuration"
            run.reason = "model_consent_required" if not data.allow_model else "not_configured"
            run.model_status = status.status
            run.version += 1
            self._event(run, run.reason, run.status)
            return self._finish(run)
        reserve = self.model.reserve(data.goal)
        budget = Budget.model_validate(run.budget)
        if reserve <= 0 or run.spent_usd + run.reserved_usd + reserve > budget.max_cost_usd:
            run.status, run.reason = "paused", "cost_budget"
            run.version += 1
            self._event(run, run.reason, run.status)
            return self._finish(run)
        timeout = min(30.0, budget.max_seconds - run.elapsed_ms / 1000)
        lease = self._claim_model(run, data.goal, reserve, timeout)
        start = monotonic()
        try:
            reply = self.model.decide(data.goal, timeout)
        except BusinessError:
            reply = None  # Unknown state retains the reservation, never retries.
        elapsed = max(1, int((monotonic() - start) * 1000))
        return self._complete_plan(lease, reply, elapsed)

    def _claim_model(
        self, run: AgentExecution, goal: str, reserve: Decimal, timeout: float
    ) -> ModelLease:
        run.status, run.model_status = "running", "running"
        run.reserved_usd += reserve
        run.steps_used += 1
        run.version += 1
        run.lease_token = str(uuid4())
        run.lease_until = utc_now() + timedelta(seconds=timeout + 15)
        step = AgentStep(
            execution_id=run.id,
            node=run.next_node,
            status="running",
            input={
                "goal": goal,
                "model_configuration": self.model.status().model_dump(mode="json"),
            },
            output=None,
        )
        self.repo.add(step)
        lease = ModelLease(
            run.owner_id,
            run.shop_id,
            run.id,
            run.lease_token,
            run.version,
            step.id,
            reserve,
        )
        # Network I/O must occur with no open transaction or owner/shop lock.
        self.uow.commit()
        return lease

    def _generation_request(self, run: AgentExecution, data: StartAgent) -> dict[str, Any]:
        if run.next_node == "compose_support":
            support = SupportPreparation.model_validate(run.result)
            self._current_support(run, support)
            return support_request(data.goal, support)
        if run.next_node == "compose_listing":
            prepared = ListingPreparation.model_validate(run.result)
            self._current_listing(run, prepared)
            return listing_request(data.goal, prepared.product)
        if run.next_node == "question_plan":
            return question_request(data.goal, data.scope.model_dump(mode="json"))
        return explanation_request(data.goal, AnalysisResult.model_validate(run.result))

    def _current_support(self, run: AgentExecution, prepared: SupportPreparation) -> None:
        data = StartAgent.model_validate(run.input)
        if data.message_id is None or data.support_context is None:
            raise BusinessError("missing_object", "客服依据缺失", 422)
        with self.uow.defer_commits():
            current = SupportService(self.uow).prepare_candidate(
                run.owner_id,
                run.shop_id,
                data.message_id,
                data.support_context,
            )
        if current != prepared:
            raise ConflictError("消息、订单关联或适用政策已变化，请重新核对")

    def _current_listing(self, run: AgentExecution, prepared: ListingPreparation) -> None:
        current = ListingService(self.uow).workspace(
            run.owner_id, run.shop_id, prepared.product.product_id
        )
        if (
            current.product.source.row_id != prepared.product.source.row_id
            or current.active_id != prepared.active_id
        ):
            raise ConflictError("商品来源或本地生效版本已变化，请重新生成候选")

    def _generate_content(self, run: AgentExecution) -> AgentOutput:
        data = StartAgent.model_validate(run.input)
        status = self.model.status()
        listing = run.next_node == "compose_listing"
        support = run.next_node == "compose_support"
        consent = (
            data.allow_support_data
            if support
            else data.allow_listing_data
            if listing
            else data.allow_analysis_data
        )
        if not data.goal:
            run.status, run.reason = "blocked", "missing_goal"
        elif not data.allow_model or not consent:
            run.status = "waiting_configuration"
            run.reason = (
                "support_consent_required"
                if support
                else "listing_consent_required"
                if listing
                else "analysis_consent_required"
            )
        elif status.status != "configured":
            run.status, run.reason = "waiting_configuration", "not_configured"
            run.model_status = status.status
        else:
            try:
                request = self._generation_request(run, data)
                reserve = self.model.reserve_generation(request)
            except (BusinessError, ValueError) as error:
                run.status = "blocked"
                run.reason = (
                    error.code if isinstance(error, BusinessError) else "invalid_product_facts"
                )
                run.version += 1
                self._event(run, run.reason, run.status)
                return self._finish(run)
            budget = Budget.model_validate(run.budget)
            if reserve <= 0 or run.spent_usd + run.reserved_usd + reserve > budget.max_cost_usd:
                run.status, run.reason = "paused", "cost_budget"
            else:
                timeout = min(30.0, budget.max_seconds - run.elapsed_ms / 1000)
                lease = self._claim_model(run, data.goal, reserve, timeout)
                started = monotonic()
                try:
                    reply = self.model.generate(request, timeout)
                except BusinessError:
                    reply = GenerationReply(None, None)
                elapsed = max(1, int((monotonic() - started) * 1000))
                return self._complete_generation(lease, reply, elapsed)
        run.version += 1
        self._event(run, run.reason, run.status)
        return self._finish(run)

    def _complete_generation(
        self, lease: ModelLease, reply: GenerationReply, elapsed: int
    ) -> AgentOutput:
        run = self._load(lease.owner, lease.shop, lease.run_id)
        step = next(s for s in self.repo.steps(run.id) if s.id == lease.step_id)
        accepted = (
            run.lease_token == lease.token
            and run.version == lease.version
            and run.status == "running"
            and run.source_status == "current"
        )
        run.lease_token, run.lease_until = None, None
        run.elapsed_ms += elapsed
        run.version += 1
        step.duration_ms = elapsed
        if reply.cost is None:
            run.model_status, step.status, step.reason = (
                "result_unknown",
                "result_unknown",
                "model_result_unknown",
            )
            if run.status == "running":
                run.status, run.reason = "result_unknown", "model_result_unknown"
        else:
            run.reserved_usd -= lease.reserve
            run.spent_usd += reply.cost
            run.model_status = reply.engine
            step.status = "completed" if accepted else "discarded"
            if run.source_status != "cleared":
                step.output = {
                    "cost_usd": str(reply.cost),
                    "input_tokens": reply.input_tokens,
                    "output_tokens": reply.output_tokens,
                    "engine": reply.engine,
                }
            if accepted:
                try:
                    if reply.content is None:
                        raise ValueError("no valid content")
                    output = self._accept_generation(run, reply.content, reply.engine)
                    step.output = {**(step.output or {}), **output}
                except BusinessError as error:
                    run.status, run.reason = "blocked", error.code
                    step.status, step.reason = "failed", error.code
                except (ValidationError, ValueError, KeyError):
                    run.status, run.reason = "blocked", "invalid_model_output"
                    step.status, step.reason = "failed", "invalid_model_output"
            elif run.status == "running":
                run.status, run.reason = "blocked", "source_changed"
        step.next_node = run.next_node
        self.uow.record_event(
            run.owner_id,
            "agent.model_completed",
            "agent_execution",
            run.id,
            {"node": step.node, "status": step.status, "cost_known": reply.cost is not None},
        )
        return self._finish(run)

    def _accept_generation(
        self, run: AgentExecution, content: dict[str, Any], engine: str
    ) -> dict[str, Any]:
        if run.next_node == "compose_support":
            support = SupportPreparation.model_validate(run.result)
            self._current_support(run, support)
            selection = SupportSelection.model_validate(content)
            snapshot = compose_support(support, selection)
            if engine not in {"openai_responses", "dashscope_chat", "test_double"}:
                raise ValueError("Unknown composition engine")
            output = {
                "preparation": support.model_dump(mode="json"),
                "candidate": snapshot.model_dump(mode="json"),
                "selection": selection.model_dump(mode="json"),
                "engine": engine,
            }
            run.result = output
            run.status, run.reason, run.next_node = (
                "waiting_approval",
                "support_handoff" if snapshot.reasons else "support_candidate_ready",
                "support_candidate",
            )
            return output
        if run.next_node == "compose_listing":
            prepared = ListingPreparation.model_validate(run.result)
            self._current_listing(run, prepared)
            candidate = compose_listing(prepared.product, content)
            if candidate is None:
                run.status, run.reason = "waiting_input", "listing_needs_review"
                return {"next_action": "needs_review"}
            if engine not in {"openai_responses", "dashscope_chat", "test_double"}:
                raise ValueError("Unknown composition engine")
            output = {
                "preparation": prepared.model_dump(mode="json"),
                "candidate": candidate.model_dump(),
                "selection": content,
                "engine": engine,
            }
            run.result = output
            run.status, run.reason, run.next_node = (
                "waiting_approval",
                "listing_candidate_ready",
                "listing_candidate",
            )
            return output
        if run.next_node == "question_plan":
            decision = QuestionDecision.model_validate(content)
            output = decision.model_dump()
            if decision.intent == "unsupported":
                run.status, run.reason, run.next_node = "blocked", "unsupported_analysis", "end"
            else:
                run.result = output
                run.status, run.reason, run.next_node = "ready", "intent_selected", "metrics"
            return output
        analysis = AnalysisResult.model_validate(run.result)
        explanation = compose(analysis, content)
        run.result = {"analysis": analysis.model_dump(mode="json"), "explanation": explanation}
        if explanation["next_action"] == "offer_todo":
            run.status, run.reason, run.next_node = (
                "waiting_approval",
                "analysis_review_suggested",
                "analysis_todo",
            )
        else:
            run.status, run.reason, run.next_node = "succeeded", "analysis_explained", "end"
        return {"explanation": explanation}

    def _complete_plan(
        self, lease: ModelLease, reply: ModelReply | None, elapsed: int
    ) -> AgentOutput:
        run = self._load(lease.owner, lease.shop, lease.run_id)
        step = next(s for s in self.repo.steps(run.id) if s.id == lease.step_id)
        accepted = (
            run.lease_token == lease.token
            and run.version == lease.version
            and run.status == "running"
            and run.source_status == "current"
        )
        run.lease_token, run.lease_until = None, None
        run.elapsed_ms += elapsed
        run.version += 1
        step.duration_ms = elapsed
        if reply is None:
            run.model_status, step.status, step.reason = (
                "result_unknown",
                "result_unknown",
                "model_result_unknown",
            )
            if run.status == "running":
                run.status, run.reason = "result_unknown", "model_result_unknown"
        else:
            run.reserved_usd -= lease.reserve
            run.spent_usd += reply.cost
            run.model_status = reply.engine
            step.status = "completed" if accepted else "discarded"
            if run.source_status != "cleared":
                step.output = {
                    "intent": reply.decision.intent,
                    "input_tokens": reply.input_tokens,
                    "output_tokens": reply.output_tokens,
                    "cost_usd": str(reply.cost),
                    "engine": reply.engine,
                }
            if accepted:
                self._accept_plan(run, reply)
            elif run.status == "running":
                run.status, run.reason = "blocked", "source_changed"
        return self._finish(run)

    def _accept_plan(self, run: AgentExecution, reply: ModelReply) -> None:
        if reply.decision.intent == "blocked":
            run.status, run.reason = "blocked", "policy_denied"
            run.next_node = "end"
        else:
            run.next_node = FIRST_NODE[reply.decision.intent]
            budget = Budget.model_validate(run.budget)
            reason = self._budget_reason(run)
            if run.spent_usd >= budget.max_cost_usd:
                reason = "cost_budget"
            run.status, run.reason = ("paused", reason) if reason else ("ready", "intent_selected")
