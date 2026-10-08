from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.profit import ProfitFee, ProfitScenario, ProfitStudy
from app.schemas.profit import FEE_LABELS, FeeInput, ScenarioInput, StudyInput


class ProfitRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find(self, owner_id: int, shop_id: int, study_id: int) -> ProfitStudy | None:
        return self.session.scalar(
            select(ProfitStudy)
            .where(
                ProfitStudy.owner_id == owner_id,
                ProfitStudy.shop_id == shop_id,
                ProfitStudy.id == study_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def by_request(self, owner_id: int, request_key: str) -> ProfitStudy | None:
        return self.session.scalar(
            select(ProfitStudy)
            .where(
                ProfitStudy.owner_id == owner_id,
                ProfitStudy.request_key == request_key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def list_studies(self, owner_id: int, shop_id: int, offset: int) -> list[ProfitStudy]:
        return list(
            self.session.scalars(
                select(ProfitStudy)
                .where(
                    ProfitStudy.owner_id == owner_id,
                    ProfitStudy.shop_id == shop_id,
                    ProfitStudy.status == "saved",
                )
                .order_by(ProfitStudy.id.desc())
                .offset(offset)
                .limit(50)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def add(self, record: ProfitStudy, data: StudyInput) -> None:
        self.session.add(record)
        self.session.flush()
        for position, item in enumerate(data.scenarios):
            scenario = ProfitScenario(
                study_id=record.id,
                position=position,
                name=item.name,
                price=item.price,
                purchase_cost=item.purchase_cost,
                basis=item.basis,
            )
            self.session.add(scenario)
            self.session.flush()
            self.session.add_all(
                [ProfitFee(scenario_id=scenario.id, **fee.model_dump()) for fee in item.fees]
            )
        self.session.flush()

    def scenarios(self, record: ProfitStudy) -> list[ProfitScenario]:
        return list(
            self.session.scalars(
                select(ProfitScenario)
                .join(ProfitStudy)
                .where(
                    ProfitStudy.id == record.id,
                    ProfitStudy.owner_id == record.owner_id,
                    ProfitStudy.shop_id == record.shop_id,
                )
                .order_by(ProfitScenario.position)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def input(self, record: ProfitStudy) -> StudyInput:
        scenarios = []
        for row in self.scenarios(record):
            fees = list(
                self.session.scalars(
                    select(ProfitFee)
                    .where(ProfitFee.scenario_id == row.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            by_kind = {fee.kind: fee for fee in fees}
            scenarios.append(
                ScenarioInput(
                    name=row.name,
                    price=row.price,
                    purchase_cost=row.purchase_cost,
                    basis=row.basis,
                    fees=[
                        FeeInput.model_validate(
                            {
                                "kind": kind,
                                "mode": by_kind[kind].mode,
                                "value": by_kind[kind].value,
                                "basis": by_kind[kind].basis,
                            }
                        )
                        for kind in FEE_LABELS
                    ],
                )
            )
        return StudyInput.model_validate(
            {
                "title": record.title,
                "currency": record.currency,
                "data_identity": record.data_identity,
                "scenarios": scenarios,
            }
        )

    def clear(self, record: ProfitStudy) -> None:
        ids = [row.id for row in self.scenarios(record)]
        self.session.execute(delete(ProfitFee).where(ProfitFee.scenario_id.in_(ids)))
        self.session.execute(delete(ProfitScenario).where(ProfitScenario.id.in_(ids)))
        record.title = ""
        record.status = "cleared"
