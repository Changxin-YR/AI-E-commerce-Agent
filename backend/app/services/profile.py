from app.core.errors import ConflictError, NotFoundError
from app.models.identity import SellerProfile, Shop
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import (
    OnboardingOutput,
    ProfileInput,
    ProfileOutput,
    ShopInput,
    ShopOutput,
)


class ProfileService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def get_profile(self, user_id: int) -> ProfileOutput | None:
        profile = self.uow.identity.get_profile(user_id)
        return ProfileOutput.model_validate(profile) if profile else None

    def save_profile(self, user_id: int, data: ProfileInput) -> ProfileOutput:
        # Serialize first-time creation as well as updates of an existing profile.
        self.uow.identity.lock_user(user_id)
        profile = self.uow.identity.get_profile(user_id, lock=True)
        values = data.model_dump(exclude={"version"})
        if profile is None:
            if data.version != 0:
                raise ConflictError("经营资料版本已变化，请刷新后重试")
            profile = SellerProfile(user_id=user_id, version=1, **values)
            self.uow.identity.add_profile(profile)
        else:
            if data.version != profile.version:
                raise ConflictError("经营资料已在其他页面更新，请刷新后重试")
            for field, value in values.items():
                setattr(profile, field, value)
            profile.version += 1
        self.uow.record_event(
            user_id, "profile.saved", "profile", user_id, {"version": profile.version}
        )
        self.uow.commit()
        return ProfileOutput.model_validate(profile)

    def list_shops(self, user_id: int) -> list[ShopOutput]:
        return [ShopOutput.model_validate(shop) for shop in self.uow.identity.list_shops(user_id)]

    def get_shop(self, user_id: int, shop_id: int) -> ShopOutput:
        shop = self.uow.identity.get_shop(user_id, shop_id)
        if shop is None:
            raise NotFoundError()
        return ShopOutput.model_validate(shop)

    def create_shop(self, user_id: int, data: ShopInput) -> ShopOutput:
        shop = Shop(owner_id=user_id, **data.model_dump())
        self.uow.identity.add_shop(shop)
        self.uow.record_event(user_id, "shop.created", "shop", shop.id)
        self.uow.commit()
        return ShopOutput.model_validate(shop)

    def onboarding(self, user_id: int) -> OnboardingOutput:
        has_profile = self.uow.identity.get_profile(user_id) is not None
        shop_count = self.uow.identity.count_shops(user_id)
        return OnboardingOutput(
            profile_complete=has_profile,
            shop_count=shop_count,
            next_step="profile" if not has_profile else "shop" if not shop_count else "import",
        )
