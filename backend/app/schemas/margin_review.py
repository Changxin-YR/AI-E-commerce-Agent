from typing import Literal

from app.schemas.analytics import AnalysisInput, AnalysisResult
from app.schemas.common import InputModel, OutputModel
from app.schemas.listings import ListingContent, ProductFacts


class MarginInput(InputModel):
    analysis: AnalysisResult
    product_id: int | None = None


class MarginListing(OutputModel):
    product: ProductFacts
    active_id: int
    before: ListingContent
    missing_parameters: list[str]


class MarginRecommendation(OutputModel):
    kind: Literal["input", "cost", "pricing", "listing"]
    title: str
    evidence: str
    action: str
    risk: Literal["R0", "R1"]


class MarginEvidence(OutputModel):
    scope: AnalysisInput
    source_revision: int
    included_lines: int
    ranking_available: bool
    candidate_count: int
    candidates: list[str]
    candidate_limit: int = 20
    cost_basis: str
    fee_gaps: list[str]
    data_gaps: list[str]
    recommendations: list[MarginRecommendation]
    save_analysis: bool
    listing: MarginListing | None
    listing_note: str
