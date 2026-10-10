from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedules import OperationSchedule, ScheduleOccurrence


class SchedulesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: OperationSchedule | ScheduleOccurrence) -> None:
        self.session.add(row)
        self.session.flush()

    def get(self, owner: int, shop: int, schedule: int) -> OperationSchedule | None:
        return self.session.scalar(
            select(OperationSchedule)
            .where(
                OperationSchedule.owner_id == owner,
                OperationSchedule.shop_id == shop,
                OperationSchedule.id == schedule,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def by_request(self, owner: int, request: str) -> OperationSchedule | None:
        return self.session.scalar(
            select(OperationSchedule)
            .where(
                OperationSchedule.owner_id == owner,
                OperationSchedule.request_id == request,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def schedules(self, owner: int, shop: int) -> list[OperationSchedule]:
        return list(
            self.session.scalars(
                select(OperationSchedule)
                .where(
                    OperationSchedule.owner_id == owner,
                    OperationSchedule.shop_id == shop,
                )
                .order_by(OperationSchedule.id.desc())
                .limit(100)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def due(self, now: datetime) -> list[tuple[int, int, int, int, datetime]]:
        rows = self.session.execute(
            select(
                OperationSchedule.owner_id,
                OperationSchedule.shop_id,
                OperationSchedule.id,
                OperationSchedule.version,
                OperationSchedule.next_run_at,
            )
            .where(OperationSchedule.status == "active", OperationSchedule.next_run_at <= now)
            .order_by(OperationSchedule.next_run_at, OperationSchedule.id)
            .limit(20)
        )
        return [
            (owner, shop, schedule, version, due) for owner, shop, schedule, version, due in rows
        ]

    def by_slot(self, schedule: int, key: str) -> ScheduleOccurrence | None:
        return self.session.scalar(
            select(ScheduleOccurrence)
            .where(
                ScheduleOccurrence.schedule_id == schedule,
                ScheduleOccurrence.slot_key == key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def history(
        self, owner: int, shop: int, before: int | None, *, unread: bool, now: datetime
    ) -> list[ScheduleOccurrence]:
        query = select(ScheduleOccurrence).where(
            ScheduleOccurrence.owner_id == owner,
            ScheduleOccurrence.shop_id == shop,
        )
        if before:
            query = query.where(ScheduleOccurrence.id < before)
        if unread:
            query = query.where(
                ScheduleOccurrence.read_at.is_(None),
                ScheduleOccurrence.notify_at <= now,
            )
        return list(
            self.session.scalars(
                query.order_by(ScheduleOccurrence.id.desc())
                .limit(50)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def latest_timer(self, owner: int, shop: int) -> ScheduleOccurrence | None:
        return self.session.scalar(
            select(ScheduleOccurrence)
            .where(
                ScheduleOccurrence.owner_id == owner,
                ScheduleOccurrence.shop_id == shop,
                ScheduleOccurrence.trigger == "timer",
            )
            .order_by(ScheduleOccurrence.created_at.desc(), ScheduleOccurrence.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )

    def notification(self, owner: int, shop: int, item: int) -> ScheduleOccurrence | None:
        return self.session.scalar(
            select(ScheduleOccurrence)
            .where(
                ScheduleOccurrence.owner_id == owner,
                ScheduleOccurrence.shop_id == shop,
                ScheduleOccurrence.id == item,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
