from fastapi import APIRouter

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.identity import (
    OnboardingOutput,
    ProfileInput,
    ProfileOutput,
    ShopInput,
    ShopOutput,
)
from app.services.profile import ProfileService

router = APIRouter(tags=["经营资料"])


@router.get("/profile", response_model=ProfileOutput | None)
def get_profile(current: CurrentSession, uow: UowDependency) -> ProfileOutput | None:
    return ProfileService(uow).get_profile(current.user_id)


@router.put("/profile", response_model=ProfileOutput)
def save_profile(data: ProfileInput, current: CurrentSession, uow: UowDependency) -> ProfileOutput:
    return ProfileService(uow).save_profile(current.user_id, data)


@router.get("/onboarding", response_model=OnboardingOutput)
def onboarding(current: CurrentSession, uow: UowDependency) -> OnboardingOutput:
    return ProfileService(uow).onboarding(current.user_id)


@router.get("/shops", response_model=list[ShopOutput])
def list_shops(current: CurrentSession, uow: UowDependency) -> list[ShopOutput]:
    return ProfileService(uow).list_shops(current.user_id)


@router.post("/shops", response_model=ShopOutput, status_code=201)
def create_shop(data: ShopInput, current: CurrentSession, uow: UowDependency) -> ShopOutput:
    return ProfileService(uow).create_shop(current.user_id, data)


@router.get("/shops/{shop_id}", response_model=ShopOutput)
def get_shop(shop_id: int, current: CurrentSession, uow: UowDependency) -> ShopOutput:
    return ProfileService(uow).get_shop(current.user_id, shop_id)
