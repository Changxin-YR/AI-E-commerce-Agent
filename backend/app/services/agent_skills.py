"""Closed registry: definitions describe code-owned business services, never executable text."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.errors import BusinessError
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import SkillDefinition, StartAgent
from app.schemas.analytics import AnalysisInput, AnalysisResult
from app.schemas.common import InputModel, OutputModel
from app.schemas.listings import GenerateInput, ListingContent, ListingOutput, ProductFacts
from app.schemas.operations import CheckPreview, OperationScope, RunInput, RunOutput
from app.schemas.support import GenerateReply, MessageFacts, ReplyOutput
from app.services.analytics import AnalyticsService
from app.services.listing_generation import FactTemplateGenerator
from app.services.listings import ListingService
from app.services.operations import OperationsService
from app.services.support import SupportService


class ObjectInput(InputModel):
    object_id: int


class ListingPreparation(OutputModel):
    product: ProductFacts
    active_id: int | None
    before: ListingContent | None


class SupportInput(GenerateReply):
    message_id: int


class SupportPreparation(OutputModel):
    message: MessageFacts


@dataclass(frozen=True)
class Contract:
    purpose: str
    tool: str
    input: type[BaseModel]
    output: type[BaseModel]
    writes: bool = False


CONTRACTS = {
    "data_check": Contract(
        "检查导入数据与异常证据", "operations.preview", OperationScope, CheckPreview
    ),
    "metrics": Contract(
        "确定性销售与已知毛利；全店所选身份，不按渠道过滤",
        "analytics.run",
        AnalysisInput,
        AnalysisResult,
    ),
    "propose_tasks": Contract(
        "将已审阅异常保存为待审批候选", "operations.run", RunInput, RunOutput, True
    ),
    "product_context": Contract(
        "读取商品与当前本地版本", "listings.workspace", ObjectInput, ListingPreparation
    ),
    "listing_draft": Contract(
        "保存本地事实模板草稿", "listings.generate", GenerateInput, ListingOutput, True
    ),
    "message_context": Contract(
        "读取待回复消息", "support.workspace", ObjectInput, SupportPreparation
    ),
    "support_draft": Contract(
        "保存未核验订单的人工接管草稿", "support.generate", SupportInput, ReplyOutput, True
    ),
}


def definition(name: str, contract: Contract) -> SkillDefinition:
    return SkillDefinition(
        name=name,
        version="1",
        purpose=contract.purpose,
        input_schema=contract.input.model_json_schema(),
        input_sources=["当前卖家指定店铺/数据身份/时间窗", "受控业务服务的当前来源与版本"],
        output_schema=contract.output.model_json_schema(),
        permissions=["shop:owned", "internal:write" if contract.writes else "data:read"],
        tools=[contract.tool],
        read_scope="当前用户拥有的指定店铺，逐项核对数据身份与来源",
        write_scope="指定店铺的内部候选或草稿" if contract.writes else "无业务写入",
        risk="R1" if contract.writes else "R0",
        side_effects=contract.writes,
        preconditions=["店铺归属校验", "输入类型与来源有效性校验", "写入须审批当前节点"],
        idempotency="执行请求 UUID + 业务服务来源/版本去重；本地变更与步骤原子提交",
        max_attempts=1 if contract.writes else 3,
        failure_policy="硬规则拒绝即停止；只读临时故障至多三次，之后熔断；写入不自动重试",
        confirmation="回读业务记录 ID、来源状态及本地状态；外部固定未提交",
    )


REGISTRY = {name: definition(name, contract) for name, contract in CONTRACTS.items()}


def require_skill(name: str) -> SkillDefinition:
    try:
        contract = CONTRACTS[name]
        spec = SkillDefinition.model_validate(REGISTRY[name].model_dump())
    except (KeyError, ValidationError, AttributeError) as error:
        raise BusinessError("invalid_skill", "技能未注册或元数据无效", 422) from error
    if spec != definition(name, contract):
        raise BusinessError("skill_policy_denied", "技能权限或元数据不匹配，已阻断", 403)
    return spec


def evidence(value: Any) -> tuple[set[int], set[int]]:
    """Extract dependencies only from validated business output, not from model text."""
    batches: set[int] = set()
    policies: set[int] = set()
    if isinstance(value, dict):
        if "batch_id" in value and "row_id" in value and "row_number" in value:
            batches.add(int(value["batch_id"]))
        for key, child in value.items():
            if key == "policies" and isinstance(child, list):
                policies.update(int(p["id"]) for p in child if isinstance(p, dict) and "id" in p)
            b, p = evidence(child)
            batches.update(b)
            policies.update(p)
    elif isinstance(value, list):
        for child in value:
            b, p = evidence(child)
            batches.update(b)
            policies.update(p)
    return batches, policies


class ControlledSkills:
    def __init__(self, uow: UnitOfWork, owner: int, shop: int) -> None:
        self.uow, self.owner, self.shop = uow, owner, shop

    def inputs(self, name: str, data: StartAgent, prior: dict[str, Any]) -> dict[str, Any]:
        if name == "data_check":
            return data.scope.model_dump(mode="json")
        if name == "metrics":
            return (
                AnalysisInput.model_validate(
                    {
                        k: v
                        for k, v in data.scope.model_dump().items()
                        if k in AnalysisInput.model_fields
                    }
                )
                .model_copy(update={"intent": "summary"})
                .model_dump(mode="json")
            )
        if name == "propose_tasks":
            return RunInput(request_id=data.request_id, scope=data.scope).model_dump(mode="json")
        if name in {"product_context", "message_context"}:
            target = data.product_id if name == "product_context" else data.message_id
            if target is None:
                raise BusinessError("missing_object", "请在业务页面选择商品或消息后启动", 422)
            return {"object_id": target}
        if name == "listing_draft":
            prepared = ListingPreparation.model_validate(prior)
            return GenerateInput(
                product_id=prepared.product.product_id,
                expected_source_row_id=prepared.product.source.row_id,
                expected_active_id=prepared.active_id,
            ).model_dump(mode="json")
        prepared_message = SupportPreparation.model_validate(prior)
        return SupportInput(
            message_id=prepared_message.message.id,
            expected_source_row_id=prepared_message.message.source.row_id,
        ).model_dump(mode="json")

    def call(self, name: str, payload: dict[str, Any], *, approved: bool) -> dict[str, Any]:
        spec = require_skill(name)
        if spec.side_effects and not approved:
            raise BusinessError("approval_required", "当前节点尚未批准", 403)
        contract = CONTRACTS[name]
        try:
            args = contract.input.model_validate(payload)
        except ValidationError as error:
            raise BusinessError("invalid_skill_input", "技能输入缺失或类型无效", 422) from error
        # Dispatch is explicit; metadata and model output cannot choose arbitrary methods.
        result: BaseModel
        if name == "data_check":
            result = OperationsService(self.uow).preview(
                self.owner, self.shop, OperationScope.model_validate(args)
            )
        elif name == "metrics":
            result = AnalyticsService(self.uow).run(
                self.owner, self.shop, AnalysisInput.model_validate(args)
            )
        elif name == "propose_tasks":
            result = OperationsService(self.uow).run(
                self.owner, self.shop, RunInput.model_validate(args)
            )
        elif name == "product_context":
            workspace = ListingService(self.uow).workspace(
                self.owner, self.shop, ObjectInput.model_validate(args).object_id
            )
            result = ListingPreparation(
                product=workspace.product,
                active_id=workspace.active_id,
                before=workspace.active_version.snapshot.proposed
                if workspace.active_version and workspace.active_version.snapshot
                else None,
            )
        elif name == "listing_draft":
            result = ListingService(self.uow).generate(
                self.owner, self.shop, GenerateInput.model_validate(args), FactTemplateGenerator()
            )
        elif name == "message_context":
            message = (
                SupportService(self.uow)
                .workspace(self.owner, self.shop, ObjectInput.model_validate(args).object_id)
                .message
            )
            result = SupportPreparation(message=message)
        else:
            support = SupportInput.model_validate(args)
            result = SupportService(self.uow).generate(
                self.owner,
                self.shop,
                support.message_id,
                GenerateReply.model_validate(support.model_dump(exclude={"message_id"})),
            )
        try:
            return contract.output.model_validate(result).model_dump(mode="json")
        except ValidationError as error:
            raise BusinessError("invalid_skill_output", "技能输出未通过类型校验", 422) from error
