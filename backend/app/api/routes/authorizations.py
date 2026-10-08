from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.authorizations import (
    AuthorizationOutput,
    AuthorizationPage,
    CreateAuthorization,
    RevokeAuthorization,
)
from app.services.authorizations import AuthorizationsService

router = APIRouter(prefix="/shops/{shop_id}/authorizations", tags=["内部预授权"])


@router.post("")
def create(
    shop_id: int, data: CreateAuthorization, current: CurrentSession, uow: UowDependency
) -> AuthorizationOutput:
    return AuthorizationsService(uow).create(current.user_id, shop_id, data)


@router.get("")
def list_grants(
    shop_id: int,
    current: CurrentSession,
    uow: UowDependency,
    before_id: Annotated[int | None, Query(gt=0)] = None,
) -> AuthorizationPage:
    return AuthorizationsService(uow).list(current.user_id, shop_id, before_id)


@router.get("/{grant_id}")
def get(
    shop_id: int, grant_id: int, current: CurrentSession, uow: UowDependency
) -> AuthorizationOutput:
    return AuthorizationsService(uow).get(current.user_id, shop_id, grant_id)


@router.post("/{grant_id}/revoke")
def revoke(
    shop_id: int,
    grant_id: int,
    data: RevokeAuthorization,
    current: CurrentSession,
    uow: UowDependency,
) -> AuthorizationOutput:
    return AuthorizationsService(uow).revoke(current.user_id, shop_id, grant_id, data.version)


@router.post("/{grant_id}/uses/{use_id}/revert")
def revert(
    shop_id: int, grant_id: int, use_id: int, current: CurrentSession, uow: UowDependency
) -> AuthorizationOutput:
    return AuthorizationsService(uow).revert(current.user_id, shop_id, grant_id, use_id)
