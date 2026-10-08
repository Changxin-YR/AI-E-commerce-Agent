from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authorizations import AuthorizationUse, InternalAuthorization


class AuthorizationsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, item: InternalAuthorization | AuthorizationUse) -> None:
        self.session.add(item)
        self.session.flush()

    def get(self, owner: int, shop: int, grant: int) -> InternalAuthorization | None:
        return self.session.scalar(
            select(InternalAuthorization)
            .where(
                InternalAuthorization.owner_id == owner,
                InternalAuthorization.shop_id == shop,
                InternalAuthorization.id == grant,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def by_request(self, owner: int, request: str) -> InternalAuthorization | None:
        return self.session.scalar(
            select(InternalAuthorization)
            .where(
                InternalAuthorization.owner_id == owner, InternalAuthorization.request_id == request
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def grants(self, owner: int, shop: int, before: int | None) -> list[InternalAuthorization]:
        query = select(InternalAuthorization).where(
            InternalAuthorization.owner_id == owner, InternalAuthorization.shop_id == shop
        )
        if before is not None:
            query = query.where(InternalAuthorization.id < before)
        return list(
            self.session.scalars(
                query.order_by(InternalAuthorization.id.desc())
                .limit(51)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def uses(self, grant: int) -> list[AuthorizationUse]:
        return list(
            self.session.scalars(
                select(AuthorizationUse)
                .where(AuthorizationUse.authorization_id == grant)
                .order_by(AuthorizationUse.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def for_execution(self, execution: int) -> AuthorizationUse | None:
        return self.session.scalar(
            select(AuthorizationUse)
            .where(AuthorizationUse.execution_id == execution)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
