import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import PurePath

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.identity import Shop
from app.models.imports import ImportBatch, ImportRow
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.imports import (
    BatchOutput,
    BatchSummary,
    CommitInput,
    MappingTemplateInput,
    MappingTemplateOutput,
    ParsedRow,
    PreviewInput,
    RowIssue,
    RowOutput,
    UploadOptions,
)
from app.services.import_catalog import FIELDS, guess_kind, suggest_mapping
from app.services.import_parser import parse_file
from app.services.import_validation import business_key, normalize_row


class ImportService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.imports

    def _shop(self, owner_id: int, shop_id: int) -> Shop:
        shop = self.uow.identity.get_shop(owner_id, shop_id, lock=True)
        if shop is None:
            raise NotFoundError()
        return shop

    def _batch(self, owner_id: int, batch_id: int) -> ImportBatch:
        batch = self.repo.get_batch(owner_id, batch_id)
        if batch is None:
            raise NotFoundError()
        return batch

    def _editable(self, batch: ImportBatch, version: int) -> None:
        if batch.version != version:
            raise ConflictError("批次已变化，请重新打开后操作")
        if batch.status not in {"draft", "preview"}:
            raise ConflictError("该批次已结束；纠错请重新上传文件")
        if batch.expires_at < utc_now():
            raise ConflictError("预览已过期，请重新上传文件")

    def _expire(self, owner_id: int) -> None:
        for batch in self.repo.expired_drafts(owner_id, utc_now()):
            self.repo.replace_rows(owner_id, batch.id, [])
            batch.raw_data = None
            batch.headers = []
            batch.mapping = {}
            batch.status = "expired"
            batch.version += 1

    def upload(
        self, owner_id: int, shop_id: int, options: UploadOptions, data: bytes
    ) -> BatchOutput:
        headers, rows, sheet_name = parse_file(options.filename, data)
        self.uow.identity.lock_user(owner_id)
        self._shop(owner_id, shop_id)
        self._expire(owner_id)
        batch = ImportBatch(
            owner_id=owner_id,
            shop_id=shop_id,
            kind=options.kind,
            source_channel=options.source_channel,
            data_identity=options.data_identity,
            filename=PurePath(options.filename.replace("\\", "/")).name,
            sheet_name=sheet_name,
            file_sha256=hashlib.sha256(data).hexdigest(),
            timezone=options.timezone,
            exported_at=options.exported_at.astimezone(UTC).replace(tzinfo=None)
            if options.exported_at
            else None,
            expires_at=utc_now() + timedelta(hours=24),
            headers=headers,
            raw_data=[row.model_dump() for row in rows],
            total_rows=len(rows),
            mapping={item.field: item.column for item in suggest_mapping(options.kind, headers)},
        )
        self.repo.add_batch(batch)
        self.uow.record_event(
            owner_id, "import.uploaded", "import_batch", batch.id, {"rows": len(rows)}
        )
        self.uow.commit()
        return self._output(owner_id, batch)

    def list_batches(self, owner_id: int, shop_id: int) -> list[BatchSummary]:
        self.uow.identity.lock_user(owner_id)
        self._shop(owner_id, shop_id)
        self._expire(owner_id)
        self.uow.commit()
        return [BatchSummary.model_validate(b) for b in self.repo.list_batches(owner_id, shop_id)]

    def get(self, owner_id: int, batch_id: int) -> BatchOutput:
        self.uow.identity.lock_user(owner_id)
        self._expire(owner_id)
        self.uow.commit()
        return self._output(owner_id, self._batch(owner_id, batch_id))

    def _output(self, owner_id: int, batch: ImportBatch) -> BatchOutput:
        examples = {}
        if batch.raw_data:
            first = ParsedRow.model_validate(batch.raw_data[0])
            examples = dict(zip(batch.headers, first.values, strict=True))
        return BatchOutput(
            **BatchSummary.model_validate(batch).model_dump(),
            headers=batch.headers,
            examples=examples,
            mapping=batch.mapping,
            suggestions=suggest_mapping(batch.kind, batch.headers),
            suggested_kind=guess_kind(batch.headers),
            errors=batch.errors,
            rows=[RowOutput.model_validate(row) for row in self.repo.rows(owner_id, batch.id)],
        )

    def preview(self, owner_id: int, batch_id: int, data: PreviewInput) -> BatchOutput:
        self.uow.identity.lock_user(owner_id)
        batch = self._batch(owner_id, batch_id)
        self._editable(batch, data.version)
        shop = self._shop(owner_id, batch.shop_id)
        allowed = {field.key for field in FIELDS[batch.kind]}
        mapping = {key: value for key, value in data.mapping.items() if value}
        if set(mapping) - allowed or set(mapping.values()) - set(batch.headers):
            raise BusinessError("invalid_mapping", "映射包含未知目标字段或源列", 422)
        if len(set(mapping.values())) != len(mapping):
            raise BusinessError("invalid_mapping", "每个源列只能映射一个目标字段", 422)
        source_rows = [ParsedRow.model_validate(row) for row in batch.raw_data or []]
        if set(data.corrections) - {row.row_number for row in source_rows}:
            raise BusinessError("invalid_correction", "修正行不属于当前文件", 422)
        for correction in data.corrections.values():
            if set(correction) - allowed or any(len(value) > 2000 for value in correction.values()):
                raise BusinessError("invalid_correction", "修正包含未知字段或过长内容", 422)
        batch.mapping = mapping
        batch.errors = [
            f"请映射必填字段：{field.label}"
            for field in FIELDS[batch.kind]
            if field.required and field.key not in mapping
        ]
        current = self.repo.current_entries(owner_id, shop.id, batch.kind)
        results: list[ImportRow] = []
        seen: dict[str, list[ImportRow]] = {}
        for raw in source_rows:
            result = normalize_row(
                batch.kind,
                raw,
                batch.headers,
                mapping,
                data.corrections.get(raw.row_number, {}),
                batch.timezone,
            )
            key = (
                business_key(batch.kind, result.normalized, batch.source_channel)
                if result.normalized
                else None
            )
            if key and key in current:
                result.previous = current[key][1].normalized
                if batch.kind == "inventory" and not result.errors:
                    incoming_time = datetime.fromisoformat(str(result.normalized["snapshot_at"]))
                    previous_time = datetime.fromisoformat(str(result.previous["snapshot_at"]))
                    if incoming_time < previous_time:
                        result.warnings.append(
                            "新文件快照时间早于现有快照；确认覆盖会使用更旧的库存依据"
                        )
                if not result.errors:
                    result.action = (
                        "unchanged" if result.normalized == result.previous else "update"
                    )
            record = ImportRow(
                batch_id=batch.id, business_key=key, **result.model_dump(mode="json")
            )
            if key:
                seen.setdefault(key, []).append(record)
            results.append(record)
        for records in seen.values():
            if len(records) > 1:
                for record in records:
                    record.errors.append(
                        RowIssue(
                            field="key",
                            message="文件内业务键重复，请修正源文件后重导；整批尚未写入业务数据",
                        ).model_dump()
                    )
                    record.action = "error"
        self.repo.replace_rows(owner_id, batch.id, results)
        batch.total_rows = len(results)
        batch.error_rows = sum(bool(row.errors) for row in results)
        batch.valid_rows = batch.total_rows - batch.error_rows
        batch.new_rows = sum(row.action == "new" for row in results)
        batch.updated_rows = sum(row.action == "update" for row in results)
        batch.unchanged_rows = sum(row.action == "unchanged" for row in results)
        batch.currencies = sorted(
            {
                str(row.normalized[key])
                for row in results
                for key in ("currency", "cost_currency")
                if row.normalized.get(key)
            }
        )
        time_key = {"messages": "sent_at", "inventory": "snapshot_at"}.get(batch.kind, "ordered_at")
        times = [str(row.normalized[time_key]) for row in results if row.normalized.get(time_key)]
        batch.coverage_start = min(times, key=datetime.fromisoformat) if times else None
        batch.coverage_end = max(times, key=datetime.fromisoformat) if times else None
        batch.preview_revision = shop.data_revision
        batch.status = "preview"
        batch.version += 1
        self.uow.commit()
        return self._output(owner_id, batch)

    def commit(self, owner_id: int, batch_id: int, data: CommitInput) -> BatchOutput:
        self.uow.identity.lock_user(owner_id)
        batch = self._batch(owner_id, batch_id)
        if batch.status == "committed":
            return self._output(owner_id, batch)
        self._editable(batch, data.version)
        shop = self._shop(owner_id, batch.shop_id)
        if batch.status != "preview" or batch.errors or batch.error_rows or not batch.valid_rows:
            raise ConflictError("请完成预览并修正全部错误行后再确认")
        if batch.preview_revision != shop.data_revision:
            raise ConflictError("预览后店铺数据已变化，请重新预览最新差异")
        if batch.updated_rows and not data.allow_updates:
            raise ConflictError("存在覆盖更新，请核对旧值和新值并明确确认")
        current = self.repo.current_entries(owner_id, shop.id, batch.kind)
        for row in self.repo.rows(owner_id, batch.id):
            existing = current.get(row.business_key or "")
            self.repo.apply_row(shop.id, batch.kind, row, existing[0] if existing else None)
        shop.data_revision += 1
        self.uow.analytics.invalidate(owner_id, shop.id)
        self.uow.listings.invalidate(owner_id, shop.id)
        self.uow.support.invalidate(owner_id, shop.id, batch.kind)
        batch.applied_revision = shop.data_revision
        batch.status = "committed"
        batch.committed_at = utc_now()
        batch.raw_data = (
            None  # Unmapped source cells (e.g. customer contact details) are discarded.
        )
        batch.version += 1
        self.uow.record_event(
            owner_id,
            "import.committed",
            "import_batch",
            batch.id,
            {"revision": shop.data_revision, "rows": batch.valid_rows},
        )
        self.uow.commit()
        return self._output(owner_id, batch)

    def withdraw(
        self, owner_id: int, batch_id: int, version: int, *, purge: bool = False
    ) -> BatchOutput:
        self.uow.identity.lock_user(owner_id)
        batch = self._batch(owner_id, batch_id)
        if batch.status == "cleared" or (batch.status == "revoked" and not purge):
            return self._output(owner_id, batch)
        if batch.version != version:
            raise ConflictError("批次已变化，请刷新后操作")
        shop = self._shop(owner_id, batch.shop_id)
        rows = self.repo.rows(owner_id, batch.id)
        keys = {row.business_key for row in rows if row.business_key}
        was_active = batch.status == "committed"
        batch.status = "cleared" if purge else "revoked"
        if was_active:
            self.repo.flush()
            current = self.repo.current_entries(owner_id, shop.id, batch.kind)
            winners = self.repo.active_versions(owner_id, shop.id, batch.kind, keys)
            for key in keys:
                existing = current.get(key)
                if key in winners:
                    self.repo.apply_row(
                        shop.id, batch.kind, winners[key], existing[0] if existing else None
                    )
                elif existing:
                    self.repo.delete_record(existing[0])
            shop.data_revision += 1
            self.uow.analytics.invalidate(owner_id, shop.id)
            self.repo.flush()
        batch.raw_data = None
        self.uow.listings.invalidate(owner_id, shop.id)
        self.uow.support.invalidate(owner_id, shop.id, batch.kind)
        if purge or not was_active and batch.committed_at is None:
            self.uow.analytics.purge_batch(owner_id, shop.id, batch.id)
            self.uow.listings.purge_batch(owner_id, shop.id, batch.id)
            self.uow.support.purge_batch(owner_id, shop.id, batch.id)
            self.repo.clear_previous(owner_id, shop.id, keys)
            self.repo.replace_rows(owner_id, batch.id, [])
            batch.filename = "已清除"
            batch.file_sha256 = ""
            batch.headers = []
            batch.mapping = {}
            batch.errors = []
        batch.version += 1
        self.uow.record_event(
            owner_id,
            "import.cleared" if purge else "import.revoked",
            "import_batch",
            batch.id,
            {"revision": shop.data_revision},
        )
        self.uow.commit()
        return self._output(owner_id, batch)

    def templates(self, owner_id: int) -> list[MappingTemplateOutput]:
        return [MappingTemplateOutput.model_validate(t) for t in self.repo.templates(owner_id)]

    def save_template(self, owner_id: int, data: MappingTemplateInput) -> MappingTemplateOutput:
        allowed = {field.key for field in FIELDS[data.kind]}
        if set(data.mapping) - allowed or any(not v or len(v) > 120 for v in data.mapping.values()):
            raise BusinessError("invalid_mapping", "模板字段无效", 422)
        self.uow.identity.lock_user(owner_id)
        template = self.repo.save_template(owner_id, data.model_dump())
        self.uow.commit()
        return MappingTemplateOutput.model_validate(template)
