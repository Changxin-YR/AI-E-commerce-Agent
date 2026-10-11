"""No-database regression for mobile product channel evidence and saved snapshots."""

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from app.schemas.listings import ProductFacts  # noqa: E402
from app.services.listings import product_facts  # noqa: E402


def test_current_product_exposes_channel_and_legacy_snapshot_remains_readable():
    product = SimpleNamespace(id=1, sku="SYN-CUP", name="Synthetic", facts="Capacity: 350 mL")
    row = SimpleNamespace(id=2, row_number=2)
    batch = SimpleNamespace(
        id=3,
        origin="file_import",
        filename="synthetic.csv",
        sheet_name="",
        exported_at=None,
        created_at=datetime(2026, 10, 11),
        data_identity="synthetic",
        source_channel="amazon",
    )
    result = product_facts((product, row, batch))
    assert result.source_channel == "amazon"
    assert result.source.data_identity == "synthetic"
    legacy = result.model_dump()
    legacy.pop("source_channel")
    restored = ProductFacts.model_validate(legacy)
    assert restored.source_channel is None
    assert restored.source.row_id == result.source.row_id
