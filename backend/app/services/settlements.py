from datetime import timedelta
from hashlib import sha256

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.settlements import Settlement, SettlementReceipt, SettlementRevision
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.expenses import ExpenseControl
from app.schemas.settlements import (
    SettlementCurrent,
    SettlementDraft,
    SettlementHistory,
    SettlementPage,
    SettlementPreview,
    SettlementSaved,
    SettlementSnapshot,
    SettlementWrite,
)
from app.schemas.statements import StatementItem
from app.services.evidence import evidence_key
from app.services.expenses import naive_utc
from app.services.import_groups import require_import_coverage
from app.services.product_quality import digest
from app.services.profit_calculation import reference, utc_text
from app.services.settlement_calculation import compare_payouts, settlement_totals


class SettlementService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.settlements

    def _shop(self, owner: int, shop: int) -> None:
        self.uow.identity.lock_user(owner)
        if self.uow.identity.get_shop(owner, shop, lock=True) is None:
            raise NotFoundError()

    def _settlement(self, owner: int, shop: int, settlement: int) -> Settlement:
        item = self.repo.get(owner, shop, settlement)
        if item is None:
            raise NotFoundError()
        return item

    def _output(
        self, settlement: Settlement, full: bool = True, version: int | None = None
    ) -> SettlementSaved:
        revision = (
            self.repo.revision(settlement, version or settlement.content_version) if full else None
        )
        if version is not None and revision is None:
            raise NotFoundError()
        return SettlementSaved(
            id=settlement.id,
            shop_id=settlement.shop_id,
            data_identity=settlement.data_identity,
            channel=settlement.channel,
            status=settlement.status,
            version=settlement.version,
            content_version=settlement.content_version,
            created_at=utc_text(settlement.created_at),
            snapshot=SettlementSnapshot.model_validate(revision.snapshot)
            if revision and revision.snapshot
            else None,
            history=[
                SettlementHistory(
                    version=v,
                    action=a,
                    created_at=utc_text(t),
                    has_content=c,
                )
                for v, a, t, c in self.repo.history(settlement)
            ]
            if full
            else [],
        )

    def _preview(self, owner: int, shop: int, data: SettlementDraft) -> SettlementPreview:
        self._shop(owner, shop)
        if data.settlement_id:
            settlement = self._settlement(owner, shop, data.settlement_id)
            if (
                settlement.status not in {"active", "stale"}
                or settlement.version != data.version
                or settlement.data_identity != data.scope.data_identity
                or settlement.channel != data.scope.channel
            ):
                raise ConflictError("结算登记版本或范围已变化，请重新读取。")
            if len(self.repo.history(settlement)) >= 100:
                raise BusinessError(
                    "revision_limit", "每份结算登记最多 100 次保存，仍可撤销或清除。", 422
                )
        elif data.version:
            raise ConflictError("新存档版本必须为零。")
        receipt_keys = {evidence_key(r.receipt_ref) for r in data.content.receipts}
        if len(receipt_keys) != len(data.content.receipts):
            raise BusinessError("duplicate_receipt", "同一到账凭据不能重复登记。", 422)
        if self.repo.conflicts(
            owner,
            shop,
            data.scope.data_identity,
            data.scope.channel,
            data.settlement_id,
            self._statement_key(data.content.statement_id),
            receipt_keys,
        ):
            raise ConflictError("原账单号或到账凭据已由其他有效/待重核登记占用，请先处理原登记。")
        snapshot = self._calculate(owner, shop, data)
        if len(snapshot.model_dump_json().encode("utf-8")) > 2 * 1024 * 1024:
            raise BusinessError("snapshot_too_large", "存档依据超过 2 MiB，请缩短核对范围。", 422)
        payload = snapshot.model_dump(mode="json")
        del payload["calculated_at"]
        return SettlementPreview(
            snapshot=snapshot,
            preview_hash=digest(
                {
                    "contract": "settlement-v1",
                    "shop": shop,
                    "draft": data.model_dump(mode="json"),
                    "registry_revision": self.repo.scope_revision(
                        owner, shop, data.scope.data_identity, data.scope.channel
                    ),
                    "snapshot": payload,
                }
            ),
        )

    @staticmethod
    def _statement_key(value: str) -> str:
        # Match the exact platform identifier used by StatementLine's binary collation.
        return sha256(value.encode("utf-8")).hexdigest()

    def _calculate(self, owner: int, shop: int, data: SettlementDraft) -> SettlementSnapshot:
        scope = data.scope
        require_import_coverage(
            self.uow, owner, shop, scope.data_identity, {"statements"}, scope.channel
        )
        if any(
            naive_utc(r.received_at) > utc_now() + timedelta(minutes=5)
            for r in data.content.receipts
        ):
            raise BusinessError("future_receipt", "到账登记不能使用未来时间。", 422)
        store = self.uow.identity.get_shop(owner, shop, lock=True)
        assert store is not None
        rows = self.uow.statements.by_statement(
            owner, shop, scope.data_identity, scope.channel, data.content.statement_id
        )
        if len(rows) > 1000:
            raise BusinessError(
                "range_too_large", "单个原账单号超过 1000 行，无法保存部分结算依据。", 422
            )
        statements = [
            StatementItem(
                **(
                    row.normalized
                    | {"amount": line.amount, "occurred_at": utc_text(line.occurred_at)}
                ),
                id=line.id,
                source=reference(row, batch),
            )
            for line, row, batch in rows
        ]
        return SettlementSnapshot(
            scope=scope,
            content=data.content,
            source_revision=store.data_revision,
            calculated_at=utc_text(utc_now()),
            statements=statements,
            totals=settlement_totals(statements, data.content.receipts),
            comparisons=compare_payouts(statements, data.content.receipts),
            outside_cycle_ids=[
                line.id
                for line, _, _ in rows
                if line.entry_type != "payout"
                and not naive_utc(scope.start_at) <= line.occurred_at < naive_utc(scope.end_at)
            ],
            checks=[
                "周期由卖家按原始结算文件登记，包含开始、不含结束；原账单号精确关联全部当前行，不按发生日期猜测归属。",
                "平台回款及人工到账可发生于周期之外；非回款行落在周期外会单独列出，请核实归属。",
                "回款凭据编号经 NFKC、大小写和空白规范化后一对一比较；"
                "差额为平台记载减人工登记，重复不抵销，跨币种不换汇。",
                "未登记到账凭据只表示本地缺少登记，不能推断尚未到账；人工到账金额是卖家声明，银行证据未核验。",
                "文件覆盖、期初期末余额及结算完整性未知，金额一致不表示结算完成或银行已确证，不计算可提现余额或净利润。",
            ],
        )

    def preview(self, owner: int, shop: int, data: SettlementDraft) -> SettlementPreview:
        output = self._preview(owner, shop, data)
        self.uow.commit()
        return output

    def _replay(
        self, owner: int, shop: int, request: str, request_hash: str
    ) -> SettlementSaved | None:
        previous = self.repo.by_request(owner, request)
        if previous is None:
            return None
        if previous.request_hash != request_hash:
            raise ConflictError("请求标识已用于另一项结算登记操作。")
        return self._output(self._settlement(owner, shop, previous.settlement_id))

    def write(self, owner: int, shop: int, data: SettlementWrite) -> SettlementSaved:
        self._shop(owner, shop)
        request_hash = digest(
            {
                "shop": shop,
                "action": "write",
                **data.model_dump(mode="json", exclude={"request_id"}),
            }
        )
        replay = self._replay(owner, shop, str(data.request_id), request_hash)
        if replay:
            self.uow.commit()
            return replay
        draft = SettlementDraft.model_validate(
            data.model_dump(exclude={"request_id", "confirm", "preview_hash"})
        )
        current = self._preview(owner, shop, draft)
        if current.preview_hash != data.preview_hash:
            raise ConflictError("账单、周期或人工凭据已变化，请重新预览并确认。")
        if data.settlement_id:
            settlement = self._settlement(owner, shop, data.settlement_id)
            settlement.version += 1
            settlement.content_version = settlement.version
            settlement.status = "active"
        else:
            settlement = Settlement(
                owner_id=owner,
                shop_id=shop,
                data_identity=data.scope.data_identity,
                channel=data.scope.channel,
                status="active",
                version=1,
                content_version=1,
            )
            self.repo.add(settlement)
        self.repo.release(settlement)
        settlement.statement_key = self._statement_key(data.content.statement_id)
        action = "update" if data.settlement_id else "create"
        revision = SettlementRevision(
            settlement_id=settlement.id,
            owner_id=owner,
            version=settlement.version,
            request_id=str(data.request_id),
            request_hash=request_hash,
            action=action,
            snapshot=current.snapshot.model_dump(mode="json"),
        )
        self.repo.revise(revision)
        for position, receipt in enumerate(data.content.receipts):
            self.repo.receipt(
                SettlementReceipt(
                    settlement_id=settlement.id,
                    revision_id=revision.id,
                    owner_id=owner,
                    shop_id=shop,
                    data_identity=data.scope.data_identity,
                    channel=data.scope.channel,
                    receipt_key=evidence_key(receipt.receipt_ref),
                    position=position,
                    amount=receipt.amount,
                    received_at=naive_utc(receipt.received_at),
                )
            )
        self.repo.dependencies(settlement, {s.source.batch_id for s in current.snapshot.statements})
        self.uow.record_event(
            owner,
            f"settlement.{action}",
            "settlement",
            settlement.id,
            {"version": settlement.version},
        )
        output = self._output(settlement)
        self.uow.commit()
        return output

    def get(
        self, owner: int, shop: int, settlement: int, version: int | None = None
    ) -> SettlementSaved:
        self._shop(owner, shop)
        output = self._output(self._settlement(owner, shop, settlement), version=version)
        self.uow.commit()
        return output

    def page(
        self, owner: int, shop: int, identity: str, channel: str, before: int | None
    ) -> SettlementPage:
        self._shop(owner, shop)
        rows = self.repo.page(owner, shop, identity, channel, before)
        output = SettlementPage(
            items=[self._output(r, False) for r in rows[:20]],
            next_cursor=rows[19].id if len(rows) > 20 else None,
        )
        self.uow.commit()
        return output

    def current(self, owner: int, shop: int, settlement_id: int) -> SettlementCurrent:
        self._shop(owner, shop)
        settlement = self._settlement(owner, shop, settlement_id)
        saved = self._output(settlement)
        if saved.snapshot is None:
            self.uow.commit()
            return SettlementCurrent(record=saved, preview=None)
        # Status and current source evidence share a transaction; reads never activate a record.
        snapshot = self._calculate(
            owner, shop, SettlementDraft(scope=saved.snapshot.scope, content=saved.snapshot.content)
        )
        output = SettlementPreview(preview_hash="", snapshot=snapshot)
        self.uow.commit()
        return SettlementCurrent(record=saved, preview=output)

    def control(
        self, owner: int, shop: int, settlement_id: int, action: str, data: ExpenseControl
    ) -> SettlementSaved:
        self._shop(owner, shop)
        request_hash = digest(
            {
                "shop": shop,
                "settlement": settlement_id,
                "action": action,
                **data.model_dump(mode="json", exclude={"request_id"}),
            }
        )
        replay = self._replay(owner, shop, str(data.request_id), request_hash)
        if replay:
            self.uow.commit()
            return replay
        settlement = self._settlement(owner, shop, settlement_id)
        if settlement.version != data.version:
            raise ConflictError("结算登记版本已变化，请刷新。")
        if settlement.status == "cleared" or (
            action == "withdraw" and settlement.status == "withdrawn"
        ):
            output = self._output(settlement)
            self.uow.commit()
            return output
        if action == "clear":
            self.repo.clear(settlement)
        else:
            self.repo.release(settlement)
            settlement.status = "withdrawn"
            settlement.version += 1
        self.repo.revise(
            SettlementRevision(
                settlement_id=settlement.id,
                owner_id=owner,
                version=settlement.version,
                request_id=str(data.request_id),
                request_hash=request_hash,
                action=action,
                snapshot=None,
            )
        )
        self.uow.record_event(
            owner,
            f"settlement.{action}",
            "settlement",
            settlement.id,
            {"version": settlement.version},
        )
        output = self._output(settlement)
        self.uow.commit()
        return output
