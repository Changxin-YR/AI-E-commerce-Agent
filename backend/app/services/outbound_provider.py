"""Fixed-host mail adapter. A POST is attempted once; reconciliation is GET-only."""

import hashlib
import json
import re
from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol
from uuid import UUID

import httpx

from app.core.config import Settings
from app.services.listings import digest

ADDRESS = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
EVENTS = {
    "sent",
    "delivered",
    "delivery_delayed",
    "bounced",
    "failed",
    "complained",
    "opened",
    "clicked",
    "queued",
    "scheduled",
    "canceled",
    "suppressed",
}


@dataclass(frozen=True)
class MailEnvelope:
    sender: str
    recipient: str
    subject: str
    body: str
    key: str

    @property
    def content_hash(self) -> str:
        return digest([self.sender, self.recipient, self.subject, self.body])


@dataclass(frozen=True)
class MailResult:
    status: str  # accepted, rejected, unknown
    receipt_id: str | None = None
    event: str = ""


class MailProvider(Protocol):
    def verify_sender(self) -> bool: ...
    def send(self, envelope: MailEnvelope) -> MailResult: ...
    def reconcile(self, envelope: MailEnvelope, receipt_id: str | None) -> MailResult: ...


def configured(settings: Settings, owner: int, shop: int) -> bool:
    addresses_ready = bool(
        settings.outbound_enabled
        and owner > 0
        and shop > 0
        and settings.outbound_owner_id == owner
        and settings.outbound_shop_id == shop
        and ADDRESS.fullmatch(settings.outbound_sender)
        and ADDRESS.fullmatch(settings.outbound_test_recipient)
        and len(settings.outbound_sender) <= 254
        and len(settings.outbound_test_recipient) <= 254
    )
    if settings.outbound_provider == "qq_smtp":
        credential = settings.outbound_smtp_authorization_code
        secret = credential.get_secret_value() if credential else ""
        return bool(
            addresses_ready
            and settings.outbound_sender.lower().endswith("@qq.com")
            and secret
            and secret.isascii()
            and secret.isprintable()
            and secret == secret.strip()
        )
    return bool(
        addresses_ready
        and settings.outbound_api_key
        and settings.outbound_api_key.get_secret_value()
        and settings.outbound_domain_id
    )


def config_hash(settings: Settings) -> str:
    if settings.outbound_provider == "qq_smtp":
        credential = settings.outbound_smtp_authorization_code
        return digest(
            [
                "qq_smtp",
                settings.outbound_owner_id,
                settings.outbound_shop_id,
                settings.outbound_sender,
                settings.outbound_test_recipient,
                hashlib.sha256(
                    (credential.get_secret_value() if credential else "").encode()
                ).hexdigest(),
            ]
        )
    # Preserve existing Resend channel fingerprints when upgrading.
    secret = settings.outbound_api_key.get_secret_value() if settings.outbound_api_key else ""
    return digest(
        [
            settings.outbound_owner_id,
            settings.outbound_shop_id,
            settings.outbound_sender,
            settings.outbound_test_recipient,
            str(settings.outbound_domain_id),
            hashlib.sha256(secret.encode()).hexdigest(),
        ]
    )


class ResendMailProvider:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings, self.transport = settings, transport

    def _request(self, method: str, path: str, **kwargs: Any) -> tuple[int, dict[str, Any]]:
        secret = self.settings.outbound_api_key
        if not self.settings.outbound_enabled or secret is None:
            return 0, {}
        headers = {"Authorization": f"Bearer {secret.get_secret_value()}"}
        headers.update(kwargs.pop("headers", {}))
        started = monotonic()
        try:
            with (
                httpx.Client(
                    base_url="https://api.resend.com",
                    timeout=httpx.Timeout(15, connect=5),
                    trust_env=False,
                    follow_redirects=False,
                    transport=self.transport,
                ) as client,
                client.stream(method, path, headers=headers, **kwargs) as response,
            ):
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 300000 or monotonic() - started > 20:
                        return 0, {}
                value = json.loads(raw)
                return response.status_code, value if isinstance(value, dict) else {}
        except (httpx.HTTPError, ValueError):
            return 0, {}

    def verify_sender(self) -> bool:
        code, data = self._request("GET", f"/domains/{self.settings.outbound_domain_id}")
        capabilities = data.get("capabilities")
        return bool(
            code == 200
            and data.get("status") == "verified"
            and data.get("name") == self.settings.outbound_sender.rsplit("@", 1)[-1]
            and isinstance(capabilities, dict)
            and capabilities.get("sending") == "enabled"
        )

    def send(self, envelope: MailEnvelope) -> MailResult:
        code, data = self._request(
            "POST",
            "/emails",
            headers={"Idempotency-Key": envelope.key},
            json={
                "from": envelope.sender,
                "to": [envelope.recipient],
                "subject": envelope.subject,
                "text": envelope.body,
                "tags": [{"name": "soloops_dispatch", "value": envelope.key}],
            },
        )
        if code in {200, 201}:
            try:
                return MailResult("accepted", str(UUID(data["id"])), "submitted")
            except (ValueError, KeyError, TypeError, AttributeError):
                return MailResult("unknown")
        # Validation/auth errors precede acceptance. Ambiguous failures stay unknown.
        if code in {400, 401, 403, 422}:
            return MailResult("rejected")
        return MailResult("unknown")

    def _match(self, envelope: MailEnvelope, receipt: str) -> MailResult:
        try:
            receipt = str(UUID(receipt))
        except (ValueError, TypeError, AttributeError):
            return MailResult("unknown")
        code, data = self._request("GET", f"/emails/{receipt}")
        if (
            code != 200
            or data.get("id") != receipt
            or data.get("from") != envelope.sender
            or data.get("to") != [envelope.recipient]
            or data.get("subject") != envelope.subject
            or data.get("text") != envelope.body
            or data.get("cc")
            or data.get("bcc")
            or not isinstance(data.get("tags"), list)
            or {"name": "soloops_dispatch", "value": envelope.key} not in data["tags"]
        ):
            return MailResult("unknown")
        event = data.get("last_event")
        return MailResult(
            "accepted",
            receipt,
            event if isinstance(event, str) and event in EVENTS else "submitted",
        )

    def reconcile(self, envelope: MailEnvelope, receipt_id: str | None) -> MailResult:
        if receipt_id:
            return self._match(envelope, receipt_id)
        # Bounded discovery. Failure to find an item never establishes that it was not sent.
        code, data = self._request("GET", "/emails", params={"limit": 100})
        rows = data.get("data")
        if code != 200 or not isinstance(rows, list):
            return MailResult("unknown")
        candidates = [
            r
            for r in rows[:100]
            if isinstance(r, dict)
            and r.get("from") == envelope.sender
            and r.get("to") == [envelope.recipient]
            and r.get("subject") == envelope.subject
            and isinstance(r.get("id"), str)
        ]
        matches = [self._match(envelope, r["id"]) for r in candidates[:5]]
        confirmed = [m for m in matches if m.status == "accepted"]
        return confirmed[0] if len(confirmed) == 1 else MailResult("unknown")
