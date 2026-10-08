import secrets
from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import BusinessError
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import SessionOutput
from app.services.auth import AuthService

SESSION_COOKIE = "soloops_session"


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_uow(request: Request) -> Iterator[UnitOfWork]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    # Closing rolls back any uncommitted work, including unexpected exceptions.
    with factory() as session:
        yield UnitOfWork(session)


SettingsDependency = Annotated[Settings, Depends(get_settings)]
UowDependency = Annotated[UnitOfWork, Depends(get_uow)]


def get_current_session(
    request: Request, uow: UowDependency, settings: SettingsDependency
) -> SessionOutput:
    current = AuthService(uow, settings).authenticate(request.cookies.get(SESSION_COOKIE))
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_token = request.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(csrf_token, current.csrf_token):
            raise BusinessError("csrf_rejected", "请求验证失败，请刷新页面后重试", 403)
    return current


CurrentSession = Annotated[SessionOutput, Depends(get_current_session)]
