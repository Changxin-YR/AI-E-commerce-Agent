import hashlib
import json

from app.core.errors import ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.profit import ProfitStudy
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.profit import (
    SavedStudyOutput,
    SavedStudySummary,
    SaveStudyInput,
    StudyInput,
    StudyResult,
)
from app.services.profit_calculation import utc_text
from app.services.profit_rules import RULE_VERSION, calculate_study


def input_hash(data: StudyInput) -> str:
    values = data.model_dump()
    for scenario in values["scenarios"]:
        scenario["fees"].sort(key=lambda fee: fee["kind"])
    canonical = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda value: format(value, ".4f"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class ProfitService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def _scope(self, owner_id: int, shop_id: int) -> None:
        self.uow.identity.lock_user(owner_id)
        if self.uow.identity.get_shop(owner_id, shop_id, lock=True) is None:
            raise NotFoundError()

    def calculate(self, owner_id: int, shop_id: int, data: StudyInput) -> StudyResult:
        self._scope(owner_id, shop_id)
        result = calculate_study(data, utc_text(utc_now()))
        self.uow.commit()
        return result

    def _record(self, owner_id: int, shop_id: int, study_id: int) -> ProfitStudy:
        record = self.uow.profit.find(owner_id, shop_id, study_id)
        if record is None or record.status == "cleared":
            raise NotFoundError()
        return record

    def _summary(self, record: ProfitStudy) -> SavedStudySummary:
        return SavedStudySummary(
            id=record.id,
            title=record.title,
            currency=record.currency,
            data_identity=record.data_identity,
            created_at=utc_text(record.created_at),
        )

    def _output(self, record: ProfitStudy) -> SavedStudyOutput:
        if record.rule_version != RULE_VERSION:
            raise ConflictError("此方案的计算规则版本需由系统保留支持，不能静默改算")
        return SavedStudyOutput(
            **self._summary(record).model_dump(),
            result=calculate_study(self.uow.profit.input(record), utc_text(record.created_at)),
        )

    def save(self, owner_id: int, shop_id: int, data: SaveStudyInput) -> SavedStudyOutput:
        self._scope(owner_id, shop_id)
        inputs = StudyInput.model_validate(data.model_dump(exclude={"request_key"}))
        digest = input_hash(inputs)
        record = self.uow.profit.by_request(owner_id, str(data.request_key))
        if record is not None:
            if record.shop_id != shop_id or record.input_hash != digest or record.status != "saved":
                raise ConflictError("保存请求已用于其他内容或已清除，请创建新的保存请求")
        else:
            record = ProfitStudy(
                owner_id=owner_id,
                shop_id=shop_id,
                request_key=str(data.request_key),
                input_hash=digest,
                title=data.title,
                currency=data.currency,
                data_identity=data.data_identity,
                rule_version=RULE_VERSION,
            )
            self.uow.profit.add(record, inputs)
            self.uow.record_event(owner_id, "profit.save", "profit_study", record.id)
        output = self._output(record)
        self.uow.commit()
        return output

    def get(self, owner_id: int, shop_id: int, study_id: int) -> SavedStudyOutput:
        self._scope(owner_id, shop_id)
        output = self._output(self._record(owner_id, shop_id, study_id))
        self.uow.commit()
        return output

    def list(self, owner_id: int, shop_id: int, offset: int) -> list[SavedStudySummary]:
        self._scope(owner_id, shop_id)
        output = [
            self._summary(row) for row in self.uow.profit.list_studies(owner_id, shop_id, offset)
        ]
        self.uow.commit()
        return output

    def clear(self, owner_id: int, shop_id: int, study_id: int) -> None:
        self._scope(owner_id, shop_id)
        record = self.uow.profit.find(owner_id, shop_id, study_id)
        if record is None:
            raise NotFoundError()
        if record.status != "cleared":
            self.uow.profit.clear(record)
            self.uow.record_event(owner_id, "profit.clear", "profit_study", record.id)
        self.uow.commit()
