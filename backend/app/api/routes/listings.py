from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.listings import (
    DecisionInput,
    GenerateInput,
    ListingOutput,
    ProductFacts,
    ProductWorkspace,
    ReviseInput,
)
from app.services.listing_generation import ListingGenerator, get_listing_generator
from app.services.listings import ListingService

router = APIRouter(prefix="/shops/{shop_id}/listings", tags=["Listing 草稿与审批"])
GeneratorDependency = Annotated[ListingGenerator, Depends(get_listing_generator)]


@router.get("/products")
def products(
    shop_id: int,
    current: CurrentSession,
    uow: UowDependency,
    q: Annotated[str, Query(max_length=120)] = "",
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> list[ProductFacts]:
    return ListingService(uow).products(current.user_id, shop_id, q, offset)


@router.get("/products/{product_id}")
def workspace(
    shop_id: int, product_id: int, current: CurrentSession, uow: UowDependency
) -> ProductWorkspace:
    return ListingService(uow).workspace(current.user_id, shop_id, product_id)


@router.get("/versions")
def history(shop_id: int, current: CurrentSession, uow: UowDependency) -> list[ListingOutput]:
    return ListingService(uow).history(current.user_id, shop_id)


@router.get("/versions/{listing_id}")
def get(
    shop_id: int, listing_id: int, current: CurrentSession, uow: UowDependency
) -> ListingOutput:
    return ListingService(uow).get(current.user_id, shop_id, listing_id)


@router.post("/generate", status_code=201)
def generate(
    shop_id: int,
    data: GenerateInput,
    current: CurrentSession,
    uow: UowDependency,
    generator: GeneratorDependency,
) -> ListingOutput:
    return ListingService(uow).generate(current.user_id, shop_id, data, generator)


@router.post("/versions/{listing_id}/revise", status_code=201)
def revise(
    shop_id: int, listing_id: int, data: ReviseInput, current: CurrentSession, uow: UowDependency
) -> ListingOutput:
    return ListingService(uow).revise(current.user_id, shop_id, listing_id, data)


@router.post("/versions/{listing_id}/decision")
def decide(
    shop_id: int, listing_id: int, data: DecisionInput, current: CurrentSession, uow: UowDependency
) -> ListingOutput:
    return ListingService(uow).decide(current.user_id, shop_id, listing_id, data)
