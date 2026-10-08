from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.identity import LoginSession, SellerProfile, Shop, User


class IdentityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_user(self, username: str, *, lock: bool = False) -> User | None:
        statement = select(User).where(User.username == username)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def add_user(self, user: User) -> None:
        self.session.add(user)
        try:
            self.session.flush()
        except IntegrityError as error:
            raise ConflictError("账号已存在") from error

    def lock_user(self, user_id: int) -> None:
        self.session.execute(select(User.id).where(User.id == user_id).with_for_update())

    def add_session(self, login_session: LoginSession) -> None:
        self.session.add(login_session)

    def find_session(self, token_hash: str, now: datetime) -> tuple[LoginSession, User] | None:
        row = self.session.execute(
            select(LoginSession, User)
            .join(User, User.id == LoginSession.user_id)
            .where(LoginSession.token_hash == token_hash, LoginSession.expires_at > now)
        ).first()
        return (row[0], row[1]) if row else None

    def delete_session(self, token_hash: str) -> None:
        self.session.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash))

    def delete_user_sessions(self, user_id: int) -> None:
        self.session.execute(delete(LoginSession).where(LoginSession.user_id == user_id))

    def delete_expired_sessions(self, now: datetime) -> None:
        self.session.execute(delete(LoginSession).where(LoginSession.expires_at <= now))

    def get_profile(self, user_id: int, *, lock: bool = False) -> SellerProfile | None:
        statement = select(SellerProfile).where(SellerProfile.user_id == user_id)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def add_profile(self, profile: SellerProfile) -> None:
        self.session.add(profile)
        try:
            self.session.flush()
        except IntegrityError as error:
            raise ConflictError("经营资料已由另一请求创建，请刷新后再试") from error

    def list_shops(self, owner_id: int) -> list[Shop]:
        return list(
            self.session.scalars(select(Shop).where(Shop.owner_id == owner_id).order_by(Shop.id))
        )

    def count_shops(self, owner_id: int) -> int:
        return (
            self.session.scalar(select(func.count(Shop.id)).where(Shop.owner_id == owner_id)) or 0
        )

    def get_shop(self, owner_id: int, shop_id: int, *, lock: bool = False) -> Shop | None:
        statement = select(Shop).where(Shop.id == shop_id, Shop.owner_id == owner_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return self.session.scalar(statement)

    def add_shop(self, shop: Shop) -> None:
        self.session.add(shop)
        try:
            self.session.flush()
        except IntegrityError as error:
            raise ConflictError("该店铺标识已存在，请使用另一个标识") from error
