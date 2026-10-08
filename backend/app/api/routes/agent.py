from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import CurrentSession, SettingsDependency, UowDependency
from app.schemas.agent import AgentAction, AgentOutput, ModelStatus, SkillDefinition, StartAgent
from app.services.agent import AgentService
from app.services.agent_model import DecisionModel, OpenAIResponsesModel

router = APIRouter(prefix="/shops/{shop_id}/agent", tags=["受控执行"])


def configured_model(settings: SettingsDependency) -> DecisionModel:
    return OpenAIResponsesModel(settings)


ModelDependency = Annotated[DecisionModel, Depends(configured_model)]


@router.get("/skills")
def skills(
    shop_id: int, current: CurrentSession, uow: UowDependency, model: ModelDependency
) -> list[SkillDefinition]:
    service = AgentService(uow, model)
    return service.catalog(current.user_id, shop_id)


@router.get("/model")
def model_status(
    shop_id: int, current: CurrentSession, uow: UowDependency, model: ModelDependency
) -> ModelStatus:
    service = AgentService(uow, model)
    return service.model_status(current.user_id, shop_id)


@router.post("/runs")
def start(
    shop_id: int,
    data: StartAgent,
    current: CurrentSession,
    uow: UowDependency,
    model: ModelDependency,
) -> AgentOutput:
    return AgentService(uow, model).start(current.user_id, shop_id, data)


@router.get("/runs")
def runs(
    shop_id: int, current: CurrentSession, uow: UowDependency, model: ModelDependency
) -> list[AgentOutput]:
    return AgentService(uow, model).list(current.user_id, shop_id)


@router.get("/runs/{run_id}")
def get(
    shop_id: int,
    run_id: int,
    current: CurrentSession,
    uow: UowDependency,
    model: ModelDependency,
) -> AgentOutput:
    return AgentService(uow, model).get(current.user_id, shop_id, run_id)


@router.post("/runs/{run_id}")
def act(
    shop_id: int,
    run_id: int,
    data: AgentAction,
    current: CurrentSession,
    uow: UowDependency,
    model: ModelDependency,
) -> AgentOutput:
    return AgentService(uow, model).act(current.user_id, shop_id, run_id, data)
