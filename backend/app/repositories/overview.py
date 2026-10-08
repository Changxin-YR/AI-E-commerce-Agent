from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, defer

from app.models.operations import OperationTask
from app.models.overview import OverviewReport, OverviewShop, OverviewSource


class OverviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def by_request(self, owner: int, request: str) -> OverviewReport | None:
        return self.session.scalar(
            select(OverviewReport)
            .where(OverviewReport.owner_id == owner, OverviewReport.request_id == request)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def get(self, owner: int, report_id: int) -> OverviewReport | None:
        return self.session.scalar(
            select(OverviewReport)
            .where(OverviewReport.owner_id == owner, OverviewReport.id == report_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def page(self, owner: int, before: int | None) -> list[OverviewReport]:
        query = select(OverviewReport).where(OverviewReport.owner_id == owner)
        if before is not None:
            query = query.where(OverviewReport.id < before)
        return list(
            self.session.scalars(
                query.order_by(OverviewReport.id.desc())
                .limit(21)
                .options(defer(OverviewReport.snapshot))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def tasks(self, owner: int, shop: int, identity: str) -> list[OperationTask]:
        return list(
            self.session.scalars(
                select(OperationTask)
                .where(
                    OperationTask.owner_id == owner,
                    OperationTask.shop_id == shop,
                    OperationTask.data_identity == identity,
                    OperationTask.status.in_(["pending_approval", "open", "deferred"]),
                    OperationTask.source_status != "cleared",
                )
                .order_by(OperationTask.id.desc())
                .limit(51)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def add(self, report: OverviewReport, shops: list[int], batches: set[int]) -> None:
        self.session.add(report)
        self.session.flush()
        self.session.add_all([OverviewShop(report_id=report.id, shop_id=s) for s in shops])
        self.session.add_all([OverviewSource(report_id=report.id, batch_id=b) for b in batches])

    def invalidate(self, owner: int, shop: int) -> None:
        ids = select(OverviewShop.report_id).where(OverviewShop.shop_id == shop)
        self.session.execute(
            update(OverviewReport)
            .where(
                OverviewReport.owner_id == owner,
                OverviewReport.id.in_(ids),
                OverviewReport.status == "current",
            )
            .values(status="stale")
        )

    def clear(self, report: OverviewReport) -> None:
        report.snapshot = None
        report.status = "cleared"
        report.valid_until = None
        self.session.execute(delete(OverviewSource).where(OverviewSource.report_id == report.id))

    def purge_batch(self, owner: int, shop: int, batch: int) -> None:
        reports = self.session.scalars(
            select(OverviewReport)
            .join(OverviewSource)
            .join(
                OverviewShop,
                OverviewShop.report_id == OverviewReport.id,
            )
            .where(
                OverviewReport.owner_id == owner,
                OverviewShop.shop_id == shop,
                OverviewSource.batch_id == batch,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
        for report in reports:
            self.clear(report)
