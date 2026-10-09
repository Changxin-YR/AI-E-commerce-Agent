from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.schedules import OperationSchedule, ScheduleOccurrence
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import AgentAction, ModelStatus, StartAgent
from app.schemas.operations import OperationScope
from app.schemas.schedules import (
    CreateSchedule,
    ManualCheck,
    OccurrenceOutput,
    ScheduleAction,
    ScheduleConfig,
    ScheduleOutput,
)
from app.services.agent import AgentService
from app.services.agent_model import GenerationReply, ModelReply
from app.services.business_rules import BusinessRulesService
from app.services.listings import digest
from app.services.profit_calculation import utc_text
from app.services.schedule_clock import notification_time, occurrence


class LocalOnlyModel:
    """A scheduler cannot obtain a configured network adapter, even if the app has one."""

    def status(self) -> ModelStatus:
        return ModelStatus(
            status="not_configured", provider="local_rules", model="", reason="本地定时检查"
        )

    def reserve(self, goal: str) -> Decimal:
        raise BusinessError("scheduler_local_only", "定时检查只允许本地规则")

    def decide(self, goal: str, timeout: float) -> ModelReply:
        raise BusinessError("scheduler_local_only", "定时检查只允许本地规则")

    def reserve_generation(self, request: dict[str, Any]) -> Decimal:
        raise BusinessError("scheduler_local_only", "定时检查只允许本地规则")

    def generate(self, request: dict[str, Any], timeout: float) -> GenerationReply:
        raise BusinessError("scheduler_local_only", "定时检查只允许本地规则")


def operation_scope(config: ScheduleConfig, scheduled: datetime) -> OperationScope:
    end = scheduled.replace(tzinfo=UTC)
    return OperationScope(
        start_at=end - timedelta(days=config.lookback_days),
        end_at=end,
        **config.model_dump(
            include={
                "timezone",
                "currency",
                "channel",
                "data_identity",
                "rule_revision_id",
                "max_age_hours",
                "min_quantity",
                "max_margin_percent",
            }
        ),
    )


class SchedulesService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow, self.repo = uow, uow.schedules

    def _shop(self, owner: int, shop: int) -> None:
        self.uow.identity.lock_user(owner)
        if self.uow.identity.get_shop(owner, shop, lock=True) is None:
            raise NotFoundError()

    def _load(self, owner: int, shop: int, schedule: int) -> OperationSchedule:
        self._shop(owner, shop)
        row = self.repo.get(owner, shop, schedule)
        if row is None:
            raise NotFoundError()
        return row

    def _validate(self, owner: int, shop: int, config: ScheduleConfig, now: datetime) -> None:
        BusinessRulesService(self.uow).validate_scope(owner, shop, operation_scope(config, now))

    def _output(self, row: OperationSchedule) -> ScheduleOutput:
        return ScheduleOutput(
            id=row.id,
            shop_id=row.shop_id,
            status=row.status,
            version=row.version,
            config=ScheduleConfig.model_validate(row.config),
            next_run_at=utc_text(row.next_run_at) if row.next_run_at else None,
            created_at=utc_text(row.created_at),
        )

    def _notice(self, row: ScheduleOccurrence) -> OccurrenceOutput:
        return OccurrenceOutput(
            id=row.id,
            shop_id=row.shop_id,
            schedule_id=row.schedule_id,
            schedule_version=row.schedule_version,
            trigger=row.trigger,
            scheduled_at=utc_text(row.scheduled_at),
            coalesced_from=utc_text(row.coalesced_from) if row.coalesced_from else None,
            execution_id=row.execution_id,
            status=row.status,
            reason=row.reason,
            notify_at=utc_text(row.notify_at),
            read_at=utc_text(row.read_at) if row.read_at else None,
            created_at=utc_text(row.created_at),
        )

    def create(self, owner: int, shop: int, data: CreateSchedule) -> ScheduleOutput:
        self._shop(owner, shop)
        if not data.confirmed:
            raise ConflictError("请确认周期检查范围和站内通知")
        key = digest([shop, data.config.model_dump(mode="json")])
        prior = self.repo.by_request(owner, str(data.request_id))
        if prior:
            if prior.request_hash != key:
                raise ConflictError("请求标识已用于其他计划")
            return self._output(prior)
        if len(self.repo.schedules(owner, shop)) >= 100:
            raise ConflictError("每店最多保留 100 个计划，请修改已有计划")
        now = utc_now()
        self._validate(owner, shop, data.config, now)
        row = OperationSchedule(
            owner_id=owner,
            shop_id=shop,
            request_id=str(data.request_id),
            request_hash=key,
            config=data.config.model_dump(mode="json"),
            next_run_at=occurrence(data.config, now, future=True),
        )
        self.repo.add(row)
        self._event(row, "create")
        output = self._output(row)
        self.uow.commit()
        return output

    def _event(self, row: OperationSchedule, action: str) -> None:
        self.uow.record_event(
            row.owner_id,
            f"schedule.{action}",
            "operation_schedule",
            row.id,
            {"version": row.version, "status": row.status},
        )

    def schedules(self, owner: int, shop: int) -> list[ScheduleOutput]:
        self._shop(owner, shop)
        return [self._output(row) for row in self.repo.schedules(owner, shop)]

    def act(self, owner: int, shop: int, schedule: int, data: ScheduleAction) -> ScheduleOutput:
        row = self._load(owner, shop, schedule)
        target = {"pause": "paused", "resume": "active", "revoke": "revoked"}.get(data.action)
        if row.status == target:
            return self._output(row)
        if row.version != data.version or row.status == "revoked":
            raise ConflictError("计划已变化或已撤销，请刷新")
        if data.action in {"resume", "edit"}:
            if not data.confirmed:
                raise ConflictError("请重新确认周期检查范围")
            config = (
                data.config if data.action == "edit" else ScheduleConfig.model_validate(row.config)
            )
            if config is None:
                raise ConflictError("请提供完整计划配置")
            self._validate(owner, shop, config, utc_now())
            row.config = config.model_dump(mode="json")
            row.next_run_at = occurrence(config, utc_now(), future=True)
        if target:
            row.status = target
        if row.status != "active":
            row.next_run_at = None
        row.version += 1
        self._event(row, data.action)
        output = self._output(row)
        self.uow.commit()
        return output

    def manual(self, owner: int, shop: int, schedule: int, data: ManualCheck) -> OccurrenceOutput:
        row = self._load(owner, shop, schedule)
        key = f"manual:{data.request_id}"
        prior = self.repo.by_slot(row.id, key)
        if prior:
            return self._notice(prior)
        if row.status != "active" or row.version != data.version:
            raise ConflictError("计划已变化或未启用，请刷新")
        now = utc_now()
        notice = self._execute(row, key, now, now, "manual", None)
        output = self._notice(notice)
        self.uow.commit()
        return output

    def run_due(self, owner: int, shop: int, schedule: int, now: datetime) -> bool:
        row = self._load(owner, shop, schedule)
        if row.status != "active" or row.next_run_at is None or row.next_run_at > now:
            return False
        config = ScheduleConfig.model_validate(row.config)
        due = occurrence(config, now, future=False)
        first = row.next_run_at
        if due < first:
            return False
        key = f"timer:{utc_text(due)}"
        row.next_run_at = occurrence(config, now, future=True)
        if self.repo.by_slot(row.id, key) is None:
            self._execute(row, key, due, now, "timer", first if first < due else None)
        self.uow.commit()
        return True

    def _execute(
        self,
        row: OperationSchedule,
        key: str,
        due: datetime,
        now: datetime,
        trigger: str,
        coalesced: datetime | None,
    ) -> ScheduleOccurrence:
        config = ScheduleConfig.model_validate(row.config)
        executed_version = row.version
        execution_id = None
        status, reason = "missed", "outside_recovery_window"
        if now - due <= timedelta(hours=24):
            try:
                # No network and no intermediate commit. Crash rolls back the entire cycle.
                with self.uow.session.begin_nested(), self.uow.defer_commits():
                    service = AgentService(self.uow, LocalOnlyModel())
                    run = service.start(
                        row.owner_id,
                        row.shop_id,
                        StartAgent(
                            request_id=uuid4(),
                            template="daily",
                            scope=operation_scope(config, due),
                        ),
                    )
                    run = service.act(
                        row.owner_id,
                        row.shop_id,
                        run.id,
                        AgentAction(version=run.version, action="advance"),
                    )
                    execution_id, status, reason = run.id, run.status, run.reason
            except BusinessError as error:
                status, reason = "blocked", error.code
        if status not in {"waiting_approval", "succeeded", "missed"}:
            row.status, row.next_run_at = "paused", None
            row.version += 1
            self._event(row, "blocked")
        notice = ScheduleOccurrence(
            owner_id=row.owner_id,
            shop_id=row.shop_id,
            schedule_id=row.id,
            schedule_version=executed_version,
            slot_key=key,
            trigger=trigger,
            scheduled_at=due,
            coalesced_from=coalesced,
            execution_id=execution_id,
            status=status,
            reason=reason,
            notify_at=notification_time(config, now),
            created_at=now,
        )
        self.repo.add(notice)
        self._event(row, "checked" if execution_id else "missed_or_blocked")
        return notice

    def fail_due(
        self,
        owner: int,
        shop: int,
        schedule: int,
        version: int,
        expected_due: datetime,
        now: datetime,
    ) -> None:
        """Called only after a full rollback; do not overwrite another worker/user's change."""
        row = self._load(owner, shop, schedule)
        if row.status != "active" or row.version != version or row.next_run_at != expected_due:
            return
        config = ScheduleConfig.model_validate(row.config)
        due = occurrence(config, now, future=False)
        key = f"timer:{utc_text(due)}"
        if self.repo.by_slot(row.id, key):
            return
        row.status, row.next_run_at = "paused", None
        row.version += 1
        self.repo.add(
            ScheduleOccurrence(
                owner_id=owner,
                shop_id=shop,
                schedule_id=schedule,
                schedule_version=version,
                slot_key=key,
                trigger="timer",
                scheduled_at=due,
                coalesced_from=expected_due if expected_due < due else None,
                status="blocked",
                reason="local_check_failed",
                notify_at=notification_time(config, now),
            )
        )
        self._event(row, "failed")
        self.uow.commit()

    def history(
        self, owner: int, shop: int, before: int | None = None, *, unread: bool = False
    ) -> list[OccurrenceOutput]:
        self._shop(owner, shop)
        return [
            self._notice(row)
            for row in self.repo.history(owner, shop, before, unread=unread, now=utc_now())
        ]

    def mark_read(self, owner: int, shop: int, item: int) -> OccurrenceOutput:
        self._shop(owner, shop)
        row = self.repo.notification(owner, shop, item)
        if row is None:
            raise NotFoundError()
        if row.read_at is None:
            row.read_at = utc_now()
        output = self._notice(row)
        self.uow.commit()
        return output
