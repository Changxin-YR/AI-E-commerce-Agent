"""Explicit, repeatable setup of a small synthetic shop using normal business services."""

import csv
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import StringIO

from app.core.config import Settings
from app.core.errors import BusinessError, ConflictError
from app.core.security import hash_password, verify_password
from app.core.time import utc_now
from app.models.identity import User
from app.repositories.demo import DemoRepository
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import ProfileInput, ShopInput
from app.schemas.imports import CommitInput, ImportKind, PreviewInput, UploadOptions
from app.schemas.support import PolicyData, PolicyInput
from app.services.imports import ImportService
from app.services.listings import digest
from app.services.profile import ProfileService
from app.services.support import SupportService

DEMO_USERNAME = "admin"
DEMO_PASSWORD = "qwer123"
DEMO_SHOP_CODE = "demo-shop"


@dataclass(frozen=True)
class DemoSetupResult:
    user_id: int
    shop_id: int
    imported_rows: dict[str, int]


def demo_datasets(now: datetime) -> dict[ImportKind, list[list[str]]]:
    """Six products and recent activity are enough for all four primary workflows."""
    products = [
        ["DEMO-MUG", "Ceramic Coffee Mug", "Ceramic; 350 ml; cream white", "18.00", "7.00"],
        [
            "DEMO-BAG",
            "Canvas Tote Bag",
            "Cotton canvas; 38 x 42 cm; natural beige",
            "22.00",
            "9.00",
        ],
        ["DEMO-TOWEL", "Cotton Hand Towel", "Cotton; 35 x 75 cm; sage green", "12.00", "5.00"],
        ["DEMO-TRAY", "Bamboo Desk Tray", "Bamboo; 24 x 16 cm; natural finish", "24.00", "10.00"],
        ["DEMO-VASE", "Glass Bud Vase", "Glass; 18 cm tall; clear", "16.00", "14.00"],
        ["DEMO-POUCH", "Travel Storage Pouch", "Polyester; 22 x 15 cm; navy blue", "14.00", "5.50"],
    ]
    datasets: dict[ImportKind, list[list[str]]] = {
        "products": [["sku", "name", "facts", "price", "currency", "unit_cost", "cost_currency"]],
        "orders": [
            [
                "order_id",
                "line_id",
                "sku",
                "quantity",
                "unit_price",
                "currency",
                "ordered_at",
                "status",
                "discount",
                "refund",
                "fulfillment_status",
            ]
        ],
        "inventory": [["sku", "available", "snapshot_at", "safety_threshold"]],
        "messages": [
            [
                "message_id",
                "sent_at",
                "body",
                "language",
                "order_id",
                "reply_status",
                "reply_updated_at",
            ]
        ],
    }
    for sku, name, facts, price, cost in products:
        datasets["products"].append([sku, name, facts, price, "USD", cost, "USD"])
    for index in range(24):
        product = products[index % len(products)]
        datasets["orders"].append(
            [
                f"DEMO-ORDER-{index + 1:03}",
                "1",
                product[0],
                str(1 + index % 3),
                product[3],
                "USD",
                (now - timedelta(days=index % 14, hours=2 + index % 5)).isoformat(),
                "partially_refunded" if index == 5 else "paid",
                "0",
                "4.00" if index == 5 else "0",
                "unfulfilled" if index in {0, 1} else "fulfilled",
            ]
        )
    for index, product in enumerate(products):
        datasets["inventory"].append(
            [
                product[0],
                str([3, 28, 42, 16, 2, 35][index]),
                now.isoformat(),
                "8",
            ]
        )
    for index, body, order in [
        (1, "Where is my order? Could you check the shipping status?", "DEMO-ORDER-001"),
        (2, "How can I confirm the material and capacity of the coffee mug?", ""),
        (3, "I would like to return my purchase. What is the return process?", "DEMO-ORDER-006"),
    ]:
        sent_at = (now - timedelta(hours=2 + index)).isoformat()
        datasets["messages"].append(
            [
                f"DEMO-MESSAGE-{index:03}",
                sent_at,
                body,
                "en",
                order,
                "awaiting_reply",
                sent_at,
            ]
        )
    return datasets


def csv_bytes(rows: list[list[str]]) -> bytes:
    output = StringIO(newline="")
    csv.writer(output).writerows(rows)
    return output.getvalue().encode("utf-8-sig")


class DemoService:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self.uow = uow
        self.settings = settings
        self.repo = DemoRepository(uow.session)

    def setup(self, *, adopt_existing_admin: bool = False) -> DemoSetupResult:
        if not self.settings.demo_enabled:
            raise BusinessError("demo_disabled", "请先显式设置 SOLOOPS_DEMO_ENABLED=true", 403)
        with self.uow.defer_commits():
            user = self._account(adopt_existing_admin)
            self.uow.identity.lock_user(user.id)
            profile = ProfileService(self.uow)
            if profile.get_profile(user.id) is None:
                profile.save_profile(
                    user.id,
                    ProfileInput(
                        display_name="演示卖家",
                        target_market="US",
                        business_model="独立站零售",
                        category="家居与生活用品",
                        currency="USD",
                        timezone="Asia/Shanghai",
                        language="zh-CN",
                        version=0,
                    ),
                )
            shop = next(
                (shop for shop in profile.list_shops(user.id) if shop.code == DEMO_SHOP_CODE), None
            )
            if shop is None:
                shop = profile.create_shop(
                    user.id,
                    ShopInput(
                        code=DEMO_SHOP_CODE,
                        name="生活杂货演示店",
                        platform="manual",
                        market="US",
                        currency="USD",
                        timezone="Asia/Shanghai",
                    ),
                )
                self.uow.record_event(user.id, "demo.shop_initialized", "shop", shop.id)
            elif not self.repo.initialized(user.id, "demo.shop_initialized", shop.id):
                raise ConflictError("demo-shop 已存在且不属于演示初始化；请先核对店铺归属")
            now = utc_now().replace(tzinfo=UTC, microsecond=0)
            counts = self._imports(user.id, shop.id, now)
            self._policies(user.id, shop.id, now)
        self.uow.commit()
        return DemoSetupResult(user.id, shop.id, counts)

    def _account(self, adopt: bool) -> User:
        user = self.uow.identity.find_user(DEMO_USERNAME, lock=True)
        if user is None:
            user = User(username=DEMO_USERNAME, password_hash=hash_password(DEMO_PASSWORD))
            self.uow.identity.add_user(user)
            self.uow.record_event(user.id, "account.created", "user", user.id)
        elif not self.repo.initialized(user.id, "demo.account_initialized", user.id) and not adopt:
            raise ConflictError(
                "admin 已存在且未标记为演示账号；核实后使用 --adopt-existing-admin 明确转换"
            )
        changed = not verify_password(DEMO_PASSWORD, user.password_hash)
        if changed:
            user.password_hash = hash_password(DEMO_PASSWORD)
            self.uow.identity.delete_user_sessions(user.id)
            self.uow.record_event(user.id, "account.password_reset", "user", user.id)
        user.failed_login_count = 0
        user.locked_until = None
        if not self.repo.initialized(user.id, "demo.account_initialized", user.id):
            self.uow.record_event(user.id, "demo.account_initialized", "user", user.id)
        return user

    def _imports(self, owner: int, shop: int, now: datetime) -> dict[str, int]:
        service = ImportService(self.uow)
        counts: dict[str, int] = {}
        for kind, rows in demo_datasets(now).items():
            action = f"demo.{kind}_initialized"
            if self.repo.initialized(owner, action, shop):
                continue
            # Preserve any data imported or edited after the dedicated shop was created.
            if self.uow.imports.current_entries(owner, shop, kind):
                continue
            batch = service.upload(
                owner,
                shop,
                UploadOptions(
                    filename=f"demo-{kind}.csv",
                    kind=kind,
                    source_channel="generic",
                    data_identity="synthetic",
                    timezone="Asia/Shanghai",
                    exported_at=now,
                ),
                csv_bytes(rows),
            )
            batch = service.preview(
                owner,
                batch.id,
                PreviewInput(
                    version=batch.version,
                    mapping={column: column for column in rows[0]},
                ),
            )
            service.commit(
                owner,
                batch.id,
                CommitInput(
                    version=batch.version,
                    reviewed_fields=[item.field for item in batch.required_reviews],
                ),
            )
            counts[kind] = len(rows) - 1
            self.uow.record_event(owner, action, "shop", shop, {"rows": counts[kind]})
        return counts

    def _policies(self, owner: int, shop: int, now: datetime) -> None:
        service = SupportService(self.uow)
        policies: list[PolicyData] = [
            PolicyData(
                code="demo-shipping",
                title="演示发货说明",
                topic="shipping",
                text="Orders are normally prepared within 2 business days. "
                "Check the order record before confirming dispatch or delivery dates.",
                market="US",
                channel="generic",
                language="en",
                data_identity="synthetic",
                source="演示店铺合成政策",
                source_version="1",
                source_confirmed=True,
                valid_from=now - timedelta(days=1),
            ),
            PolicyData(
                code="demo-faq",
                title="演示商品说明",
                topic="faq",
                text="The coffee mug is ceramic with a capacity of 350 ml. "
                "Use the product record to confirm the specifications of other items.",
                market="US",
                channel="generic",
                language="en",
                data_identity="synthetic",
                source="演示店铺合成政策",
                source_version="1",
                source_confirmed=True,
                valid_from=now - timedelta(days=1),
            ),
            PolicyData(
                code="demo-returns",
                title="演示退货说明",
                topic="refund",
                text="Contact support with the order number to request a return review. "
                "Return eligibility and refund amounts must be checked by a seller.",
                market="US",
                channel="generic",
                language="en",
                data_identity="synthetic",
                source="演示店铺合成政策",
                source_version="1",
                source_confirmed=True,
                valid_from=now - timedelta(days=1),
            ),
        ]
        for policy in policies:
            if self.uow.support.latest_policy(owner, shop, digest([shop, policy.code])) is None:
                service.save_policy(owner, shop, PolicyInput(expected_policy_id=None, data=policy))
