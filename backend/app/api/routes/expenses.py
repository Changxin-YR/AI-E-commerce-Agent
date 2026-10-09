from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.expenses import (
    ExpenseControl,
    ExpenseOrders,
    ExpensePage,
    ExpenseSaved,
    ExpenseScope,
    ExpenseSummary,
    ExpenseWrite,
)
from app.schemas.imports import DataIdentity, SourceChannel
from app.services.expenses import ExpenseService

router = APIRouter(prefix="/shops/{shop_id}/expenses", tags=["实际费用"])


@router.post("", status_code=201)
def create(
    shop_id: int, data: ExpenseWrite, current: CurrentSession, uow: UowDependency
) -> ExpenseSaved:
    return ExpenseService(uow).write(current.user_id, shop_id, data)


@router.get("")
def page(
    shop_id: int,
    data_identity: DataIdentity,
    channel: SourceChannel,
    current: CurrentSession,
    uow: UowDependency,
    before: Annotated[int | None, Query(gt=0)] = None,
) -> ExpensePage:
    return ExpenseService(uow).page(current.user_id, shop_id, data_identity, channel, before)


@router.get("/orders")
def orders(
    shop_id: int,
    data_identity: DataIdentity,
    channel: SourceChannel,
    order_id: Annotated[str, Query(min_length=1, max_length=120)],
    current: CurrentSession,
    uow: UowDependency,
) -> ExpenseOrders:
    return ExpenseService(uow).orders(current.user_id, shop_id, data_identity, channel, order_id)


@router.post("/summary")
def summary(
    shop_id: int, data: ExpenseScope, current: CurrentSession, uow: UowDependency
) -> ExpenseSummary:
    return ExpenseService(uow).summary(current.user_id, shop_id, data)


@router.get("/{expense_id}")
def get(shop_id: int, expense_id: int, current: CurrentSession, uow: UowDependency) -> ExpenseSaved:
    return ExpenseService(uow).get(current.user_id, shop_id, expense_id)


@router.post("/{expense_id}")
def update(
    shop_id: int, expense_id: int, data: ExpenseWrite, current: CurrentSession, uow: UowDependency
) -> ExpenseSaved:
    return ExpenseService(uow).write(current.user_id, shop_id, data, expense_id)


@router.post("/{expense_id}/{action}")
def control(
    shop_id: int,
    expense_id: int,
    action: Literal["withdraw", "clear"],
    data: ExpenseControl,
    current: CurrentSession,
    uow: UowDependency,
) -> ExpenseSaved:
    return ExpenseService(uow).control(current.user_id, shop_id, expense_id, action, data)
