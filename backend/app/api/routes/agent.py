from fastapi import APIRouter

from app.api.dependencies import CurrentSession, SettingsDependency, UowDependency
from app.schemas.agent import AgentAction, AgentOutput, ModelStatus, SkillDefinition, StartAgent
from app.services.agent import AgentService
from app.services.agent_model import OpenAIResponsesModel

router = APIRouter(prefix="/shops/{shop_id}/agent", tags=["受控执行"])


@router.get("/skills")
def skills(
    shop_id: int, current: CurrentSession, uow: UowDependency, settings: SettingsDependency
) -> list[SkillDefinition]:
    service = AgentService(uow, OpenAIResponsesModel(settings))
    return service.catalog(current.user_id, shop_id)


@router.get("/model")
def model_status(
    shop_id: int, current: CurrentSession, uow: UowDependency, settings: SettingsDependency
) -> ModelStatus:
    service = AgentService(uow, OpenAIResponsesModel(settings))
    return service.model_status(current.user_id, shop_id)


@router.post("/runs")
def start(
    shop_id: int,
    data: StartAgent,
    current: CurrentSession,
    uow: UowDependency,
    settings: SettingsDependency,
) -> AgentOutput:
    return AgentService(uow, OpenAIResponsesModel(settings)).start(current.user_id, shop_id, data)


@router.get("/runs")
def runs(
    shop_id: int, current: CurrentSession, uow: UowDependency, settings: SettingsDependency
) -> list[AgentOutput]:
    return AgentService(uow, OpenAIResponsesModel(settings)).list(current.user_id, shop_id)


@router.get("/runs/{run_id}")
def get(
    shop_id: int,
    run_id: int,
    current: CurrentSession,
    uow: UowDependency,
    settings: SettingsDependency,
) -> AgentOutput:
    return AgentService(uow, OpenAIResponsesModel(settings)).get(current.user_id, shop_id, run_id)


@router.post("/runs/{run_id}")
def act(
    shop_id: int,
    run_id: int,
    data: AgentAction,
    current: CurrentSession,
    uow: UowDependency,
    settings: SettingsDependency,
) -> AgentOutput:
    return AgentService(uow, OpenAIResponsesModel(settings)).act(
        current.user_id, shop_id, run_id, data
    )
