import hashlib
import json

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.models.identity import Shop
from app.models.import_groups import ImportGroup
from app.models.imports import ImportBatch
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.import_groups import GroupInput, GroupOutput, ImportManifest
from app.schemas.imports import BatchSummary, UploadOptions


def require_import_coverage(
    uow: UnitOfWork,
    owner: int,
    shop: int,
    identity: str,
    kinds: set[str],
    channel: str | None = None,
) -> None:
    if uow.import_groups.incomplete(owner, shop, identity, kinds, channel):
        raise BusinessError(
            "partial_coverage",
            "部分覆盖／数据不足：所选来源存在未完成的导入组。请到文件导入继续各分片，"
            "或撤销整组后再计算；当前暂停汇总、排行与完整性判断。",
            409,
        )


class ImportGroupService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.import_groups

    def _shop(self, owner: int, shop_id: int) -> Shop:
        self.uow.identity.lock_user(owner)
        shop = self.uow.identity.get_shop(owner, shop_id, lock=True)
        if shop is None:
            raise NotFoundError()
        return shop

    def _group(self, owner: int, group_id: int) -> ImportGroup:
        group = self.repo.get(owner, group_id)
        if group is None:
            raise NotFoundError()
        return group

    def create(self, owner: int, shop_id: int, data: GroupInput) -> GroupOutput:
        shop = self._shop(owner, shop_id)
        key = hashlib.sha256(
            json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        existing = self.repo.by_key(owner, shop_id, key)
        if existing is not None:
            return self._output(owner, existing)
        group = ImportGroup(
            owner_id=owner,
            shop_id=shop_id,
            kind=data.options.kind,
            source_channel=data.options.source_channel,
            data_identity=data.options.data_identity,
            request_key=key,
            options=data.options.model_dump(mode="json"),
            manifest=data.manifest.model_dump(mode="json"),
        )
        self.repo.add(group)
        # Coverage itself is a source change, including a group with zero uploaded parts.
        from app.services.imports import ImportService

        shop.data_revision += 1
        ImportService(self.uow).invalidate(owner, shop_id, group.kind)
        self.uow.record_event(
            owner,
            "import_group.created",
            "import_group",
            group.id,
            {"rows": data.manifest.total_rows, "parts": len(data.manifest.parts)},
        )
        self.uow.commit()
        return self._output(owner, group)

    def get(self, owner: int, group_id: int) -> GroupOutput:
        self.uow.identity.lock_user(owner)
        return self._output(owner, self._group(owner, group_id))

    def list(self, owner: int, shop_id: int, before: int | None = None) -> list[GroupOutput]:
        self._shop(owner, shop_id)
        return [self._output(owner, group) for group in self.repo.groups(owner, shop_id, before)]

    def _output(self, owner: int, group: ImportGroup) -> GroupOutput:
        latest = {batch.group_part: batch for batch in self.repo.batches(owner, group.id)}
        committed = [batch for batch in latest.values() if batch.status == "committed"]
        _, unique = self.repo.counts(owner, group.id)
        total = sum(batch.total_rows for batch in committed)
        return GroupOutput(
            id=group.id,
            shop_id=group.shop_id,
            version=group.version,
            status=group.status,
            complete=group.complete,
            options=UploadOptions.model_validate(group.options),
            manifest=ImportManifest.model_validate(group.manifest),
            batches=[BatchSummary.model_validate(batch) for batch in latest.values()],
            committed_parts=len(committed),
            committed_rows=total,
            unique_rows=unique,
            overlap_rows=total - unique,
        )

    def attach(
        self, owner: int, shop_id: int, options: UploadOptions, data: bytes, rows: int
    ) -> ImportBatch | None:
        if options.group_id is None:
            if options.group_part is not None:
                raise ConflictError("分片必须指定导入组")
            return None
        group = self._group(owner, options.group_id)
        if group.shop_id != shop_id:
            raise NotFoundError()
        manifest = ImportManifest.model_validate(group.manifest)
        if (
            group.status != "active"
            or not options.group_part
            or options.group_part > len(manifest.parts)
        ):
            raise ConflictError("导入组已撤销或分片序号无效")
        part = manifest.parts[options.group_part - 1]
        expected = UploadOptions.model_validate(group.options)
        fields = {"kind", "source_channel", "data_identity", "timezone", "exported_at"}
        if options.model_dump(include=fields) != expected.model_dump(include=fields):
            raise ConflictError("分片须沿用导入组的类型、渠道、数据身份、时区和导出时间")
        if (options.filename, len(data), rows, hashlib.sha256(data).hexdigest()) != (
            part.filename,
            part.bytes,
            part.rows,
            part.sha256,
        ):
            raise ConflictError(
                "分片与清单的文件名、大小、行数或指纹不一致；请使用原分片或重新拆分建组"
            )
        for batch in reversed(self.repo.batches(owner, group.id)):
            if batch.group_part == options.group_part and batch.status in {
                "draft",
                "preview",
                "committed",
            }:
                return batch
        return None

    def changed(self, owner: int, batch: ImportBatch) -> None:
        if batch.group_id is None:
            return
        group = self._group(owner, batch.group_id)
        self.uow.imports.flush()
        output = self._output(owner, group)
        group.complete = (
            group.status == "active"
            and output.committed_parts == len(output.manifest.parts)
            and output.committed_rows == output.manifest.total_rows
        )
        group.version += 1

    def validate_mapping(self, owner: int, batch: ImportBatch, mapping: dict[str, str]) -> None:
        if batch.group_id is not None:
            for other in self.repo.batches(owner, batch.group_id):
                if (
                    other.id != batch.id
                    and other.status == "committed"
                    and other.mapping != mapping
                ):
                    raise ConflictError(
                        "同组分片须沿用已提交分片的字段映射；口径变化请撤销整组并重新核对"
                    )

    def withdraw(self, owner: int, group_id: int, version: int) -> GroupOutput:
        from app.services.imports import ImportService

        self.uow.identity.lock_user(owner)
        group = self._group(owner, group_id)
        shop = self._shop(owner, group.shop_id)
        if group.status == "revoked":
            return self._output(owner, group)
        if group.version != version:
            raise ConflictError("导入组已变化，请刷新后再次确认")
        with self.uow.defer_commits():
            for batch in reversed(self.repo.batches(owner, group.id)):
                ImportService(self.uow).withdraw(owner, batch.id, batch.version)
            group.status = "revoked"
            group.complete = False
            group.version += 1
            shop.data_revision += 1
            ImportService(self.uow).invalidate(owner, shop.id, group.kind)
            self.uow.record_event(owner, "import_group.revoked", "import_group", group.id)
        self.uow.commit()
        return self._output(owner, group)
