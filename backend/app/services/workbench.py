import base64
import binascii
import json
from datetime import datetime
from typing import Any

from app.core.errors import BusinessError, NotFoundError
from app.core.time import utc_now
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.workbench import WorkItem, WorkPage, WorkQuery
from app.services.listings import digest
from app.services.profit_calculation import utc_text

LINKS = {
    "operation_task": ("/", "task", "R1"),
    "operation_run": ("/", "run", "R0"),
    "agent": ("/agent", "execution", "按节点核验"),
    "listing": ("/listings", "listing", "R1"),
    "reply": ("/support", "draft", "R1"),
    "analysis_todo": ("/analytics", "analysis", "R1"),
    "analysis": ("/analytics", "analysis", "R0"),
    "overview": ("/overview", "report", "R0"),
    "authorization": ("/agent", "authorization", "R1"),
    "outbound": ("/outbound", "mail", "R2"),
}

DETAIL_LABELS = {
    "data_check": "检查数据",
    "metrics": "核对指标",
    "propose_tasks": "保存候选",
    "product_context": "读取商品",
    "listing_draft": "保存文案草稿",
    "message_context": "读取消息",
    "support_draft": "保存客服草稿",
    "verify": "回读核验",
    "plan": "识别目标",
    "end": "结束",
    "completed": "已完成",
    "failed": "失败",
    "waiting_approval": "等待审批",
    "ready": "待执行",
    "paused": "暂停",
    "running": "执行中",
    "discarded": "结果未采纳",
    "result_unknown": "结果未知",
    "low_inventory": "库存阈值核对",
    "low_margin": "已知低毛利核对",
    "order_review": "订单履约核对",
    "message_review": "消息回复核对",
}


def detail_text(row: dict[str, Any]) -> str:
    if row["source_status"] == "cleared":
        return "正文已清除"
    text = row["detail"] or ""
    if row["kind"] in {"agent", "operation_task"}:
        text = " · ".join(DETAIL_LABELS.get(part, part) for part in text.split(" · "))
    return str(text)[:240]


def fingerprint(query: WorkQuery) -> str:
    return digest(query.model_dump(exclude={"cursor"}))


def decode_cursor(query: WorkQuery) -> tuple[datetime, str, int] | None:
    if not query.cursor:
        return None
    try:
        at, kind, identifier, scope = json.loads(base64.urlsafe_b64decode(query.cursor))
        stamp = datetime.fromisoformat(at)
        if (
            stamp.tzinfo is not None
            or stamp.year < 1000
            or kind not in LINKS
            or type(identifier) is not int
            or identifier <= 0
            or scope != fingerprint(query)
        ):
            raise ValueError
        return stamp, kind, identifier
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError) as error:
        raise BusinessError("invalid_cursor", "列表范围或游标无效，请重新刷新", 422) from error


def encode_cursor(row: dict[str, Any], query: WorkQuery) -> str:
    value = [row["created_at"].isoformat(), row["kind"], row["id"], fingerprint(query)]
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode()


def output(row: dict[str, Any]) -> WorkItem:
    path, key, risk = LINKS[row["kind"]]
    query = {key: str(row["target_id"])}
    if row["shop_id"] is not None:
        query["shop"] = str(row["shop_id"])
    for field, param in [("data_identity", "identity"), ("channel", "channel")]:
        if row[field]:
            query[param] = row[field]
    return WorkItem(
        **{
            k: row[k]
            for k in [
                "kind",
                "id",
                "target_id",
                "shop_id",
                "data_identity",
                "channel",
                "status",
                "source_status",
                "bucket",
            ]
        },
        shop_name=row["shop_name"] or "跨店经营摘要",
        timezone=row["timezone"] or "UTC",
        label=(row["label"] or "")[:120] if row["source_status"] != "cleared" else "",
        detail=detail_text(row),
        created_at=utc_text(row["created_at"]),
        due_at=utc_text(row["due_at"]) if row["due_at"] else None,
        risk=risk,
        path=path,
        query=query,
    )


class WorkbenchService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def page(self, owner: int, query: WorkQuery) -> WorkPage:
        if query.shop_id and self.uow.identity.get_shop(owner, query.shop_id) is None:
            raise NotFoundError()
        before = decode_cursor(query)
        now = utc_now()
        rows, counts, recent = self.uow.workbench.page(owner, query, now, before)
        return WorkPage(
            items=[output(row) for row in rows[:20]],
            recent_runs=[output(row) for row in recent],
            counts=counts,
            next_cursor=encode_cursor(rows[19], query) if len(rows) > 20 else None,
            read_at=utc_text(now),
        )
