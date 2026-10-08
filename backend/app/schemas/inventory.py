from typing import Annotated, Literal

from pydantic import Field

from app.schemas.analytics import SourceReference
from app.schemas.common import InputModel, OutputModel
from app.schemas.imports import DataIdentity, SourceChannel


class InventoryQuery(InputModel):
    data_identity: DataIdentity = "user_import"
    channel: SourceChannel = "generic"
    max_age_hours: Annotated[int, Field(ge=1, le=720)] = 24
    search: Annotated[str, Field(max_length=120)] = ""
    offset: Annotated[int, Field(ge=0, le=1000000)] = 0


class InventoryItem(OutputModel):
    id: int
    sku: str
    channel: str
    available: int
    safety_threshold: int
    snapshot_at: str
    valid_until: str
    status: Literal["low", "above_threshold", "unknown"]
    reason: str
    source: SourceReference


class InventoryOutput(OutputModel):
    shop_id: int
    source_revision: int
    checked_at: str
    scope: InventoryQuery
    items: list[InventoryItem]
    has_more: bool
    note: str = "数量仅为该渠道的历史快照；未列出的 SKU 库存未知。跨渠道可能共享库存，不合计。"
