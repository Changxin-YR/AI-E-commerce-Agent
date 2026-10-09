from datetime import timedelta

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.identity import Shop
from app.models.imports import ImportBatch, ImportRow
from app.models.product_edits import ProductEdit
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.imports import CommitInput, ProductData
from app.schemas.product_edits import (
    EditControl,
    EditCreate,
    EditDecision,
    EditItem,
    EditPage,
    EditSaved,
    EditSnapshot,
)
from app.services.imports import ImportService
from app.services.product_quality import digest
from app.services.profit_calculation import reference, utc_text


def preview_hash(edit: ProductEdit) -> str:
    snapshot = EditSnapshot.model_validate(edit.snapshot) if edit.snapshot else None
    return digest(
        {
            "id": edit.id,
            "snapshot": snapshot.model_dump(
                mode="json", exclude={"items": {"__all__": {"result", "message"}}}
            )
            if snapshot
            else None,
        }
    )


class ProductEditService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.product_edits

    def _shop(self, owner: int, shop: int) -> Shop:
        self.uow.identity.lock_user(owner)
        found = self.uow.identity.get_shop(owner, shop, lock=True)
        if found is None:
            raise NotFoundError()
        return found

    def _edit(self, owner: int, shop: int, edit_id: int) -> ProductEdit:
        edit = self.repo.get(owner, shop, edit_id)
        if edit is None:
            raise NotFoundError()
        return edit

    def _output(self, edit: ProductEdit, full: bool = True) -> EditSaved:
        return EditSaved(
            id=edit.id,
            shop_id=edit.shop_id,
            version=edit.version,
            status=edit.status,
            preview_hash=preview_hash(edit),
            snapshot=EditSnapshot.model_validate(edit.snapshot) if full and edit.snapshot else None,
            output_batch_id=edit.output_batch_id,
            created_at=utc_text(edit.created_at),
            decided_at=utc_text(edit.decided_at) if edit.decided_at else None,
            current_count=self.repo.current_count(edit.owner_id, edit.shop_id, edit.output_batch_id)
            if edit.output_batch_id
            else 0,
        )

    def create(self, owner: int, shop: int, data: EditCreate) -> EditSaved:
        store = self._shop(owner, shop)
        request_hash = digest(
            {"shop": shop, **data.model_dump(mode="json", exclude={"request_id"})}
        )
        existing = self.repo.by_request(owner, str(data.request_id))
        if existing:
            if existing.shop_id != shop or existing.request_hash != request_hash:
                raise ConflictError("请求标识已用于另一份商品修订。")
            output = self._output(existing)
            self.uow.commit()
            return output
        items: list[EditItem] = []
        batches: set[int] = set()
        for change in data.changes:
            evidence = self.uow.listings.product(owner, shop, change.product_id)
            if evidence is None:
                raise ConflictError("所选商品不可用，请重新加载商品。")
            product, row, batch = evidence
            if (
                row.id != change.expected_source_row_id
                or batch.data_identity != data.data_identity
                or batch.source_channel != data.channel
            ):
                raise ConflictError("商品来源或范围已变化，请重新加载并核对修订。")
            before = ProductData.model_validate(row.normalized)
            after = before.model_copy(update={"name": change.name, "facts": change.facts})
            if before == after:
                raise BusinessError("unchanged_product", "仅选择名称或参数有变化的商品。", 422)
            items.append(
                EditItem(
                    product_id=product.id, before=before, after=after, source=reference(row, batch)
                )
            )
            batches.add(batch.id)
        ancestors = self.repo.ancestors(owner, shop, batches)
        if len(ancestors) > 1000:
            raise BusinessError(
                "lineage_too_large", "依赖链超过 1000 个批次，请整理来源后再修订。", 422
            )
        snapshot = EditSnapshot(
            source_revision=store.data_revision,
            data_identity=data.data_identity,
            channel=data.channel,
            reason=data.reason,
            items=items,
        )
        if len(snapshot.model_dump_json().encode()) > 1_000_000:
            raise BusinessError("range_too_large", "修订正文超过 1 MB，请缩小批量。", 422)
        edit = ProductEdit(
            owner_id=owner,
            shop_id=shop,
            request_id=str(data.request_id),
            request_hash=request_hash,
            snapshot=snapshot.model_dump(mode="json"),
        )
        self.repo.add(edit, ancestors)
        self.uow.record_event(
            owner, "product_edit.drafted", "product_edit", edit.id, {"rows": len(items)}
        )
        output = self._output(edit)
        self.uow.commit()
        return output

    def get(self, owner: int, shop: int, edit_id: int) -> EditSaved:
        self._shop(owner, shop)
        output = self._output(self._edit(owner, shop, edit_id))
        self.uow.commit()
        return output

    def page(self, owner: int, shop: int, before: int | None) -> EditPage:
        self._shop(owner, shop)
        rows = self.repo.page(owner, shop, before)
        output = EditPage(
            items=[self._output(e, False) for e in rows[:20]],
            next_cursor=rows[19].id if len(rows) > 20 else None,
        )
        self.uow.commit()
        return output

    def approve(self, owner: int, shop: int, edit_id: int, data: EditDecision) -> EditSaved:
        store = self._shop(owner, shop)
        edit = self._edit(owner, shop, edit_id)
        if preview_hash(edit) != data.expected_preview_hash:
            raise ConflictError("草稿差异已变化，请重新打开核对。")
        if edit.status == "applied" and data.version == edit.version - 1:
            output = self._output(edit)
            self.uow.commit()
            return output
        if edit.version != data.version or edit.status != "draft" or not edit.snapshot:
            raise ConflictError("草稿已处理或依据已失效，请重新加载商品建立草稿。")
        snapshot = EditSnapshot.model_validate(edit.snapshot)
        failed = store.data_revision != snapshot.source_revision
        for item in snapshot.items:
            evidence = self.uow.listings.product(owner, shop, item.product_id)
            if (
                evidence is None
                or evidence[1].id != item.source.row_id
                or evidence[2].data_identity != snapshot.data_identity
                or evidence[2].source_channel != snapshot.channel
                or ProductData.model_validate(evidence[1].normalized) != item.before
            ):
                item.result = "conflict"
                item.message = "商品或来源已变化，请重新加载后修订。"
                failed = True
        if failed:
            for item in snapshot.items:
                if item.result != "conflict":
                    item.result = "blocked"
                    item.message = "店铺数据版本已变化，本批未生效；请重新加载核对。"
            edit.status = "failed"
            edit.version += 1
            edit.decided_at = utc_now()
            edit.snapshot = snapshot.model_dump(mode="json")
            self.uow.record_event(owner, "product_edit.failed", "product_edit", edit.id)
        else:
            with self.uow.defer_commits():
                batch = self._batch(owner, store, edit, snapshot)
                self.uow.imports.flush()
                ImportService(self.uow).commit(
                    owner, batch.id, CommitInput(version=batch.version, allow_updates=True)
                )
                edit.output_batch_id = batch.id
                edit.status = "applied"
                edit.version += 1
                edit.decided_at = utc_now()
                for item in snapshot.items:
                    item.result = "applied"
                    item.message = "本地修订已生效"
                edit.snapshot = snapshot.model_dump(mode="json")
                self.uow.record_event(
                    owner,
                    "product_edit.applied",
                    "product_edit",
                    edit.id,
                    {"batch_id": batch.id, "rows": len(snapshot.items)},
                )
                self.uow.commit()
        output = self._output(edit)
        self.uow.commit()
        return output

    def _batch(
        self, owner: int, shop: Shop, edit: ProductEdit, snapshot: EditSnapshot
    ) -> ImportBatch:
        now = utc_now()
        batch = ImportBatch(
            owner_id=owner,
            shop_id=shop.id,
            kind="products",
            origin="manual_edit",
            source_channel=snapshot.channel,
            data_identity=snapshot.data_identity,
            filename=f"人工商品修订 #{edit.id}",
            sheet_name=f"人工修订 #{edit.id}",
            file_sha256="",
            timezone=shop.timezone,
            exported_at=None,
            expires_at=now + timedelta(days=1),
            status="preview",
            headers=[],
            raw_data=None,
            total_rows=len(snapshot.items),
            valid_rows=len(snapshot.items),
            updated_rows=len(snapshot.items),
            preview_revision=shop.data_revision,
        )
        self.uow.imports.add_batch(batch)
        rows = []
        for number, item in enumerate(snapshot.items, 1):
            evidence = self.uow.listings.product(owner, shop.id, item.product_id)
            assert evidence is not None
            rows.append(
                ImportRow(
                    batch_id=batch.id,
                    row_number=number,
                    business_key=evidence[1].business_key,
                    raw={
                        "依据批次": str(item.source.batch_id),
                        "依据行": str(item.source.row_id),
                        "修订理由": snapshot.reason,
                        "原名称": item.before.name,
                        "原参数": item.before.facts,
                    },
                    corrections={"name": item.after.name, "facts": item.after.facts},
                    normalized=item.after.model_dump(mode="json"),
                    previous=item.before.model_dump(mode="json"),
                    errors=[],
                    warnings=["人工修订；金额沿用原来源，未提交外部平台"],
                    action="update",
                )
            )
        self.uow.imports.replace_rows(owner, batch.id, rows)
        return batch

    def control(
        self, owner: int, shop: int, edit_id: int, action: str, data: EditControl
    ) -> EditSaved:
        self._shop(owner, shop)
        edit = self._edit(owner, shop, edit_id)
        terminal = {"reject": "rejected", "withdraw": "revoked", "clear": "cleared"}[action]
        if edit.status == terminal or edit.status == "cleared":
            output = self._output(edit)
            self.uow.commit()
            return output
        if edit.version != data.version:
            raise ConflictError("修订记录已变化，请刷新后操作。")
        with self.uow.defer_commits():
            if action == "reject":
                if edit.status != "draft":
                    raise ConflictError("仅待审草稿可以拒绝。")
                edit.status = "rejected"
                edit.version += 1
                edit.decided_at = utc_now()
            elif edit.output_batch_id:
                batch = self.uow.imports.get_batch(owner, edit.output_batch_id)
                assert batch is not None
                ImportService(self.uow).withdraw(
                    owner, batch.id, batch.version, purge=action == "clear"
                )
            elif action == "clear":
                self.repo.clear(edit)
            else:
                raise ConflictError("该记录尚未本地生效。")
            self.uow.record_event(owner, f"product_edit.{terminal}", "product_edit", edit.id)
            self.uow.commit()
        output = self._output(edit)
        self.uow.commit()
        return output
