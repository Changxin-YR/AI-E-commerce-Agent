"""Acceptance harness cannot connect to a non-dedicated database or real providers."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from business_fixture import SyntheticMail, SyntheticModel, build_app  # noqa: E402

from app.services.outbound_provider import MailEnvelope  # noqa: E402


@pytest.mark.parametrize(
    "url",
    [
        "mysql+pymysql://synthetic:fake@127.0.0.1:3306/soloops_harmony_r2_test",
        "mysql+pymysql://synthetic:fake@localhost:3315/soloops_harmony_r2_test",
        "mysql+pymysql://synthetic:fake@127.0.0.1:3315/soloops",
        "mysql+pymysql://synthetic:fake@example.invalid:3315/soloops_harmony_r2_test",
    ],
)
def test_fixture_refuses_other_database_before_constructing_app(url):
    with (
        patch("business_fixture.dotenv_values", return_value={"SOLOOPS_TEST_DATABASE_URL": url}),
        patch("business_fixture.create_app") as create,
    ):
        with pytest.raises(RuntimeError, match="Refusing any database"):
            build_app()
        create.assert_not_called()


def test_synthetic_model_and_mail_need_no_external_transport():
    with (
        patch("business_fixture.time.sleep"),
        patch("business_fixture.journal") as events,
        patch("httpx.Client", side_effect=AssertionError("external transport forbidden")),
    ):
        model = SyntheticModel()
        assert model.status().provider == "test_double"
        assert model.decide("daily check", 5).engine == "test_double"
        reply = model.generate(
            {"name": "listing_composition", "payload": {"facts": {"fact_1": "500 mL"}}}, 5
        )
        assert reply.content["title_fact_ids"] == ["fact_1"]
        mail = SyntheticMail()
        envelope = MailEnvelope(
            "sender@example.invalid",
            "recipient@example.invalid",
            "Synthetic",
            "Synthetic body",
            "key",
        )
        result = mail.send(envelope)
        assert result.status == "accepted"
        assert mail.reconcile(envelope, result.receipt_id).event == "delivered"
        assert len(events.call_args_list) == 4
