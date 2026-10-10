from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.imports import CustomerMessage, ImportBatch, ImportRow, OrderLine
from app.models.support import (
    ReplyDraft,
    ReplyManualAction,
    ReplyPolicy,
    ReplySource,
    SupportPolicy,
)
from app.repositories.analytics import OrderEvidence

MessageEvidence = tuple[CustomerMessage, ImportRow, ImportBatch]


class SupportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def messages(self, owner: int, shop: int, query: str, offset: int) -> list[MessageEvidence]:
        rows = self.session.execute(
            select(CustomerMessage, ImportRow, ImportBatch)
            .join(ImportRow, CustomerMessage.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                CustomerMessage.shop_id == shop,
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.status == "committed",
                CustomerMessage.body.contains(query, autoescape=True)
                | CustomerMessage.message_id.contains(query, autoescape=True),
            )
            .order_by(CustomerMessage.sent_at.desc(), CustomerMessage.id.desc())
            .offset(offset)
            .limit(50)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(m, r, b) for m, r, b in rows]

    def message(self, owner: int, shop: int, message_id: int) -> MessageEvidence | None:
        row = self.session.execute(
            select(CustomerMessage, ImportRow, ImportBatch)
            .join(ImportRow, CustomerMessage.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                CustomerMessage.id == message_id,
                CustomerMessage.shop_id == shop,
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.status == "committed",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        return (row[0], row[1], row[2]) if row else None

    def orders(
        self, owner: int, shop: int, order_id: str, identity: str, channel: str
    ) -> list[OrderEvidence]:
        rows = self.session.execute(
            select(OrderLine, ImportRow, ImportBatch)
            .join(ImportRow, OrderLine.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                OrderLine.shop_id == shop,
                OrderLine.order_id == order_id,
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.status == "committed",
                ImportBatch.data_identity == identity,
                ImportBatch.source_channel == channel,
            )
            .order_by(OrderLine.id)
            .limit(101)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(o, r, b) for o, r, b in rows]

    def policies(
        self, owner: int, shop: int, query: str = "", offset: int = 0
    ) -> list[SupportPolicy]:
        statement = select(SupportPolicy).where(
            SupportPolicy.owner_id == owner, SupportPolicy.shop_id == shop
        )
        if query:
            statement = statement.where(
                SupportPolicy.payload["title"].as_string().contains(query, autoescape=True)
                | SupportPolicy.payload["text"].as_string().contains(query, autoescape=True)
            )
        return list(
            self.session.scalars(
                statement.order_by(SupportPolicy.id.desc())
                .offset(offset)
                .limit(100)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def active_policies(self, owner: int, shop: int) -> list[SupportPolicy]:
        return list(
            self.session.scalars(
                select(SupportPolicy)
                .where(
                    SupportPolicy.owner_id == owner,
                    SupportPolicy.shop_id == shop,
                    SupportPolicy.status == "active",
                )
                .order_by(SupportPolicy.id)
                .limit(501)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def policy(self, owner: int, shop: int, policy_id: int) -> SupportPolicy | None:
        return self.session.scalar(
            select(SupportPolicy)
            .where(
                SupportPolicy.owner_id == owner,
                SupportPolicy.shop_id == shop,
                SupportPolicy.id == policy_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def latest_policy(self, owner: int, shop: int, key: str) -> SupportPolicy | None:
        return self.session.scalar(
            select(SupportPolicy)
            .where(
                SupportPolicy.owner_id == owner,
                SupportPolicy.shop_id == shop,
                SupportPolicy.policy_key == key,
            )
            .order_by(SupportPolicy.number.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def policy_request(self, owner: int, shop: int, key: str) -> SupportPolicy | None:
        return self.session.scalar(
            select(SupportPolicy)
            .where(
                SupportPolicy.owner_id == owner,
                SupportPolicy.shop_id == shop,
                SupportPolicy.request_key == key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def policy_epoch(self, owner: int, shop: int, key: str) -> int:
        return (
            self.session.scalar(
                select(func.max(SupportPolicy.id))
                .where(
                    SupportPolicy.owner_id == owner,
                    SupportPolicy.shop_id == shop,
                    SupportPolicy.policy_key == key,
                    SupportPolicy.status == "cleared",
                )
                .with_for_update()
            )
            or 0
        )

    def add_policy(self, item: SupportPolicy) -> None:
        self.session.add(item)
        self.session.flush()

    def drafts(self, owner: int, shop: int, key: str | None = None) -> list[ReplyDraft]:
        statement = select(ReplyDraft).where(
            ReplyDraft.owner_id == owner, ReplyDraft.shop_id == shop
        )
        if key:
            statement = statement.where(ReplyDraft.message_key == key)
        return list(
            self.session.scalars(
                statement.order_by(ReplyDraft.id.desc())
                .limit(50)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def draft(self, owner: int, shop: int, draft_id: int) -> ReplyDraft | None:
        return self.session.scalar(
            select(ReplyDraft)
            .where(
                ReplyDraft.owner_id == owner,
                ReplyDraft.shop_id == shop,
                ReplyDraft.id == draft_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def draft_request(self, owner: int, shop: int, key: str) -> ReplyDraft | None:
        return self.session.scalar(
            select(ReplyDraft)
            .where(
                ReplyDraft.owner_id == owner,
                ReplyDraft.shop_id == shop,
                ReplyDraft.request_key == key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def epoch(self, owner: int, shop: int, key: str) -> int:
        return (
            self.session.scalar(
                select(func.max(ReplyDraft.id))
                .where(
                    ReplyDraft.owner_id == owner,
                    ReplyDraft.shop_id == shop,
                    ReplyDraft.message_key == key,
                    ReplyDraft.source_status != "current",
                )
                .with_for_update()
            )
            or 0
        )

    def add_draft(self, item: ReplyDraft, batches: set[int], policies: set[int]) -> None:
        self.session.add(item)
        self.session.flush()
        self.session.add_all([ReplySource(draft_id=item.id, batch_id=b) for b in batches])
        self.session.add_all([ReplyPolicy(draft_id=item.id, policy_id=p) for p in policies])

    def invalidate(self, owner: int, shop: int, kind: str) -> None:
        self.session.flush()
        current_message = exists(
            select(CustomerMessage.id).where(
                CustomerMessage.shop_id == shop,
                CustomerMessage.source_row_id == ReplyDraft.source_row_id,
            )
        )
        condition = ~current_message
        if kind == "orders":
            # A new line may change a verified order even when its earlier rows remain current.
            condition |= ReplyDraft.snapshot["order_verified"].as_boolean() == True  # noqa: E712
        if kind == "policy":
            condition = ReplyDraft.id > 0
        self.session.execute(
            update(ReplyDraft)
            .where(
                ReplyDraft.owner_id == owner,
                ReplyDraft.shop_id == shop,
                ReplyDraft.source_status == "current",
                condition,
            )
            .values(source_status="stale", version=ReplyDraft.version + 1, updated_at=utc_now())
        )

    def expire_policies(self, owner: int, shop: int) -> None:
        expired = (
            select(ReplyPolicy.draft_id)
            .join(SupportPolicy)
            .where(
                SupportPolicy.owner_id == owner,
                SupportPolicy.shop_id == shop,
                (SupportPolicy.valid_until <= utc_now()) | (SupportPolicy.valid_from > utc_now()),
            )
        )
        self.session.execute(
            update(ReplyDraft)
            .where(
                ReplyDraft.owner_id == owner,
                ReplyDraft.shop_id == shop,
                ReplyDraft.source_status == "current",
                ReplyDraft.id.in_(expired),
            )
            .values(source_status="stale", version=ReplyDraft.version + 1, updated_at=utc_now())
        )

    def _purge(self, owner: int, shop: int, ids: list[int]) -> None:
        if not ids:
            return
        self.session.execute(
            update(ReplyDraft)
            .where(
                ReplyDraft.owner_id == owner,
                ReplyDraft.shop_id == shop,
                ReplyDraft.id.in_(ids),
            )
            .values(
                snapshot=None,
                reviewed_version=None,
                reviewed_at=None,
                reviewed_language=None,
                source_row_id=None,
                source_status="cleared",
                version=ReplyDraft.version + 1,
                updated_at=utc_now(),
            )
        )
        self.session.execute(
            update(ReplyManualAction)
            .where(
                ReplyManualAction.owner_id == owner,
                ReplyManualAction.shop_id == shop,
                ReplyManualAction.draft_id.in_(ids),
            )
            .values(payload=None)
        )
        self.session.execute(delete(ReplySource).where(ReplySource.draft_id.in_(ids)))
        self.session.execute(delete(ReplyPolicy).where(ReplyPolicy.draft_id.in_(ids)))

    def purge_batch(self, owner: int, shop: int, batch_id: int) -> None:
        ids = list(
            self.session.scalars(
                select(ReplyDraft.id)
                .join(ReplySource)
                .where(
                    ReplyDraft.owner_id == owner,
                    ReplyDraft.shop_id == shop,
                    ReplySource.batch_id == batch_id,
                )
                .with_for_update()
            )
        )
        self._purge(owner, shop, ids)

    def purge_policy(self, owner: int, shop: int, policy_id: int) -> None:
        ids = list(
            self.session.scalars(
                select(ReplyDraft.id)
                .join(ReplyPolicy)
                .where(
                    ReplyDraft.owner_id == owner,
                    ReplyDraft.shop_id == shop,
                    ReplyPolicy.policy_id == policy_id,
                )
                .with_for_update()
            )
        )
        self._purge(owner, shop, ids)

    def manual_actions(
        self, owner: int, shop: int, draft: int, before: int | None
    ) -> list[ReplyManualAction]:
        query = select(ReplyManualAction).where(
            ReplyManualAction.owner_id == owner,
            ReplyManualAction.shop_id == shop,
            ReplyManualAction.draft_id == draft,
        )
        if before is not None:
            query = query.where(ReplyManualAction.id < before)
        return list(self.session.scalars(query.order_by(ReplyManualAction.id.desc()).limit(50)))

    def manual_request(
        self, owner: int, shop: int, draft: int, key: str
    ) -> ReplyManualAction | None:
        return self.session.scalar(
            select(ReplyManualAction)
            .where(
                ReplyManualAction.owner_id == owner,
                ReplyManualAction.shop_id == shop,
                ReplyManualAction.draft_id == draft,
                ReplyManualAction.request_key == key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def add_manual_action(self, item: ReplyManualAction) -> None:
        self.session.add(item)
        self.session.flush()
