"""Run a single existing Agent action with an independent session and SSE output."""

import json
from collections.abc import Iterator
from queue import Empty, SimpleQueue
from threading import Thread
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import BusinessError
from app.models.agent import AgentExecution
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import AgentAction
from app.services.agent import AgentService
from app.services.agent_model import DecisionModel
from app.services.model_stream import stream_deltas


def action_events(
    factory: sessionmaker[Session],
    model: DecisionModel,
    owner: int,
    shop: int,
    run_id: int,
    data: AgentAction,
) -> Iterator[str]:
    events: SimpleQueue[tuple[str, dict[str, Any]] | None] = SimpleQueue()

    def execute() -> None:
        try:
            # The worker creates, uses and closes its own Session on the same thread.
            # A disconnected browser does not cancel cost settlement or retry a model call.
            with (
                factory() as session,
                stream_deltas(lambda text: events.put(("delta", {"text": text}))),
            ):
                result = AgentService(UnitOfWork(session), model).act(owner, shop, run_id, data)
                events.put(("result", result.model_dump(mode="json")))
        except BusinessError as error:
            events.put(("error", {"code": error.code, "message": error.message}))
        except Exception:
            # Remote or database exception text can contain secrets. Never send it to SSE.
            events.put(
                ("error", {"code": "internal_error", "message": "执行连接异常，请刷新查看任务结果"})
            )
        finally:
            events.put(None)

    yield _event("status", {"status": "running", "message": "正在执行当前步骤"})
    Thread(target=execute, name=f"agent-stream-{run_id}", daemon=True).start()
    while True:
        try:
            item = events.get(timeout=10)
        except Empty:
            yield ": heartbeat\n\n"
            continue
        if item is None:
            return
        if item[0] == "delta" and not _delta_visible(factory, owner, shop, run_id):
            # Check at delivery, so even deltas queued before a clear cannot reappear.
            # The producer continues reading upstream and settling the actual model charge.
            continue
        yield _event(*item)


def _delta_visible(factory: sessionmaker[Session], owner: int, shop: int, run_id: int) -> bool:
    try:
        # A fresh short transaction for each delivery avoids retaining an earlier
        # MySQL REPEATABLE READ snapshot. Never reuse the executing worker's Session.
        with factory() as session:
            source_status = session.scalar(
                select(AgentExecution.source_status).where(
                    AgentExecution.id == run_id,
                    AgentExecution.owner_id == owner,
                    AgentExecution.shop_id == shop,
                )
            )
            return source_status is not None and source_status != "cleared"
    except SQLAlchemyError:
        # An unconfirmed visibility check suppresses text without interrupting billing.
        return False


def _event(kind: str, data: dict[str, Any]) -> str:
    return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
