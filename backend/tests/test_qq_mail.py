"""QQ adapter and approval tests use synthetic credentials and no external network."""

import smtplib
import ssl
from email import policy
from email.parser import BytesParser
from unittest.mock import patch
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.api.routes.outbound import get_provider
from app.core.config import Settings
from app.services.outbound_provider import MailEnvelope, MailResult, config_hash, configured
from app.services.qq_mail_provider import QQMailProvider, smtp_message_id
from tests.test_outbound import approve, dispatch, prepare, root
from tests.test_outbound import mailbox as mailbox  # register shared synthetic fixture


@pytest.fixture()
def qq_settings():
    return Settings(
        _env_file=None,
        database_url="mysql+pymysql://synthetic:synthetic@localhost/synthetic_test",
        outbound_enabled=True,
        outbound_provider="qq_smtp",
        outbound_sender="synthetic-owner@qq.com",
        outbound_test_recipient="synthetic-owner@qq.com",
        outbound_owner_id=1,
        outbound_shop_id=1,
        outbound_smtp_authorization_code=SecretStr("synthetic-authorization-code"),
    )


class SMTPDouble(smtplib.SMTP):
    """Run stdlib send_message/sendmail, replacing only the socket-level commands."""

    def __init__(self):
        self.does_esmtp = False
        self.sent = []
        self.logins = []
        self.recipients = []
        self.sender = None
        self.closed = False
        self.login_error = None
        self.data_error = None
        self.quit_error = None
        self.data_code = 250
        self.rcpt_code = 250

    def ehlo_or_helo_if_needed(self):
        pass

    def login(self, user, password, **kwargs):
        self.logins.append((user, password))
        if self.login_error:
            raise self.login_error
        return 235, b"authenticated"

    def mail(self, sender, options=()):
        self.sender = sender
        return 250, b"ok"

    def rcpt(self, recipient, options=()):
        self.recipients.append(recipient)
        return self.rcpt_code, b"recipient result"

    def data(self, msg):
        self.sent.append(msg)
        if self.data_error:
            raise self.data_error
        return self.data_code, b"data result"

    def _rset(self):
        pass

    def quit(self):
        if self.quit_error:
            raise self.quit_error
        return 221, b"bye"

    def close(self):
        self.closed = True


@pytest.fixture()
def envelope(qq_settings):
    return MailEnvelope(
        qq_settings.outbound_sender,
        "synthetic-recipient@example.com",
        "经营摘要 · 合成测试",
        "第一行\n第二行\n.正文事实",
        str(uuid4()),
    )


def test_qq_uses_verified_ssl_login_and_exact_mime(qq_settings, envelope):
    check, send = SMTPDouble(), SMTPDouble()
    with patch("app.services.qq_mail_provider.smtplib.SMTP_SSL", side_effect=[check, send]) as ctor:
        provider = get_provider(qq_settings)
        assert isinstance(provider, QQMailProvider)
        assert provider.verify_sender()
        result = provider.send(envelope)
    assert result == MailResult("accepted", envelope.key, "smtp_accepted")
    assert not check.sent and len(send.sent) == 1
    for call in ctor.call_args_list:
        assert call.args == ("smtp.qq.com", 465)
        assert call.kwargs["timeout"] == 15
        context = call.kwargs["context"]
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert send.logins == [(envelope.sender, "synthetic-authorization-code")]
    assert send.sender == envelope.sender and send.recipients == [envelope.recipient]
    parsed = BytesParser(policy=policy.default).parsebytes(send.sent[0])
    assert str(parsed["From"]) == envelope.sender
    assert str(parsed["To"]) == envelope.recipient
    assert str(parsed["Subject"]) == envelope.subject
    assert parsed["Message-ID"] == smtp_message_id(envelope.key)
    assert parsed.get_content().replace("\r\n", "\n").rstrip("\n") == envelope.body
    assert not parsed["Cc"] and not parsed["Bcc"] and not parsed.is_multipart()
    assert check.closed and send.closed


@pytest.mark.parametrize(
    "failure,expected",
    [
        ("authentication", "rejected"),
        ("recipient", "rejected"),
        ("data_refused", "rejected"),
        ("data_timeout", "unknown"),
        ("data_disconnect", "unknown"),
        ("quit_refused", "accepted"),
        ("quit_timeout", "accepted"),
    ],
)
def test_smtp_boundary_failures_never_retry_or_downgrade_acceptance(
    qq_settings, envelope, failure, expected
):
    smtp = SMTPDouble()
    if failure == "authentication":
        smtp.login_error = smtplib.SMTPAuthenticationError(535, b"synthetic secret omitted")
    elif failure == "recipient":
        smtp.rcpt_code = 550
    elif failure == "data_refused":
        smtp.data_code = 554
    elif failure == "data_timeout":
        smtp.data_error = TimeoutError()
    elif failure == "data_disconnect":
        smtp.data_error = smtplib.SMTPServerDisconnected()
    elif failure == "quit_refused":
        smtp.quit_error = smtplib.SMTPResponseException(500, b"quit error")
    else:
        smtp.quit_error = TimeoutError()
    with patch("app.services.qq_mail_provider.smtplib.SMTP_SSL", return_value=smtp) as ctor:
        result = QQMailProvider(qq_settings).send(envelope)
    assert result.status == expected
    assert bool(result.receipt_id) == (expected == "accepted")
    assert len(smtp.sent) <= 1 and ctor.call_count == 1 and smtp.closed


@pytest.mark.parametrize(
    "changed",
    [
        {"outbound_enabled": False},
        {"outbound_smtp_authorization_code": None},
        {"outbound_smtp_authorization_code": SecretStr("错误的授权码")},
        {"outbound_smtp_authorization_code": SecretStr("synthetic\ncode")},
        {"outbound_sender": "synthetic@gmail.com"},
        {"outbound_sender": "x@qq.com\r\nBcc:x@y.com"},
        {"outbound_owner_id": None},
        {"outbound_shop_id": None},
    ],
)
def test_incomplete_qq_config_never_connects(qq_settings, envelope, changed):
    settings = qq_settings.model_copy(update=changed)
    with patch("app.services.qq_mail_provider.smtplib.SMTP_SSL") as ctor:
        provider = QQMailProvider(settings)
        assert not provider.verify_sender()
        assert provider.send(envelope).status == "rejected"
        ctor.assert_not_called()


@pytest.mark.parametrize(
    "recipient", ["bad", "a@b.com,b@c.com", "x@qq.com\nBcc: x@y.com", "Name <x@y.com>"]
)
def test_invalid_recipient_never_reaches_smtp(qq_settings, envelope, recipient):
    with patch("app.services.qq_mail_provider.smtplib.SMTP_SSL") as ctor:
        result = QQMailProvider(qq_settings).send(
            MailEnvelope(envelope.sender, recipient, envelope.subject, envelope.body, envelope.key)
        )
        assert result.status == "rejected"
        ctor.assert_not_called()


def test_qq_authentication_failure_is_safe_and_query_does_not_invent_delivery(
    qq_settings, envelope
):
    with patch(
        "app.services.qq_mail_provider.smtplib.SMTP_SSL", side_effect=ssl.SSLError()
    ) as ctor:
        provider = QQMailProvider(qq_settings)
        assert not provider.verify_sender()
        assert provider.send(envelope).status == "rejected"
        assert ctor.call_count == 2
        assert provider.reconcile(envelope, envelope.key) == MailResult("unknown")
        assert ctor.call_count == 2


def test_provider_rotation_and_owner_scope_invalidate_config(qq_settings):
    assert configured(qq_settings, 1, 1)
    assert not configured(qq_settings, 2, 1) and not configured(qq_settings, 1, 2)
    assert config_hash(qq_settings) != config_hash(
        qq_settings.model_copy(
            update={"outbound_smtp_authorization_code": SecretStr("rotated-synthetic")}
        )
    )
    assert config_hash(qq_settings) != config_hash(
        qq_settings.model_copy(update={"outbound_provider": "resend"})
    )


def use_qq(config):
    config.outbound_provider = "qq_smtp"
    config.outbound_sender = "synthetic-owner@qq.com"
    config.outbound_test_recipient = "synthetic-owner@qq.com"
    config.outbound_smtp_authorization_code = SecretStr("synthetic-code")


@pytest.mark.parametrize("status", ["accepted", "unknown"])
def test_qq_recipient_approval_receipt_and_replay(logged_in, mailbox, status):
    shop, fake, config = mailbox
    use_qq(config)
    own = prepare(logged_in, shop, fake)
    assert own["provider"] == "qq_smtp" and own["recipient"] == config.outbound_test_recipient
    response = logged_in.post(
        root(shop) + "/messages",
        json={"run_id": own["run_id"], "recipient": "synthetic-other@example.net"},
    )
    assert response.status_code == 200
    mail = response.json()
    assert mail["id"] != own["id"] and mail["content_hash"] != own["content_hash"]
    assert mail["recipient"] == "synthetic-other@example.net"
    assert "发往本人测试邮箱" not in mail["body"]
    base = root(shop) + f"/messages/{mail['id']}"
    own_approved = approve(logged_in, own)
    assert (
        logged_in.post(
            base + "/send",
            json={"version": mail["version"], "approval_id": own_approved["approvals"][0]["id"]},
        ).status_code
        == 409
    )
    approved = approve(logged_in, mail)
    fake.result = MailResult(
        status,
        str(uuid4()) if status == "accepted" else None,
        "smtp_accepted" if status == "accepted" else "",
    )
    sent = dispatch(logged_in, approved).json()
    assert sent["status"] == status and sent["smtp_message_id"]
    assert fake.sent[-1].recipient == mail["recipient"]
    assert dispatch(logged_in, approved).json()["status"] == status
    assert len(fake.sent) == 2
    assert logged_in.post(base + "/reconcile", json={}).status_code == 409
    receipt = logged_in.post(
        base + "/receipt",
        json={"confirmed": True, "evidence": "合成收件人确认时间与邮件标识 synthetic-qq"},
    ).json()
    assert receipt["received_at"] and receipt["status"] == status
    assert receipt["receipt_id"] == sent["receipt_id"]
    assert logged_in.get(base).json()["recipient"] == mail["recipient"]


def test_qq_secret_rotation_blocks_prior_approval_and_history_keeps_provider(logged_in, mailbox):
    shop, fake, config = mailbox
    use_qq(config)
    mail = approve(logged_in, prepare(logged_in, shop, fake))
    config.outbound_smtp_authorization_code = SecretStr("rotated-synthetic-code")
    assert dispatch(logged_in, mail).status_code == 409
    config.outbound_provider = "resend"
    assert logged_in.get(root(shop) + f"/messages/{mail['id']}").json()["provider"] == "qq_smtp"
    assert len(fake.sent) == 1


def test_new_verification_previews_current_addresses_after_config_change(logged_in, mailbox):
    shop, fake, config = mailbox
    old_mail = prepare(logged_in, shop, fake)
    use_qq(config)
    current = logged_in.get(root(shop) + "/channel").json()
    assert current["status"] == "configuration_changed"
    assert current["provider"] == "qq_smtp"
    assert current["sender"] == config.outbound_sender
    assert current["recipient"] == config.outbound_test_recipient
    assert current["verified_at"] is None and current["receipt_id"] is None
    history = logged_in.get(root(shop) + f"/messages/{old_mail['id']}").json()
    assert history["provider"] == "resend" and history["recipient"] == "test@example.net"
    assert len(fake.sent) == 1


@pytest.mark.parametrize("recipient", ["a@b.com,b@c.com", "x@y.com\n", "Name <x@y.com>", ""])
def test_recipient_input_rejects_lists_headers_and_blank(logged_in, mailbox, recipient):
    shop, _, config = mailbox
    use_qq(config)
    assert (
        logged_in.post(
            root(shop) + "/messages", json={"run_id": 1, "recipient": recipient}
        ).status_code
        == 422
    )
