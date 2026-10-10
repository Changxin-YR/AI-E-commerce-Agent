import csv
import hashlib
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import BusinessError
from app.core.time import utc_now
from app.models.imports import ImportBatch, OrderLine
from app.services.import_parser import MAX_BYTES, parse_file
from app.services.import_split import split_csv
from app.services.imports import ImportService
from tests.test_analytics import SCOPE, calculate
from tests.test_imports import ORDER_HEADER, commit, create_shop, preview, upload


def csv_line(index: int, *, quantity: int = 1, status: str = "paid") -> str:
    order, line = ("CROSS", index - 1998) if index >= 1999 else (f"O{index}", 1)
    return f"{order},{line},S{index % 2},{quantity},2,USD,2026-10-07T00:00:00Z,{status},0,0\n"


def group_data(contents: list[bytes]) -> dict[str, Any]:
    return {
        "options": {
            "filename": "synthetic.csv",
            "kind": "orders",
            "source_channel": "generic",
            "data_identity": "synthetic",
            "timezone": "Asia/Shanghai",
        },
        "manifest": {
            "format": "soloops-split-v1",
            "source_filename": "synthetic.csv",
            "source_sha256": hashlib.sha256(b"".join(contents)).hexdigest(),
            "total_rows": sum(len(parse_file("part.csv", data)[1]) for data in contents),
            "parts": [
                {
                    "filename": f"part-{i + 1:03d}.csv",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "rows": len(parse_file("part.csv", data)[1]),
                    "bytes": len(data),
                }
                for i, data in enumerate(contents)
            ],
        },
    }


def create_group(client: TestClient, shop: int, data: dict[str, Any]) -> dict[str, Any]:
    result = client.post(f"/api/shops/{shop}/import-groups", json=data)
    assert result.status_code == 201, result.text
    return result.json()


def part_upload(
    client: TestClient, group: dict[str, Any], part: int, data: bytes
) -> dict[str, Any]:
    result = client.post(
        f"/api/shops/{group['shop_id']}/imports",
        params={
            **{k: v for k, v in group["options"].items() if v is not None},
            "filename": group["manifest"]["parts"][part - 1]["filename"],
            "group_id": group["id"],
            "group_part": part,
        },
        content=data,
    )
    assert result.status_code == 201, result.text
    return result.json()


def read_group(client: TestClient, group: dict[str, Any]) -> dict[str, Any]:
    result = client.get(f"/api/import-groups/{group['id']}")
    assert result.status_code == 200
    return result.json()


def test_large_group_reconcile_retry_correct_revoke_and_restore(
    logged_in: TestClient, tmp_path: Path, session_factory: sessionmaker[Session]
) -> None:
    source = tmp_path / "synthetic.csv"
    source.write_text(
        ORDER_HEADER
        + "".join(csv_line(i, status="cancelled" if i == 1 else "paid") for i in range(2000))
        + csv_line(2000, quantity=0)
        + csv_line(0),
        encoding="utf-8",
    )
    manifest = split_csv(source, tmp_path / "parts")
    assert [part.rows for part in manifest.parts] == [2000, 2]
    contents = [(tmp_path / "parts" / part.filename).read_bytes() for part in manifest.parts]
    shop = create_shop(logged_in)
    data = group_data(contents)
    data["manifest"] = manifest.model_dump()
    group = create_group(logged_in, shop, data)
    assert create_group(logged_in, shop, data)["id"] == group["id"]
    blocked = logged_in.post(f"/api/shops/{shop}/analytics/calculate", json=SCOPE)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "partial_coverage"
    first = commit(logged_in, preview(logged_in, part_upload(logged_in, group, 1, contents[0])))
    assert read_group(logged_in, group)["committed_rows"] == 2000
    assert logged_in.post(f"/api/shops/{shop}/analytics/calculate", json=SCOPE).status_code == 409
    second = preview(logged_in, part_upload(logged_in, group, 2, contents[1]))
    assert second["error_rows"] == 1
    assert (
        logged_in.post(
            f"/api/imports/{second['id']}/commit", json={"version": second["version"]}
        ).status_code
        == 409
    )
    assert part_upload(logged_in, group, 2, contents[1])["id"] == second["id"]
    second = commit(logged_in, preview(logged_in, second, corrections={"2": {"quantity": "1"}}))
    assert part_upload(logged_in, group, 2, contents[1])["id"] == second["id"]
    complete = read_group(logged_in, group)
    assert complete["complete"] and complete["committed_rows"] == 2002
    assert complete["unique_rows"] == 2001 and complete["overlap_rows"] == 1
    result = calculate(logged_in, shop)
    assert Decimal(result["summary"]["sales"]) == Decimal(4000)
    with session_factory() as session:
        assert len(session.scalars(select(OrderLine)).all()) == 2001
        assert (
            len(session.scalars(select(OrderLine).where(OrderLine.order_id == "CROSS")).all()) == 2
        )
    # A single-part rollback makes coverage incomplete; retry creates only that slot's new batch.
    assert (
        logged_in.post(
            f"/api/imports/{first['id']}/revoke", json={"version": first["version"]}
        ).status_code
        == 200
    )
    assert not read_group(logged_in, group)["complete"]
    assert logged_in.post(f"/api/shops/{shop}/analytics/calculate", json=SCOPE).status_code == 409
    recovered = commit(logged_in, preview(logged_in, part_upload(logged_in, group, 1, contents[0])))
    assert recovered["id"] != first["id"] and read_group(logged_in, group)["complete"]
    # Later independent data survives the entire group's rollback.
    external = ORDER_HEADER + csv_line(0).replace(",2,USD", ",3,USD")
    commit(
        logged_in,
        preview(logged_in, upload(logged_in, shop, external, "orders")),
        allow_updates=True,
    )
    complete = read_group(logged_in, group)
    assert (
        logged_in.post(
            f"/api/import-groups/{group['id']}/revoke", json={"version": group["version"]}
        ).status_code
        == 409
    )
    revoked = logged_in.post(
        f"/api/import-groups/{group['id']}/revoke", json={"version": complete["version"]}
    )
    assert revoked.status_code == 200 and revoked.json()["status"] == "revoked"
    assert Decimal(calculate(logged_in, shop)["summary"]["sales"]) == Decimal(3)
    assert (
        logged_in.post(
            f"/api/import-groups/{group['id']}/revoke", json={"version": complete["version"]}
        ).status_code
        == 200
    )


def test_group_conflicting_overlap_scope_manifest_and_expiry(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    contents = [
        (ORDER_HEADER + csv_line(0)).encode(),
        (ORDER_HEADER + csv_line(0, quantity=2)).encode(),
    ]
    shop = create_shop(logged_in)
    data = group_data(contents)
    invalid = {**data, "manifest": {**data["manifest"], "total_rows": 3}}
    assert logged_in.post(f"/api/shops/{shop}/import-groups", json=invalid).status_code == 422
    group = create_group(logged_in, shop, data)
    first = part_upload(logged_in, group, 1, contents[0])
    with session_factory() as session:
        batch = session.get(ImportBatch, first["id"])
        assert batch is not None
        batch.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()
    first = commit(logged_in, preview(logged_in, part_upload(logged_in, group, 1, contents[0])))
    second = preview(logged_in, part_upload(logged_in, group, 2, contents[1]))
    assert any(e["field"] == "group_key" for e in second["rows"][0]["errors"])
    assert (
        logged_in.post(
            f"/api/imports/{second['id']}/commit",
            json={"version": second["version"], "allow_updates": True},
        ).status_code
        == 409
    )
    commit(logged_in, preview(logged_in, second, corrections={"2": {"quantity": "1"}}))
    for changes in (
        {"data_identity": "user_import"},
        {"source_channel": "amazon"},
        {"timezone": "UTC"},
        {"group_part": 3},
    ):
        response = logged_in.post(
            f"/api/shops/{shop}/imports",
            params={
                **data["options"],
                "filename": "part-001.csv",
                "group_id": group["id"],
                "group_part": 1,
                **changes,
            },
            content=contents[0],
        )
        assert response.status_code == 409
    response = logged_in.post(
        f"/api/shops/{shop}/imports",
        params={
            **data["options"],
            "filename": "part-001.csv",
            "group_id": group["id"],
            "group_part": 1,
        },
        content=contents[1],
    )
    assert response.status_code == 409
    other = create_shop(logged_in, "other")
    assert (
        logged_in.post(
            f"/api/shops/{other}/imports",
            params={
                **data["options"],
                "filename": "part-001.csv",
                "group_id": group["id"],
                "group_part": 1,
            },
            content=contents[0],
        ).status_code
        == 404
    )
    assert logged_in.get(f"/api/shops/{other}/import-groups").json() == []


def test_group_revoke_transaction_rolls_back_all_parts(logged_in: TestClient) -> None:
    contents = [(ORDER_HEADER + csv_line(i)).encode() for i in range(2)]
    group = create_group(logged_in, create_shop(logged_in), group_data(contents))
    for index, content in enumerate(contents, 1):
        commit(logged_in, preview(logged_in, part_upload(logged_in, group, index, content)))
    current = read_group(logged_in, group)
    original = ImportService.withdraw
    calls = 0

    def fail_second(service: ImportService, *args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise BusinessError("synthetic_failure", "合成撤销故障", 422)
        return original(service, *args, **kwargs)

    with patch.object(ImportService, "withdraw", fail_second):
        response = logged_in.post(
            f"/api/import-groups/{group['id']}/revoke", json={"version": current["version"]}
        )
    assert response.status_code == 422
    assert read_group(logged_in, group) == current
    assert Decimal(calculate(logged_in, group["shop_id"])["summary"]["sales"]) == Decimal(4)


def test_split_byte_limit_multiline_unicode_and_refuse_overwrite(tmp_path: Path) -> None:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["sku", "name", "facts"])
    for index in range(650):
        writer.writerow([f"S{index}", "合成,商品", "首行\n" + "字" * 1800])
    source = tmp_path / "synthetic.csv"
    source.write_bytes(output.getvalue().encode("utf-8-sig"))
    assert source.stat().st_size > MAX_BYTES
    manifest = split_csv(source, tmp_path / "parts")
    assert manifest.total_rows == 650 and len(manifest.parts) == 2
    rows = []
    for part in manifest.parts:
        content = (tmp_path / "parts" / part.filename).read_bytes()
        assert len(content) <= MAX_BYTES and hashlib.sha256(content).hexdigest() == part.sha256
        rows.extend(parse_file(part.filename, content)[1])
    assert len(rows) == 650 and rows[-1].values[2] == "首行\n" + "字" * 1800
    with pytest.raises(ValueError, match="已存在"):
        split_csv(source, tmp_path / "parts")


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"sku,sku\nx,y\n",
        b"sku,name\nx,\xff\n",
        b'sku,name\nx,"bad\n',
        b"sku,name\nx," + b"a" * 2001 + b"\n",
    ],
)
def test_split_bad_input_keeps_source_and_leaves_no_parts(tmp_path: Path, content: bytes) -> None:
    source = tmp_path / "source.csv"
    source.write_bytes(content)
    with pytest.raises(ValueError):
        split_csv(source, tmp_path / "parts")
    assert source.read_bytes() == content and not (tmp_path / "parts").exists()


def test_group_owner_isolation(logged_in, session_factory, settings):
    from app.repositories.unit_of_work import UnitOfWork
    from app.schemas.identity import AccountInput
    from app.services.auth import AuthService
    from tests.conftest import TEST_PASSWORD

    content = (ORDER_HEADER + csv_line(0)).encode()
    data = group_data([content])
    group = create_group(logged_in, create_shop(logged_in), data)
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="another", password=TEST_PASSWORD)
        )
    result = logged_in.post(
        "/api/auth/login", json={"username": "another", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    assert logged_in.get(f"/api/import-groups/{group['id']}").status_code == 404
    assert logged_in.get(f"/api/shops/{group['shop_id']}/import-groups").status_code == 404
    assert (
        logged_in.post(
            f"/api/import-groups/{group['id']}/revoke", json={"version": group["version"]}
        ).status_code
        == 404
    )
    assert (
        logged_in.post(f"/api/shops/{group['shop_id']}/import-groups", json=data).status_code == 404
    )
    other = create_shop(logged_in, "other-owner")
    assert (
        logged_in.post(
            f"/api/shops/{other}/imports",
            params={
                **data["options"],
                "filename": "part-001.csv",
                "group_id": group["id"],
                "group_part": 1,
            },
            content=content,
        ).status_code
        == 404
    )


def test_group_mapping_and_source_freshness_gates(logged_in):
    from tests.test_analytics import save

    shop = create_shop(logged_in)
    commit(
        logged_in,
        preview(logged_in, upload(logged_in, shop, ORDER_HEADER + csv_line(10), "orders")),
    )
    saved = save(logged_in, shop)
    contents = [(ORDER_HEADER + csv_line(i)).encode() for i in range(2)]
    group = create_group(logged_in, shop, group_data(contents))
    assert (
        logged_in.get(f"/api/shops/{shop}/analytics/saved/{saved['id']}").json()["status"]
        == "stale"
    )
    # Other identity and channel queries remain possible for order-only groups.
    assert (
        logged_in.post(
            f"/api/shops/{shop}/analytics/calculate", json={**SCOPE, "data_identity": "user_import"}
        ).status_code
        == 200
    )
    assert (
        logged_in.post(
            f"/api/shops/{shop}/analytics/calculate", json={**SCOPE, "channel": "amazon"}
        ).status_code
        == 200
    )
    commit(logged_in, preview(logged_in, part_upload(logged_in, group, 1, contents[0])))
    second = part_upload(logged_in, group, 2, contents[1])
    response = logged_in.post(
        f"/api/imports/{second['id']}/preview",
        json={
            "version": second["version"],
            "mapping": {**second["mapping"], "unit_price": "refund", "refund": "unit_price"},
        },
    )
    assert response.status_code == 409
    second = commit(logged_in, preview(logged_in, second))
    assert read_group(logged_in, group)["complete"]
    assert (
        logged_in.post(
            f"/api/imports/{second['id']}/clear", json={"version": second["version"]}
        ).status_code
        == 200
    )
    assert not read_group(logged_in, group)["complete"]
    assert logged_in.post(f"/api/shops/{shop}/analytics/calculate", json=SCOPE).status_code == 409


def test_incomplete_groups_block_aggregate_services(logged_in, session_factory):
    from app.models.identity import Shop
    from app.repositories.unit_of_work import UnitOfWork
    from app.services.import_groups import require_import_coverage

    shop_id = create_shop(logged_in)
    data = group_data([b"sku,name\nS1,Synthetic\n"])
    data["options"]["kind"] = "products"
    create_group(logged_in, shop_id, data)
    with session_factory() as session:
        shop = session.get(Shop, shop_id)
        # Product source channels may differ from order channels; cost completeness still gates.
        with pytest.raises(BusinessError, match="部分覆盖"):
            require_import_coverage(
                UnitOfWork(session), shop.owner_id, shop_id, "synthetic", {"products"}, "amazon"
            )
        require_import_coverage(
            UnitOfWork(session), shop.owner_id, shop_id, "synthetic", {"statements"}, "amazon"
        )


def test_migration_refuses_to_drop_active_group_coverage(logged_in, settings, monkeypatch):
    from alembic import command
    from alembic.config import Config

    group = create_group(
        logged_in, create_shop(logged_in), group_data([(ORDER_HEADER + csv_line(0)).encode()])
    )
    monkeypatch.setenv("SOLOOPS_DATABASE_URL", settings.database_url.get_secret_value())
    try:
        with pytest.raises(RuntimeError, match="活动导入组"):
            command.downgrade(Config("alembic.ini"), "92c7ea53bd10")
    finally:
        command.upgrade(Config("alembic.ini"), "head")
    assert read_group(logged_in, group)["status"] == "active"
