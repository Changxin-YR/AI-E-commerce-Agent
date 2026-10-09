import hashlib
import json
from collections import defaultdict
from typing import Any

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.identity import Shop
from app.models.product_quality import ProductQualityReport
from app.repositories.product_quality import MAX_PRODUCTS
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.product_quality import (
    QualityPage,
    QualityProduct,
    QualityResult,
    QualitySave,
    QualitySaved,
    QualityScope,
)
from app.services.product_quality_rules import (
    LIMITATIONS,
    RULE_VERSION,
    assess,
    coverage,
    normalized,
)
from app.services.profit_calculation import reference, utc_text

MAX_REPORT_BYTES = 2_000_000


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class ProductQualityService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.product_quality

    def _shop(self, owner: int, shop_id: int) -> Shop:
        self.uow.identity.lock_user(owner)
        shop = self.uow.identity.get_shop(owner, shop_id, lock=True)
        if shop is None:
            raise NotFoundError()
        return shop

    def _calculate(self, owner: int, shop: Shop, scope: QualityScope) -> QualityResult:
        rows = self.repo.products(owner, shop.id, scope)
        if len(rows) > MAX_PRODUCTS:
            raise BusinessError(
                "range_too_large", "商品超过 1000 个，请按来源渠道或 SKU 前缀缩小范围。", 422
            )
        groups: dict[str, list[str]] = defaultdict(list)
        for product, _, _ in rows:
            groups[normalized(product.sku)].append(product.sku)
        items = []
        for product, row, batch in rows:
            peers = [sku for sku in groups[normalized(product.sku)] if sku != product.sku]
            items.append(
                QualityProduct(
                    product_id=product.id,
                    sku=product.sku,
                    name=product.name,
                    facts=product.facts,
                    price=product.price,
                    currency=product.currency,
                    unit_cost=product.unit_cost,
                    cost_currency=product.cost_currency,
                    channel=batch.source_channel,
                    source=reference(row, batch),
                    issues=assess(product, len(peers)),
                    similar_skus=peers[:20],
                    similar_sku_count=len(peers),
                )
            )
        result = QualityResult(
            shop_id=shop.id,
            scope=scope,
            source_revision=shop.data_revision,
            checked_at=utc_text(utc_now()),
            rule_version=RULE_VERSION,
            preview_hash="",
            product_count=len(items),
            affected_products=sum(bool(p.issues) for p in items),
            missing_count=sum(i.status == "missing" for p in items for i in p.issues),
            review_count=sum(i.status == "review" for p in items for i in p.issues),
            coverage=coverage(bool(items)),
            limitations=LIMITATIONS,
            products=items,
        )
        if len(result.model_dump_json().encode()) > MAX_REPORT_BYTES:
            raise BusinessError(
                "range_too_large", "检查正文超过 2 MB，请按渠道或 SKU 前缀缩小范围。", 422
            )
        result.preview_hash = digest(
            result.model_dump(mode="json", exclude={"checked_at", "preview_hash"})
        )
        return result

    def preview(self, owner: int, shop_id: int, scope: QualityScope) -> QualityResult:
        result = self._calculate(owner, self._shop(owner, shop_id), scope)
        self.uow.commit()
        return result

    def save(self, owner: int, shop_id: int, data: QualitySave) -> QualitySaved:
        shop = self._shop(owner, shop_id)
        request_hash = digest(
            {"shop_id": shop_id, **data.model_dump(mode="json", exclude={"request_id"})}
        )
        existing = self.repo.by_request(owner, str(data.request_id))
        if existing:
            if existing.shop_id != shop_id or existing.request_hash != request_hash:
                raise ConflictError("请求标识已用于其他质量检查预览。")
            output = self._output(existing)
            self.uow.commit()
            return output
        result = self._calculate(owner, shop, data.scope)
        if (
            result.source_revision != data.expected_revision
            or result.preview_hash != data.expected_preview_hash
        ):
            raise ConflictError("检查范围、规则或来源已变化，请重新检查并确认后保存。")
        report = ProductQualityReport(
            owner_id=owner,
            shop_id=shop_id,
            request_id=str(data.request_id),
            request_hash=request_hash,
            scope=data.scope.model_dump(mode="json"),
            snapshot=result.model_dump(mode="json"),
            status="current",
        )
        self.repo.add(report, {p.source.batch_id for p in result.products})
        self.uow.record_event(owner, "product_quality.saved", "product_quality", report.id)
        output = self._output(report)
        self.uow.commit()
        return output

    def _output(self, report: ProductQualityReport, include_snapshot: bool = True) -> QualitySaved:
        return QualitySaved(
            id=report.id,
            shop_id=report.shop_id,
            status=report.status,
            created_at=utc_text(report.created_at),
            scope=QualityScope.model_validate(report.scope),
            snapshot=QualityResult.model_validate(report.snapshot)
            if include_snapshot and report.snapshot
            else None,
        )

    def get(self, owner: int, shop: int, report_id: int) -> QualitySaved:
        self._shop(owner, shop)
        report = self.repo.get(owner, shop, report_id)
        if report is None:
            raise NotFoundError()
        output = self._output(report)
        self.uow.commit()
        return output

    def page(self, owner: int, shop: int, before: int | None) -> QualityPage:
        self._shop(owner, shop)
        reports = self.repo.page(owner, shop, before)
        output = QualityPage(
            items=[self._output(r, False) for r in reports[:20]],
            next_cursor=reports[19].id if len(reports) > 20 else None,
        )
        self.uow.commit()
        return output

    def clear(self, owner: int, shop: int, report_id: int) -> QualitySaved:
        self._shop(owner, shop)
        report = self.repo.get(owner, shop, report_id)
        if report is None:
            raise NotFoundError()
        if report.status != "cleared":
            self.repo.clear(report)
            self.uow.record_event(owner, "product_quality.cleared", "product_quality", report.id)
        output = self._output(report)
        self.uow.commit()
        return output
