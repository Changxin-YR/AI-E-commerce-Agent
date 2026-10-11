"""Loopback-only R2 acceptance API with synthetic model/mail providers.

Uses only the dedicated 3315 test database. Production Settings/environment files
are never loaded; no real model or mail transport is constructed.
"""

from __future__ import annotations

# ruff: noqa: E402 -- Direct CLI bootstraps the backend source path.
import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import uvicorn
from dotenv import dotenv_values
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from foundation_samples import samples
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.api.dependencies import get_settings
from app.api.routes.agent import configured_model
from app.api.routes.outbound import get_provider
from app.core.config import Settings
from app.main import create_app
from app.models.identity import User
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import ModelDecision, ModelStatus
from app.schemas.identity import AccountInput
from app.services.agent_model import GenerationReply, ModelReply
from app.services.auth import AuthService
from app.services.outbound_provider import MailEnvelope, MailResult

LOCAL = ROOT / ".local/mobile-business"
USERNAME = "harmony_r2"
PASSWORD = "Synthetic-R2-2026!"


def journal(kind: str, data: dict[str, Any]) -> None:
    with (LOCAL / "fixture-events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {"at": datetime.now(UTC).isoformat(), "kind": kind, **data},
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )


class SyntheticModel:
    def status(self) -> ModelStatus:
        return ModelStatus(
            status="configured",
            provider="test_double",
            model="synthetic-r2-local",
            reason="",
            cost_note="合成计费用于预算验证，无真实模型请求",
        )

    def reserve(self, goal: str) -> Decimal:
        return Decimal("0.01")

    def reserve_generation(self, request: dict[str, Any]) -> Decimal:
        return Decimal("0.01")

    def decide(self, goal: str, timeout: float) -> ModelReply:
        time.sleep(2)
        intent = (
            "analysis"
            if any(word in goal.lower() for word in ["profit", "analysis", "利润", "分析"])
            else "daily"
        )
        journal("model_decide", {"intent": intent})
        return ModelReply(ModelDecision(intent=intent), Decimal("0.001"), 100, 30, "test_double")

    def generate(self, request: dict[str, Any], timeout: float) -> GenerationReply:
        time.sleep(2)
        name, payload = request["name"], request["payload"]
        if name == "listing_composition":
            keys = list(payload["facts"])
            value = {
                "title_fact_ids": keys[:1],
                "description_fact_ids": keys[::-1],
                "next_action": "offer_draft",
            }
        elif name == "support_composition":
            value = {
                "intent_ids": payload["local_intents"],
                "fact_ids": list(payload["facts"])[::-1],
                "policy_ids": list(payload["policies"]),
                "next_action": "offer_draft",
            }
        elif name == "analysis_question":
            value = {"intent": "low_margin"}
        elif name == "analysis_evidence":
            value = {
                "fact_ids": list(payload["facts"])[:8],
                "check_ids": ["fees", "cost_basis"],
                "next_action": "offer_todo",
            }
        elif name == "operation_evidence":
            value = {"branch_ids": list(payload["branches"]), "check_ids": list(payload["checks"])}
        else:
            raise ValueError(f"Unsupported synthetic generation: {name}")
        journal("model_generate", {"name": name})
        return GenerationReply(value, Decimal("0.001"), 100, 30, "test_double")


class SyntheticMail:
    def verify_sender(self) -> bool:
        return True

    def send(self, envelope: MailEnvelope) -> MailResult:
        journal("mail_captured", asdict(envelope))
        return MailResult("accepted", str(uuid5(NAMESPACE_URL, str(envelope))), "submitted")

    def reconcile(self, envelope: MailEnvelope, receipt_id: str | None) -> MailResult:
        journal("mail_reconciled", {"receipt_id": receipt_id})
        return MailResult("accepted", receipt_id, "delivered")


def build_app():
    values = dotenv_values(LOCAL / "test.env")
    raw = values.get("SOLOOPS_TEST_DATABASE_URL") or values.get("SOLOOPS_DATABASE_URL")
    if not raw:
        raise RuntimeError("Missing dedicated test database configuration")
    url = make_url(raw)
    if (url.host, url.port, url.database) != ("127.0.0.1", 3315, "soloops_harmony_r2_test"):
        raise RuntimeError("Refusing any database except dedicated R2 acceptance database")
    settings = Settings(
        _env_file=None,
        database_url=raw,
        scheduler_enabled=False,
        model_enabled=False,
        model_api_key=None,
        model_name="",
        model_provider="openai_responses",
        model_input_usd_per_million=None,
        model_output_usd_per_million=None,
        outbound_enabled=False,
        outbound_api_key=None,
        outbound_smtp_authorization_code=None,
        trusted_hosts=["127.0.0.1", "localhost"],
        trusted_origins=["http://127.0.0.1:18080"],
    )
    app = create_app(settings)

    @app.get("/__samples/{filename}", include_in_schema=False)
    def download_sample(filename: str):
        target = LOCAL / "samples" / filename
        if Path(filename).name != filename or not target.is_file():
            raise HTTPException(404)
        return FileResponse(target, filename=filename, media_type="application/octet-stream")

    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == USERNAME))
        if user is None:
            AuthService(UnitOfWork(session), settings).create_account(
                AccountInput(username=USERNAME, password=PASSWORD)
            )
            user = session.scalar(select(User).where(User.username == USERNAME))
        assert user is not None
        owner_id = user.id
    model, mail = SyntheticModel(), SyntheticMail()
    app.dependency_overrides[configured_model] = lambda: model
    app.dependency_overrides[get_provider] = lambda: mail

    def fixture_settings(request: Request) -> Settings:
        if "/outbound" not in request.url.path:
            return settings
        return settings.model_copy(
            update={
                "outbound_enabled": True,
                "outbound_api_key": SecretStr("synthetic-not-a-real-key"),
                "outbound_owner_id": owner_id,
                "outbound_shop_id": int(request.path_params["shop_id"]),
                "outbound_sender": "sender@example.invalid",
                "outbound_test_recipient": "recipient@example.invalid",
                "outbound_domain_id": uuid5(NAMESPACE_URL, "soloops-r2-local"),
            }
        )

    app.dependency_overrides[get_settings] = fixture_settings
    return app


def prepare_samples() -> None:
    import csv
    import io

    from openpyxl import Workbook

    target = LOCAL / "samples"
    target.mkdir(parents=True, exist_ok=True)
    data = samples(datetime.now(UTC))
    for item in data["files"]:
        (target / item["filename"]).write_text(item["text"], encoding="utf-8", newline="")
    wb = Workbook()
    for row in csv.reader(io.StringIO(data["files"][0]["text"])):
        wb.active.append(row)
    wb.save(target / "products-synthetic.xlsx")
    (target / "products-correction.csv").write_text(
        "sku,name,facts,price,currency\nSYN-FIX,,Capacity 500 mL,25,USD\n", encoding="utf-8"
    )
    (LOCAL / "fixture-samples.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18080)
    options = parser.parse_args()
    prepare_samples()
    application = build_app()
    journal(
        "started",
        {
            "port": options.port,
            "database": "soloops_harmony_r2_test",
            "real_model_calls": 0,
            "real_mail_calls": 0,
        },
    )
    uvicorn.run(application, host="127.0.0.1", port=options.port, access_log=True)
