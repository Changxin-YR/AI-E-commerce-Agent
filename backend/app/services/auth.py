from dataclasses import dataclass
from datetime import timedelta

from app.core.config import Settings
from app.core.errors import AuthenticationError, BusinessError, NotFoundError
from app.core.security import hash_password, new_token, token_digest, verify_password
from app.core.time import utc_now
from app.models.identity import LoginSession, User
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput, LoginInput, SessionOutput

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


@dataclass(frozen=True)
class LoginResult:
    token: str
    session: SessionOutput


class AuthService:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self.uow = uow
        self.settings = settings

    def create_account(self, data: AccountInput) -> int:
        user = User(
            username=data.username,
            password_hash=hash_password(data.password.get_secret_value()),
        )
        self.uow.identity.add_user(user)
        self.uow.record_event(user.id, "account.created", "user", user.id)
        self.uow.commit()
        return user.id

    def reset_password(self, data: AccountInput) -> None:
        user = self.uow.identity.find_user(data.username, lock=True)
        if user is None:
            raise NotFoundError("账号不存在")
        user.password_hash = hash_password(data.password.get_secret_value())
        user.failed_login_count = 0
        user.locked_until = None
        self.uow.identity.delete_user_sessions(user.id)
        self.uow.record_event(user.id, "account.password_reset", "user", user.id)
        self.uow.commit()

    def login(self, data: LoginInput) -> LoginResult:
        now = utc_now()
        user = self.uow.identity.find_user(data.username.strip().lower(), lock=True)
        valid = verify_password(
            data.password.get_secret_value(), user.password_hash if user else None
        )
        if user is None:
            raise AuthenticationError("账号或密码错误")
        if user.locked_until and user.locked_until > now:
            raise BusinessError("login_locked", "尝试次数过多，请 15 分钟后重试", 429)
        if user.locked_until:
            user.failed_login_count = 0
            user.locked_until = None
        if not valid:
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            # Failed attempts must survive the rejected HTTP response.
            self.uow.commit()
            raise AuthenticationError("账号或密码错误")

        user.failed_login_count = 0
        user.locked_until = None
        token = new_token()
        csrf_token = new_token()
        self.uow.identity.delete_expired_sessions(now)
        self.uow.identity.add_session(
            LoginSession(
                token_hash=token_digest(token),
                user_id=user.id,
                csrf_token=csrf_token,
                expires_at=now + timedelta(hours=self.settings.session_hours),
            )
        )
        self.uow.record_event(user.id, "session.created", "user", user.id)
        self.uow.commit()
        return LoginResult(
            token=token,
            session=SessionOutput(user_id=user.id, username=user.username, csrf_token=csrf_token),
        )

    def authenticate(self, token: str | None) -> SessionOutput:
        if token is None or len(token) > 128:
            raise AuthenticationError()
        result = self.uow.identity.find_session(token_digest(token), utc_now())
        if result is None:
            raise AuthenticationError("登录已过期，请重新登录")
        login_session, user = result
        return SessionOutput(
            user_id=user.id, username=user.username, csrf_token=login_session.csrf_token
        )

    def logout(self, token: str, user_id: int) -> None:
        self.uow.identity.delete_session(token_digest(token))
        self.uow.record_event(user_id, "session.revoked", "user", user_id)
        self.uow.commit()
