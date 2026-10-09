import hashlib
import json
from typing import Any

from app.core.errors import BusinessError, ConflictError
from app.core.time import utc_now
from app.models.listings import ListingVersion
from app.repositories.analytics import ProductEvidence
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.listings import (
    CandidateInput,
    DecisionInput,
    GenerateInput,
    ListingContent,
    ListingOutput,
    ListingSnapshot,
    ProductFacts,
    ProductWorkspace,
    ReviseInput,
)
from app.services.listing_generation import ListingGenerator, check_content
from app.services.profit_calculation import reference, utc_text


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def product_facts(evidence: ProductEvidence) -> ProductFacts:
    product, row, batch = evidence
    return ProductFacts(
        product_id=product.id,
        sku=product.sku,
        name=product.name,
        facts=product.facts,
        source=reference(row, batch),
    )


def output(item: ListingVersion) -> ListingOutput:
    return ListingOutput(
        id=item.id,
        shop_id=item.shop_id,
        number=item.number,
        version=item.version,
        status=item.status,
        source_status=item.source_status,
        base_version_id=item.base_version_id,
        engine=item.engine,
        snapshot=ListingSnapshot.model_validate(item.snapshot) if item.snapshot else None,
        created_at=utc_text(item.created_at),
        decided_at=utc_text(item.decided_at) if item.decided_at else None,
    )


class ListingService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.listings

    def _shop(self, owner: int, shop: int) -> None:
        self.uow.identity.lock_user(owner)
        if self.uow.identity.get_shop(owner, shop, lock=True) is None:
            raise BusinessError("not_found", "店铺不存在", 404)

    def _product(self, owner: int, shop: int, product_id: int) -> ProductFacts:
        evidence = self.repo.product(owner, shop, product_id)
        if evidence is None:
            raise BusinessError("not_found", "商品不存在或来源已撤销，请重新选择商品", 404)
        return product_facts(evidence)

    def _item(self, owner: int, shop: int, listing_id: int) -> ListingVersion:
        item = self.repo.find(owner, shop, listing_id)
        if item is None:
            raise BusinessError("not_found", "Listing 版本不存在", 404)
        return item

    def products(self, owner: int, shop: int, query: str, offset: int) -> list[ProductFacts]:
        self._shop(owner, shop)
        return [product_facts(e) for e in self.repo.products(owner, shop, query, offset)]

    def workspace(self, owner: int, shop: int, product_id: int) -> ProductWorkspace:
        self._shop(owner, shop)
        product = self._product(owner, shop, product_id)
        key = digest([shop, product.sku])
        active = self.repo.active(owner, shop, key)
        return ProductWorkspace(
            product=product,
            active_id=active.id if active else None,
            active_version=output(active) if active else None,
            versions=[output(v) for v in self.repo.versions(owner, shop, key)],
        )

    def history(self, owner: int, shop: int) -> list[ListingOutput]:
        self._shop(owner, shop)
        return [output(v) for v in self.repo.versions(owner, shop)]

    def get(self, owner: int, shop: int, listing_id: int) -> ListingOutput:
        self._shop(owner, shop)
        return output(self._item(owner, shop, listing_id))

    def _active(
        self, owner: int, shop: int, key: str, expected: int | None
    ) -> ListingVersion | None:
        active = self.repo.active(owner, shop, key)
        if (active.id if active else None) != expected:
            raise ConflictError("本地生效版本已变化，请刷新并核对新旧差异")
        return active

    def _save(
        self,
        owner: int,
        shop: int,
        product: ProductFacts,
        content: ListingContent,
        active: ListingVersion | None,
        request_key: str,
        engine: str,
        inherited: set[int] | None = None,
    ) -> ListingVersion:
        key = digest([shop, product.sku])
        before = ListingContent(title=product.name, description=product.facts)
        batches = {product.source.batch_id} | (inherited or set())
        if active and active.snapshot:
            before = ListingSnapshot.model_validate(active.snapshot).proposed
            batches |= self.repo.batches(owner, shop, active.id)
        snapshot = ListingSnapshot(
            product=product,
            before=before,
            proposed=content,
            missing=[]
            if product.facts.strip()
            else ["缺少可核对商品参数；当前仅能使用商品名，请补充参数文件。"],
            blockers=check_content(product.name, product.facts, content),
        )
        item = ListingVersion(
            owner_id=owner,
            shop_id=shop,
            product_key=key,
            request_key=request_key,
            number=self.repo.next_number(owner, shop, key),
            version=1,
            status="draft",
            source_status="current",
            source_row_id=product.source.row_id,
            base_version_id=active.id if active else None,
            engine=engine,
            snapshot=snapshot.model_dump(mode="json"),
        )
        self.repo.add(item, batches)
        self.uow.record_event(
            owner,
            "listing.draft_created",
            "listing",
            item.id,
            {"number": item.number, "engine": engine, "blockers": len(snapshot.blockers)},
        )
        return item

    def _finish(self, item: ListingVersion) -> ListingOutput:
        self.uow.session.flush()
        result = output(item)
        self.uow.commit()
        return result

    def generate(
        self, owner: int, shop: int, data: GenerateInput, generator: ListingGenerator
    ) -> ListingOutput:
        self._shop(owner, shop)
        product = self._product(owner, shop, data.product_id)
        if product.source.row_id != data.expected_source_row_id:
            raise ConflictError("商品来源已变化，请刷新后重新生成")
        active = self._active(owner, shop, digest([shop, product.sku]), data.expected_active_id)
        request_key = digest(
            [
                "generate",
                shop,
                product.source.row_id,
                data.expected_active_id,
                generator.engine,
                self.repo.invalidation_epoch(owner, shop, digest([shop, product.sku])),
            ]
        )
        existing = self.repo.by_key(owner, request_key)
        if existing:
            return output(existing)
        try:
            content = ListingContent.model_validate(generator.generate(product.name, product.facts))
        except Exception as error:
            # Do not persist provider text, credentials, or an invented successful draft.
            self.uow.record_event(
                owner,
                "listing.generation_failed",
                "shop",
                shop,
                {"reason": "invalid_or_unavailable_generator"},
            )
            self.uow.commit()
            raise BusinessError(
                "generation_failed", "生成器暂不可用或返回格式无效，请稍后重试", 502
            ) from error
        return self._finish(
            self._save(owner, shop, product, content, active, request_key, generator.engine)
        )

    def _current_product(self, owner: int, shop: int, item: ListingVersion) -> ProductFacts:
        if item.source_status != "current" or not item.snapshot:
            raise ConflictError("来源已变化或清除，请选择当前商品重新生成草稿")
        snapshot = ListingSnapshot.model_validate(item.snapshot)
        product = self._product(owner, shop, snapshot.product.product_id)
        if product.source.row_id != item.source_row_id:
            raise ConflictError("商品来源已变化，请重新生成草稿")
        return product

    def save_candidate(self, owner: int, shop: int, data: CandidateInput) -> ListingOutput:
        self._shop(owner, shop)
        product = self._product(owner, shop, data.product_id)
        if product.source.row_id != data.expected_source_row_id:
            raise ConflictError("商品来源已变化，请重新生成候选")
        key = digest([shop, product.sku])
        active = self._active(owner, shop, key, data.expected_active_id)
        facts = {line.strip() for line in product.facts.splitlines() if line.strip()}
        descriptions = [
            line.strip() for line in data.content.description.splitlines() if line.strip()
        ]
        if (
            check_content(product.name, product.facts, data.content)
            or not facts
            or set(descriptions) != facts
            or len(descriptions) != len(facts)
        ):
            raise BusinessError("fact_check_required", "候选须完整保留已核对参数", 422)
        request_key = digest(
            [
                "model_candidate",
                shop,
                product.source.row_id,
                data.expected_active_id,
                data.content.model_dump(),
                data.engine,
                self.repo.invalidation_epoch(owner, shop, key),
            ]
        )
        existing = self.repo.by_key(owner, request_key)
        if existing:
            return output(existing)
        return self._finish(
            self._save(owner, shop, product, data.content, active, request_key, data.engine)
        )

    def revise(self, owner: int, shop: int, listing_id: int, data: ReviseInput) -> ListingOutput:
        self._shop(owner, shop)
        original = self._item(owner, shop, listing_id)
        product = self._current_product(owner, shop, original)
        active = self._active(owner, shop, original.product_key, data.expected_active_id)
        request_key = digest(
            [
                "revise",
                listing_id,
                data.expected_version,
                data.expected_active_id,
                data.content.model_dump(),
            ]
        )
        existing = self.repo.by_key(owner, request_key)
        if existing:
            return output(existing)
        if original.version != data.expected_version:
            raise ConflictError("草稿状态已变化，请刷新后修改")
        item = self._save(
            owner,
            shop,
            product,
            data.content,
            active,
            request_key,
            "manual",
            self.repo.batches(owner, shop, original.id),
        )
        if original.status == "draft":
            original.status = "superseded"
            original.version += 1
        self.uow.record_event(
            owner, "listing.revised", "listing", item.id, {"from_id": original.id}
        )
        return self._finish(item)

    def decide(self, owner: int, shop: int, listing_id: int, data: DecisionInput) -> ListingOutput:
        self._shop(owner, shop)
        item = self._item(owner, shop, listing_id)
        target = "approved" if data.decision == "approve" else "rejected"
        if (
            item.status == target
            and item.version == data.expected_version + 1
            and item.source_status == "current"
        ):
            return output(item)
        if item.status != "draft" or item.version != data.expected_version:
            raise ConflictError("此版本已处理或状态已变化，请刷新后核对")
        if data.decision == "approve":
            product = self._current_product(owner, shop, item)
            snapshot = ListingSnapshot.model_validate(item.snapshot)
            blockers = check_content(product.name, product.facts, snapshot.proposed)
            if blockers or not data.facts_confirmed:
                self.uow.record_event(
                    owner,
                    "listing.approval_blocked",
                    "listing",
                    item.id,
                    {"rule": "source_text_coverage" if blockers else "human_fact_confirmation"},
                )
                self.uow.commit()
                raise BusinessError(
                    "fact_check_required", "请处理来源未覆盖的文字，并确认已逐项核对商品事实", 422
                )
            active = self._active(owner, shop, item.product_key, item.base_version_id)
            if active:
                active.status = "superseded"
                active.version += 1
        elif item.source_status == "cleared":
            raise ConflictError("来源已清除，保留记录不可再审批")
        item.status = target
        item.version += 1
        item.decided_at = utc_now()
        self.uow.record_event(
            owner,
            f"listing.{target}",
            "listing",
            item.id,
            {"number": item.number, "risk": "R1", "external_status": "not_submitted"},
        )
        return self._finish(item)
