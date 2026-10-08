import hashlib
import json

from app.core.errors import BusinessError, ConflictError
from app.core.time import utc_now
from app.models.analytics import AnalysisTodo, SavedAnalysis
from app.models.identity import Shop
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.analytics import (
    AnalysisInput,
    AnalysisResult,
    Intent,
    QuestionInput,
    SavedOutput,
    SaveInput,
    SourceOutput,
    TodoOutput,
)
from app.services.profit_calculation import calculate, reference, utc_text

QUESTIONS: dict[str, Intent] = {
    "查看销售与已知毛利": "summary",
    "销量前五的 SKU": "sales",
    "哪些商品销量高但已知毛利低": "low_margin",
}


class AnalyticsService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.analytics

    def _shop(self, owner_id: int, shop_id: int) -> Shop:
        # Same lock order as imports: user -> shop -> source rows -> derived rows.
        self.uow.identity.lock_user(owner_id)
        shop = self.uow.identity.get_shop(owner_id, shop_id, lock=True)
        if shop is None:
            raise BusinessError("not_found", "店铺不存在", 404)
        return shop

    def run(self, owner_id: int, shop_id: int, scope: AnalysisInput) -> AnalysisResult:
        shop = self._shop(owner_id, shop_id)
        orders = self.repo.orders(
            owner_id,
            shop_id,
            scope.start_at.replace(tzinfo=None),
            scope.end_at.replace(tzinfo=None),
            scope.data_identity,
        )
        if len(orders) > 10000:
            raise BusinessError("range_too_large", "时间窗超过 10000 行，请缩小范围", 422)
        skus = {
            order.sku for order, _, batch in orders if batch.data_identity == scope.data_identity
        }
        products = self.repo.products(owner_id, shop_id, skus) if skus else []
        return calculate(orders, products, scope, shop.data_revision, utc_now())

    def ask(self, owner_id: int, shop_id: int, data: QuestionInput) -> AnalysisResult:
        self._shop(owner_id, shop_id)
        intent = QUESTIONS.get(data.question.rstrip("？?。 "))
        if intent is None:
            raise BusinessError(
                "unsupported_question",
                "当前为本地受控规则，仅支持：查看销售与已知毛利、销量前五的 SKU、"
                "哪些商品销量高但已知毛利低。物流费用、净利润及自由问答暂缺数据或模型配置。",
                422,
            )
        return self.run(owner_id, shop_id, data.scope.model_copy(update={"intent": intent}))

    def _output(self, analysis: SavedAnalysis, *, include_snapshot: bool = True) -> SavedOutput:
        todo = self.repo.todo(analysis.owner_id, analysis.id)
        return SavedOutput(
            id=analysis.id,
            shop_id=analysis.shop_id,
            source_revision=analysis.source_revision,
            status=analysis.status,
            created_at=utc_text(analysis.created_at),
            scope=AnalysisInput.model_validate(analysis.scope),
            snapshot=AnalysisResult.model_validate(analysis.snapshot)
            if include_snapshot and analysis.snapshot
            else None,
            todo=TodoOutput.model_validate(todo) if todo else None,
        )

    def save(self, owner_id: int, shop_id: int, data: SaveInput) -> SavedOutput:
        result = self.run(owner_id, shop_id, data.scope)
        if data.expected_revision != result.source_revision:
            raise ConflictError("数据已变化，请重新计算后保存")
        canonical = json.dumps(
            [shop_id, result.source_revision, data.scope.model_dump(mode="json")],
            sort_keys=True,
            ensure_ascii=False,
        )
        key = hashlib.sha256(canonical.encode()).hexdigest()
        existing = self.repo.by_key(owner_id, key)
        if existing:
            if existing.status == "cleared":
                raise ConflictError("此分析的来源已清除，请重新计算")
            return self._output(existing)
        analysis = SavedAnalysis(
            owner_id=owner_id,
            shop_id=shop_id,
            request_key=key,
            source_revision=result.source_revision,
            scope=data.scope.model_dump(mode="json"),
            snapshot=result.model_dump(mode="json"),
            status="current",
        )
        batches = {
            ref.batch_id
            for line in result.lines
            for ref in [line.source, line.cost_source]
            if ref is not None
        }
        self.repo.add(analysis, batches)
        self.uow.record_event(
            owner_id,
            "analysis.saved",
            "analysis",
            analysis.id,
            {"revision": result.source_revision},
        )
        output = self._output(analysis)
        self.uow.commit()
        return output

    def list_saved(self, owner_id: int, shop_id: int) -> list[SavedOutput]:
        self._shop(owner_id, shop_id)
        return [
            self._output(item, include_snapshot=False)
            for item in self.repo.saved(owner_id, shop_id)
        ]

    def get_saved(self, owner_id: int, shop_id: int, analysis_id: int) -> SavedOutput:
        self._shop(owner_id, shop_id)
        analysis = self.repo.find_saved(owner_id, shop_id, analysis_id)
        if analysis is None:
            raise BusinessError("not_found", "分析不存在", 404)
        return self._output(analysis)

    def revision(self, owner_id: int, shop_id: int) -> int:
        return self._shop(owner_id, shop_id).data_revision

    def create_todo(self, owner_id: int, shop_id: int, analysis_id: int) -> SavedOutput:
        shop = self._shop(owner_id, shop_id)
        analysis = self.repo.find_saved(owner_id, shop_id, analysis_id)
        if analysis is None:
            raise BusinessError("not_found", "分析不存在", 404)
        if analysis.status != "current" or analysis.source_revision != shop.data_revision:
            raise ConflictError("分析已失效或来源已清除，请重新计算后创建待办")
        if not self.repo.todo(owner_id, analysis_id):
            self.repo.add_todo(
                AnalysisTodo(
                    analysis_id=analysis_id,
                    title="核对销售与已知毛利及缺失费用",
                    status="open",
                )
            )
            self.uow.record_event(owner_id, "analysis.todo_created", "analysis", analysis.id)
            output = self._output(analysis)
            self.uow.commit()
            return output
        return self._output(analysis)

    def source(self, owner_id: int, shop_id: int, row_id: int) -> SourceOutput:
        self._shop(owner_id, shop_id)
        evidence = self.repo.source(owner_id, shop_id, row_id)
        if evidence is None:
            raise BusinessError("not_found", "来源不存在或已清除", 404)
        row, batch = evidence
        return SourceOutput(
            reference=reference(row, batch),
            batch_status=batch.status,
            raw=row.raw,
            corrections=row.corrections,
            normalized=row.normalized,
        )
