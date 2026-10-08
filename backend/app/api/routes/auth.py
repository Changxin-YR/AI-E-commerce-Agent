from fastapi import APIRouter, Request, Response

from app.api.dependencies import (
    SESSION_COOKIE,
    CurrentSession,
    SettingsDependency,
    UowDependency,
)
from app.schemas.identity import LoginInput, SessionOutput
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["账号"])


@router.post("/login", response_model=SessionOutput)
def login(
    data: LoginInput, response: Response, uow: UowDependency, settings: SettingsDependency
) -> SessionOutput:
    result = AuthService(uow, settings).login(data)
    response.set_cookie(
        SESSION_COOKIE,
        result.token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api",
    )
    return result.session


@router.get("/session", response_model=SessionOutput)
def current_session(current: CurrentSession) -> SessionOutput:
    return current


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    current: CurrentSession,
    uow: UowDependency,
    settings: SettingsDependency,
) -> None:
    AuthService(uow, settings).logout(request.cookies[SESSION_COOKIE], current.user_id)
    response.delete_cookie(SESSION_COOKIE, path="/api", secure=settings.cookie_secure)
