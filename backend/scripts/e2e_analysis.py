"""Scoped synthetic model for the isolated browser launcher; no production registration."""

from decimal import Decimal
from typing import Any

from fastapi import FastAPI

from app.api.dependencies import CurrentSession, UowDependency
from app.api.routes.agent import configured_model
from app.core.config import Settings
from app.core.errors import BusinessError
from app.schemas.agent import ModelStatus
from app.services.agent_model import GenerationReply, ModelReply, OpenAIResponsesModel


class BrowserAnalysis(OpenAIResponsesModel):
    def status(self) -> ModelStatus:
        return ModelStatus(
            status="configured",
            provider="test_double",
            model="synthetic-evidence-model",
            reason="",
            input_usd_per_million=Decimal(1),
            output_usd_per_million=Decimal(2),
        )

    def reserve_generation(self, request: dict[str, Any]) -> Decimal:
        return Decimal("0.01")

    def generate(self, request: dict[str, Any], timeout: float) -> GenerationReply:
        value = (
            {"intent": "low_margin"}
            if request["name"] == "analysis_question"
            else {
                "fact_ids": list(request["payload"]["facts"])[:8],
                "check_ids": ["fees", "cost_basis"],
                "next_action": "offer_todo",
            }
        )
        return GenerationReply(value, Decimal("0.001"), 100, 30, "test_double")

    def decide(self, goal: str, timeout: float) -> ModelReply:
        raise BusinessError("not_configured", "合成模型仅用于问数测试", 422)


def configure(app: FastAPI, settings: Settings) -> None:
    disabled = settings.model_copy(update={"model_enabled": False, "model_api_key": None})

    def model(shop_id: int, current: CurrentSession, uow: UowDependency) -> OpenAIResponsesModel:
        shop = uow.identity.get_shop(current.user_id, shop_id)
        if shop and shop.code.startswith("question-e2e-"):
            return BrowserAnalysis(disabled)
        return OpenAIResponsesModel(disabled)

    app.dependency_overrides[configured_model] = model
