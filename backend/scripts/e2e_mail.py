"""Synthetic inbox/provider used only by the isolated browser-test launcher."""

from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_settings
from app.api.routes.outbound import get_provider
from app.core.config import Settings
from app.models.identity import Shop, User
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.services.auth import AuthService
from app.services.outbound_provider import MailEnvelope, MailResult


class BrowserMail:
    def __init__(self) -> None:
        self.messages: list[MailEnvelope] = []
        self.receipt = str(uuid4())

    def verify_sender(self) -> bool:
        return True

    def send(self, envelope: MailEnvelope) -> MailResult:
        self.messages.append(envelope)
        # Exercise a real unknown-state workflow for summaries without using any network.
        return (
            MailResult("accepted", str(uuid4()), "submitted")
            if len(self.messages) == 1
            else MailResult("unknown")
        )

    def reconcile(self, envelope: MailEnvelope, receipt_id: str | None) -> MailResult:
        return MailResult("accepted", self.receipt, "delivered")


def configure(app: FastAPI, settings: Settings, factory: sessionmaker[Session]) -> None:
    with factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "e2e_seller"))
        assert owner
        shop = Shop(
            owner_id=owner,
            code="e2e-outbound",
            name="合成外发测试店铺",
            platform="other",
            market="US",
            currency="USD",
            timezone="Asia/Shanghai",
        )
        session.add(shop)
        session.flush()
        config = settings.model_copy(
            update={
                "outbound_enabled": True,
                "outbound_provider": "resend",
                "outbound_api_key": SecretStr("synthetic-test-double"),
                "outbound_owner_id": owner,
                "outbound_shop_id": shop.id,
                "outbound_sender": "sender@example.invalid",
                "outbound_test_recipient": "inbox@example.invalid",
                "outbound_domain_id": uuid4(),
            }
        )
        qq_owner = AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="e2e_qq_seller", password="Synthetic-E2E-Password-2026!")
        )
        qq_shop = Shop(
            owner_id=qq_owner,
            code="e2e-qq-mail",
            name="合成 QQ 邮件店铺",
            platform="other",
            market="US",
            currency="USD",
            timezone="Asia/Shanghai",
        )
        session.add(qq_shop)
        session.flush()
        qq_shop_id = qq_shop.id
        qq_config = config.model_copy(
            update={
                "outbound_provider": "qq_smtp",
                "outbound_owner_id": qq_owner,
                "outbound_shop_id": qq_shop_id,
                "outbound_sender": "synthetic-owner@qq.com",
                "outbound_test_recipient": "synthetic-owner@qq.com",
                "outbound_smtp_authorization_code": SecretStr("synthetic-not-a-real-code"),
            }
        )
        session.commit()
    provider = BrowserMail()
    qq_provider = BrowserMail()

    def active_config(request: Request) -> Settings:
        return qq_config if request.url.path.startswith(f"/api/shops/{qq_shop_id}/") else config

    def active_provider(request: Request) -> BrowserMail:
        return qq_provider if request.url.path.startswith(f"/api/shops/{qq_shop_id}/") else provider

    app.dependency_overrides[get_settings] = active_config
    app.dependency_overrides[get_provider] = active_provider

    @app.get("/api/e2e/synthetic-inbox")
    def inbox() -> list[dict[str, str]]:
        return [{"subject": m.subject, "body": m.body} for m in provider.messages]

    @app.get("/api/e2e/synthetic-qq-inbox")
    def qq_inbox() -> list[dict[str, str]]:
        return [
            {"recipient": m.recipient, "subject": m.subject, "body": m.body}
            for m in qq_provider.messages
        ]
