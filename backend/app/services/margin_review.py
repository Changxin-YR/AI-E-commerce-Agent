"""Bounded, evidence-based local recommendations; no model or external writes."""

import re

from app.core.errors import BusinessError, ConflictError
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.margin_review import (
    MarginEvidence,
    MarginInput,
    MarginListing,
    MarginRecommendation,
)
from app.services.listings import ListingService

PARAMETER = re.compile(r"^[^:：\r\n]{1,80}[:：]\s*\S.*$")


class MarginReviewService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def _listing(
        self, owner: int, shop: int, data: MarginInput
    ) -> tuple[MarginListing | None, str]:
        if data.product_id is None:
            return None, "未选择商品；如需核对内容，请先选定一个本范围商品。"
        workspace = ListingService(self.uow).workspace(owner, shop, data.product_id)
        evidence = self.uow.listings.product(owner, shop, data.product_id)
        assert evidence is not None  # workspace already required this owned source.
        scope = data.analysis.scope
        if (
            evidence[2].data_identity != scope.data_identity
            or evidence[2].source_channel != scope.channel
        ):
            raise BusinessError("scope_mismatch", "商品不属于所选身份或渠道", 403)
        if workspace.product.sku not in {line.sku for line in data.analysis.lines if line.included}:
            return None, "所选商品没有本时间窗内符合口径的订单，请人工核对对象范围。"
        active = workspace.active_version
        if not active or active.source_status != "current" or not active.snapshot:
            return None, "缺少当前有效的已批准本地版本，先到Listing页面核对基线。"
        parameters = [
            line.strip()
            for line in workspace.product.facts.splitlines()
            if PARAMETER.fullmatch(line.strip())
        ]
        if not parameters:
            return None, "商品来源缺少明确的“参数名:值”行，请人工补充事实依据。"
        before = active.snapshot.proposed
        present = {line.strip() for line in before.description.splitlines()} | set(
            before.title.split(" · ")
        )
        missing = list(dict.fromkeys(line for line in parameters if line not in present))
        if not missing:
            return None, "当前本地版本已包含来源中的明确参数；本次未发现可执行的内容遗漏。"
        return MarginListing(
            product=workspace.product,
            active_id=active.id,
            before=before,
            missing_parameters=missing,
        ), "只比较来源参数与本地已批准版本，外部刊登和类目要求须人工核对。"

    def prepare(self, owner: int, shop_id: int, data: MarginInput) -> MarginEvidence:
        self.uow.identity.lock_user(owner)
        shop = self.uow.identity.get_shop(owner, shop_id, lock=True)
        if shop is None:
            raise BusinessError("not_found", "店铺不存在", 404)
        analysis = data.analysis
        if shop.data_revision != analysis.source_revision:
            raise ConflictError("分析来源已变化，请重新运行")
        included = [line for line in analysis.lines if line.included]
        listing, note = self._listing(owner, shop_id, data)
        gaps = list(dict.fromkeys(gap for line in included for gap in line.gaps))
        recommendations: list[MarginRecommendation] = []
        save_analysis = bool(included) and (
            not analysis.ranking_available or bool(analysis.candidates)
        )
        if not included:
            recommendations.append(
                MarginRecommendation(
                    kind="input",
                    title="补充范围内订单",
                    evidence="本次没有符合币种、身份、渠道和7天窗口的已支付订单行。",
                    action="导入或核对订单后新建任务。",
                    risk="R0",
                )
            )
        elif not analysis.ranking_available:
            recommendations.append(
                MarginRecommendation(
                    kind="cost",
                    title="补齐数据与成本依据",
                    evidence="完整毛利排行不可用；请查看逐行缺口及币种提示。",
                    action="批准后保存当前分析及一个核对待办，再补录凭据。",
                    risk="R1",
                )
            )
        elif analysis.candidates:
            historical = analysis.scope.cost_mode == "seller_history"
            recommendations.append(
                MarginRecommendation(
                    kind="pricing" if historical else "cost",
                    title="复核定价、成本与费用" if historical else "核实当前成本估算",
                    evidence=f"在所选口径下命中{len(analysis.candidates)}个低毛利SKU；{analysis.cost_basis}",
                    action="批准后保存定价/成本核对分析草稿与待办；费用仍待核实，实际调价由卖家另行决定。",
                    risk="R1",
                )
            )
        if listing:
            recommendations.append(
                MarginRecommendation(
                    kind="listing",
                    title="补回有来源依据的商品参数",
                    evidence=f"所选商品{listing.product.sku}的本地已批准版本遗漏{len(listing.missing_parameters)}条明确来源参数。",
                    action="单独批准后，使用完整已知事实保存Listing模板草稿。此内容遗漏与毛利之间的因果关系未确认。",
                    risk="R1",
                )
            )
        return MarginEvidence(
            scope=analysis.scope,
            source_revision=analysis.source_revision,
            included_lines=len(included),
            ranking_available=analysis.ranking_available,
            candidate_count=len(analysis.candidates),
            candidates=analysis.candidates[:20],
            cost_basis=analysis.cost_basis,
            fee_gaps=analysis.fee_gaps,
            data_gaps=gaps[:20],
            recommendations=recommendations,
            save_analysis=save_analysis,
            listing=listing,
            listing_note=note,
        )

    def require_current(self, owner: int, shop: int, plan: MarginEvidence) -> None:
        if plan.listing is None:
            return
        if not self.uow.listings.margin_current(owner, shop, plan.listing):
            raise ConflictError("本地Listing基线或商品来源已变化，请重新复核")
