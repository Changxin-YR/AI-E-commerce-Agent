from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.operations import OperationRunSource
from app.models.outbound import OutboundApproval, OutboundMessage, TestMailChannel


class OutboundRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, item: TestMailChannel | OutboundMessage | OutboundApproval) -> None:
        self.session.add(item)
        self.session.flush()

    def channels(self, owner: int, shop: int) -> list[TestMailChannel]:
        return list(
            self.session.scalars(
                select(TestMailChannel)
                .where(
                    TestMailChannel.owner_id == owner,
                    TestMailChannel.shop_id == shop,
                )
                .order_by(TestMailChannel.id.desc())
                .limit(50)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def channel(self, owner: int, shop: int, channel: int) -> TestMailChannel | None:
        return self.session.scalar(
            select(TestMailChannel)
            .where(
                TestMailChannel.owner_id == owner,
                TestMailChannel.shop_id == shop,
                TestMailChannel.id == channel,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def message(self, owner: int, shop: int, message: int) -> OutboundMessage | None:
        return self.session.scalar(
            select(OutboundMessage)
            .where(
                OutboundMessage.owner_id == owner,
                OutboundMessage.shop_id == shop,
                OutboundMessage.id == message,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def by_key(self, owner: int, key: str) -> OutboundMessage | None:
        return self.session.scalar(
            select(OutboundMessage)
            .where(
                OutboundMessage.owner_id == owner,
                OutboundMessage.dedupe_key == key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def messages(self, owner: int, shop: int, before: int | None) -> list[OutboundMessage]:
        query = select(OutboundMessage).where(
            OutboundMessage.owner_id == owner,
            OutboundMessage.shop_id == shop,
        )
        if before:
            query = query.where(OutboundMessage.id < before)
        return list(
            self.session.scalars(
                query.order_by(OutboundMessage.id.desc())
                .limit(51)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def approvals(self, owner: int, shop: int, message: int) -> list[OutboundApproval]:
        return list(
            self.session.scalars(
                select(OutboundApproval)
                .where(
                    OutboundApproval.owner_id == owner,
                    OutboundApproval.shop_id == shop,
                    OutboundApproval.message_id == message,
                )
                .order_by(OutboundApproval.id.desc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def recent_dispatches(self, owner: int, since: datetime) -> list[datetime]:
        # Include cleared and unknown attempts: they may have had an external effect.
        return list(
            self.session.scalars(
                select(OutboundMessage.dispatch_at)
                .where(
                    OutboundMessage.owner_id == owner,
                    OutboundMessage.dispatch_at >= since,
                )
                .with_for_update()
            )
        )

    def purge_batch(self, owner: int, shop: int, batch: int) -> None:
        runs = select(OperationRunSource.run_id).where(OperationRunSource.batch_id == batch)
        self.session.execute(
            update(OutboundMessage)
            .where(
                OutboundMessage.owner_id == owner,
                OutboundMessage.shop_id == shop,
                OutboundMessage.run_id.in_(runs),
            )
            .values(
                subject=None,
                body=None,
                receipt_evidence=None,
                source_status="cleared",
                version=OutboundMessage.version + 1,
            )
        )
