"""QQ SMTP over verified TLS. Each invocation attempts at most one SMTP DATA."""

import smtplib
import ssl
from contextlib import suppress
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime
from uuid import UUID

from app.core.config import Settings
from app.core.time import utc_now
from app.services.outbound_provider import ADDRESS, MailEnvelope, MailResult, configured


def smtp_message_id(key: str) -> str:
    return f"<soloops-{UUID(key)}@qq.com>"


class QQMailProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _ready(self) -> bool:
        return self.settings.outbound_provider == "qq_smtp" and configured(
            self.settings, self.settings.outbound_owner_id or 0, self.settings.outbound_shop_id or 0
        )

    def _connect(self) -> smtplib.SMTP_SSL:
        return smtplib.SMTP_SSL(
            "smtp.qq.com",
            465,
            timeout=15,
            context=ssl.create_default_context(),
            local_hostname="[127.0.0.1]",
        )

    def _login(self, client: smtplib.SMTP_SSL) -> None:
        secret = self.settings.outbound_smtp_authorization_code
        assert secret is not None
        client.login(self.settings.outbound_sender, secret.get_secret_value())

    @staticmethod
    def _close(client: smtplib.SMTP_SSL | None) -> None:
        if client is not None:
            # A QUIT failure must not overwrite an already received DATA 250 response.
            with suppress(OSError):
                client.quit()
            with suppress(OSError):
                client.close()

    def verify_sender(self) -> bool:
        if not self._ready():
            return False
        client = None
        try:
            client = self._connect()
            self._login(client)
            return True
        except OSError:
            return False
        finally:
            self._close(client)

    def send(self, envelope: MailEnvelope) -> MailResult:
        if (
            not self._ready()
            or envelope.sender != self.settings.outbound_sender
            or not ADDRESS.fullmatch(envelope.recipient)
            or len(envelope.recipient) > 254
        ):
            return MailResult("rejected")
        try:
            message = EmailMessage(policy=policy.SMTP)
            message["From"] = envelope.sender
            message["To"] = envelope.recipient
            message["Subject"] = envelope.subject
            message["Date"] = format_datetime(utc_now())
            message["Message-ID"] = smtp_message_id(envelope.key)
            message.set_content(envelope.body, charset="utf-8", cte="base64")
        except (ValueError, TypeError):
            return MailResult("rejected")
        client = None
        attempted = False
        try:
            client = self._connect()
            self._login(client)
            attempted = True
            # smtplib returns only after the final DATA response is 250; one recipient only.
            refused = client.send_message(
                message, from_addr=envelope.sender, to_addrs=[envelope.recipient]
            )
            return (
                MailResult("rejected")
                if refused
                else MailResult("accepted", str(UUID(envelope.key)), "smtp_accepted")
            )
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused):
            return MailResult("rejected")
        except smtplib.SMTPResponseException as exc:
            return MailResult("rejected" if 400 <= exc.smtp_code < 600 else "unknown")
        except OSError:
            return MailResult("unknown" if attempted else "rejected")
        finally:
            self._close(client)

    def reconcile(self, envelope: MailEnvelope, receipt_id: str | None) -> MailResult:
        # SMTP has no receipt query. A local Message-ID does not establish delivery.
        return MailResult("unknown")
