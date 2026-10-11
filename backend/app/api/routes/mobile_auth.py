"""Mobile transport for existing account and business authorization services."""

from collections import OrderedDict, deque
from datetime import datetime
from threading import Lock
from time import monotonic
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.dependencies import CurrentSession, SettingsDependency, UowDependency
from app.core.errors import BusinessError
from app.core.security import token_digest
from app.core.time import utc_now
from app.schemas.identity import LoginInput
from app.services.auth import AuthService

router = APIRouter(prefix="/mobile/auth", tags=["移动会话"])
_login_attempts: OrderedDict[str, deque[float]] = OrderedDict()
_attempt_lock = Lock()


class MobileLoginInput(LoginInput):
    client_type: Literal["ohos", "android", "weapp"] = "ohos"


class MobileSessionOutput(BaseModel):
    user_id: int
    username: str
    session_id: str
    client_type: str
    expires_at: datetime


class MobileLoginOutput(MobileSessionOutput):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"


def mobile_token(request: Request) -> str:
    value = request.headers.get("authorization", "")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise BusinessError("invalid_credentials", "请先登录移动端", 401)
    return token


def throttle(request: Request) -> None:
    # Bounded process-local limiter supplements persistent per-account lockout.
    address = request.client.host if request.client else "unknown"
    now = monotonic()
    with _attempt_lock:
        attempts = _login_attempts.setdefault(address, deque())
        _login_attempts.move_to_end(address)
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= 20:
            raise BusinessError("login_rate_limited", "登录过于频繁，请稍后重试", 429)
        attempts.append(now)
        while len(_login_attempts) > 2048:
            _login_attempts.popitem(last=False)


@router.post("/login", response_model=MobileLoginOutput)
def login(
    data: MobileLoginInput, request: Request, uow: UowDependency, settings: SettingsDependency
) -> MobileLoginOutput:
    if request.headers.get("authorization") or request.cookies.get("soloops_session"):
        raise BusinessError("ambiguous_credentials", "登录前请清除旧会话", 400)
    throttle(request)
    result = AuthService(uow, settings).login(data, client_type=data.client_type)
    return MobileLoginOutput(
        user_id=result.session.user_id,
        username=result.session.username,
        session_id=result.device_session_id or "",
        client_type=data.client_type,
        expires_at=result.expires_at,
        access_token=result.token,
    )


@router.get("/session", response_model=MobileSessionOutput)
def session(request: Request, current: CurrentSession, uow: UowDependency) -> MobileSessionOutput:
    row = uow.identity.find_session(token_digest(mobile_token(request)), utc_now())
    if row is None or row[0].device_session_id is None:
        raise BusinessError("invalid_credentials", "登录已失效", 401)
    return MobileSessionOutput(
        user_id=current.user_id,
        username=current.username,
        session_id=row[0].device_session_id,
        client_type=row[0].client_type,
        expires_at=row[0].expires_at,
    )


@router.post("/logout", status_code=204)
def logout(
    request: Request, current: CurrentSession, uow: UowDependency, settings: SettingsDependency
) -> None:
    AuthService(uow, settings).logout(mobile_token(request), current.user_id)


@router.post("/logout-all", status_code=204)
def logout_all(
    request: Request, current: CurrentSession, uow: UowDependency, settings: SettingsDependency
) -> None:
    mobile_token(request)
    AuthService(uow, settings).logout_all(current.user_id)
