import asyncio
import logging
from contextlib import suppress

from sqlalchemy.orm import Session, sessionmaker

from app.core.time import utc_now
from app.repositories.unit_of_work import UnitOfWork
from app.services.schedules import SchedulesService

logger = logging.getLogger(__name__)


def tick(factory: sessionmaker[Session]) -> int:
    now = utc_now()
    with factory() as session:
        due = UnitOfWork(session).schedules.due(now)
    count = 0
    for owner, shop, schedule, version, scheduled_at in due:
        try:
            with factory() as session:
                count += SchedulesService(UnitOfWork(session)).run_due(
                    owner, shop, schedule, utc_now()
                )
        except Exception as error:
            # No source content, database URL or driver error text in application logs.
            logger.warning("Schedule cycle rolled back (%s)", type(error).__name__)
            try:
                with factory() as session:
                    SchedulesService(UnitOfWork(session)).fail_due(
                        owner, shop, schedule, version, scheduled_at, utc_now()
                    )
            except Exception as recovery_error:
                logger.warning(
                    "Schedule failure record unavailable (%s)", type(recovery_error).__name__
                )
    return count


async def serve(factory: sessionmaker[Session], stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(tick, factory)
        except Exception as error:
            logger.warning("Scheduler unavailable (%s)", type(error).__name__)
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=30)
