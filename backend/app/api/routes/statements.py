from fastapi import APIRouter

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.expenses import ExpenseScope
from app.schemas.statements import StatementReconciliation
from app.services.statements import StatementService

router = APIRouter(prefix="/shops/{shop_id}/statements", tags=["渠道账单"])


@router.post("/reconcile")
def reconcile(
    shop_id: int, data: ExpenseScope, current: CurrentSession, uow: UowDependency
) -> StatementReconciliation:
    return StatementService(uow).reconcile(current.user_id, shop_id, data)
