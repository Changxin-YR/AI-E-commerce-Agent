from fastapi import APIRouter

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.analytics import (
    AnalysisInput,
    AnalysisResult,
    QuestionInput,
    SavedOutput,
    SaveInput,
    SourceOutput,
    TodoAction,
)
from app.schemas.order_costs import CostHistory, CostWrite
from app.services.analytics import AnalyticsService
from app.services.order_costs import OrderCostService

router = APIRouter(prefix="/shops/{shop_id}/analytics", tags=["经营分析"])


@router.get("/order-costs/{row_id}")
def cost_history(
    shop_id: int, row_id: int, current: CurrentSession, uow: UowDependency
) -> CostHistory:
    return OrderCostService(uow).get(current.user_id, shop_id, row_id)


@router.post("/order-costs/{row_id}")
def write_cost(
    shop_id: int, row_id: int, data: CostWrite, current: CurrentSession, uow: UowDependency
) -> CostHistory:
    return OrderCostService(uow).write(current.user_id, shop_id, row_id, data)


@router.get("/revision")
def revision(shop_id: int, current: CurrentSession, uow: UowDependency) -> int:
    return AnalyticsService(uow).revision(current.user_id, shop_id)


@router.get("/saved/{analysis_id}")
def get_saved(
    shop_id: int, analysis_id: int, current: CurrentSession, uow: UowDependency
) -> SavedOutput:
    return AnalyticsService(uow).get_saved(current.user_id, shop_id, analysis_id)


@router.post("/calculate")
def calculate(
    shop_id: int, data: AnalysisInput, current: CurrentSession, uow: UowDependency
) -> AnalysisResult:
    return AnalyticsService(uow).run(current.user_id, shop_id, data)


@router.post("/ask")
def ask(
    shop_id: int, data: QuestionInput, current: CurrentSession, uow: UowDependency
) -> AnalysisResult:
    return AnalyticsService(uow).ask(current.user_id, shop_id, data)


@router.post("/saved", status_code=201)
def save(shop_id: int, data: SaveInput, current: CurrentSession, uow: UowDependency) -> SavedOutput:
    return AnalyticsService(uow).save(current.user_id, shop_id, data)


@router.get("/saved")
def list_saved(shop_id: int, current: CurrentSession, uow: UowDependency) -> list[SavedOutput]:
    return AnalyticsService(uow).list_saved(current.user_id, shop_id)


@router.post("/saved/{analysis_id}/todo")
def todo(
    shop_id: int, analysis_id: int, current: CurrentSession, uow: UowDependency
) -> SavedOutput:
    return AnalyticsService(uow).create_todo(current.user_id, shop_id, analysis_id)


@router.get("/sources/{row_id}")
def source(shop_id: int, row_id: int, current: CurrentSession, uow: UowDependency) -> SourceOutput:
    return AnalyticsService(uow).source(current.user_id, shop_id, row_id)


@router.post("/saved/{analysis_id}/todo/action")
def change_todo(
    shop_id: int, analysis_id: int, data: TodoAction, current: CurrentSession, uow: UowDependency
) -> SavedOutput:
    return AnalyticsService(uow).change_todo(current.user_id, shop_id, analysis_id, data)
