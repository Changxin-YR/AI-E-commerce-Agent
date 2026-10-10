"""Read-only projections of existing records; no second task state or body cache."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, and_, case, cast, exists, func, literal, or_, select, union_all
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql import ColumnElement

from app.models.agent import AgentExecution, AgentStep
from app.models.analytics import AnalysisTodo, SavedAnalysis
from app.models.authorizations import InternalAuthorization
from app.models.business_rules import BusinessRuleRevision
from app.models.identity import Shop
from app.models.imports import ImportBatch, ImportRow
from app.models.listings import ListingVersion
from app.models.operations import OperationRun, OperationTask
from app.models.outbound import OutboundMessage
from app.models.overview import OverviewReport, OverviewShop
from app.models.support import ReplyDraft, ReplyPolicy, SupportPolicy
from app.schemas.workbench import WorkQuery

Expr = ColumnElement[Any] | InstrumentedAttribute[Any]


def rules_changed(owner: Expr, shop: Expr, channel: Expr, identity: Expr, version: Expr) -> Expr:
    current = (
        select(func.max(BusinessRuleRevision.id))
        .where(
            BusinessRuleRevision.owner_id == owner,
            BusinessRuleRevision.shop_id == shop,
            BusinessRuleRevision.channel == channel,
            BusinessRuleRevision.data_identity == identity,
        )
        .correlate_except(BusinessRuleRevision)
        .scalar_subquery()
    )
    return func.coalesce(current, 0) != func.coalesce(version, 0)


def source_state(status: Expr, invalid: Expr) -> Expr:
    return case((and_(status == "current", invalid), "stale"), else_=status)


def row_channel(row: Expr, owner: Expr, shop: Expr) -> Expr:
    return (
        select(ImportBatch.source_channel)
        .join(ImportRow, ImportRow.batch_id == ImportBatch.id)
        .where(ImportRow.id == row, ImportBatch.owner_id == owner, ImportBatch.shop_id == shop)
        .correlate_except(ImportBatch, ImportRow)
        .scalar_subquery()
    )


def projection(
    kind: str,
    model: Any,
    identity: Expr,
    channel: Expr,
    status: Expr,
    source: Expr,
    *,
    label: Expr | None = None,
    detail: Expr | None = None,
    target: Expr | None = None,
    due: Expr | None = None,
    shop: Expr | None = None,
    business: Expr | None = None,
    review_current: Expr | None = None,
) -> Select[Any]:
    return select(
        literal(kind).label("kind"),
        model.id.label("id"),
        (target if target is not None else model.id).label("target_id"),
        (shop if shop is not None else model.shop_id).label("shop_id"),
        model.created_at.label("created_at"),
        identity.label("data_identity"),
        channel.label("channel"),
        status.label("status"),
        source.label("source_status"),
        (label if label is not None else literal("")).label("label"),
        (detail if detail is not None else literal("")).label("detail"),
        (due if due is not None else literal(None)).label("due_at"),
        (business if business is not None else literal(None)).label("business_state"),
        (review_current if review_current is not None else literal(False)).label("review_current"),
    )


def task_statement(owner: int, now: datetime) -> Select[Any]:
    task = OperationTask
    changed = rules_changed(
        task.owner_id,
        task.shop_id,
        task.channel,
        task.data_identity,
        task.snapshot["rule_revision_id"].as_integer(),
    )
    result = task.review["recheck"]
    revision = result["source_revision"].as_integer()
    expiry_text = result["valid_until"].as_string()
    expiry = cast(
        func.replace(func.substring_index(expiry_text, "+", 1), "T", " "), DATETIME(fsp=6)
    )
    current = func.coalesce(
        and_(
            revision.is_not(None),
            ~changed,
            revision == Shop.data_revision,
            or_(expiry_text.is_(None), expiry > now),
        ),
        False,
    )
    business = case(
        (task.source_status == "cleared", "cleared"),
        (task.status.in_(["ignored", "rejected"]), "ignored"),
        (and_(revision.is_not(None), ~current), "awaiting_source"),
        (task.review["state"].as_string().is_not(None), task.review["state"].as_string()),
        (task.status == "completed", "checked_pending"),
        else_="pending_review",
    )
    return (
        projection(
            "operation_task",
            task,
            task.data_identity,
            task.channel,
            task.status,
            source_state(task.source_status, changed | (task.valid_until <= now)),
            label=task.snapshot["object_label"].as_string(),
            detail=task.kind,
            due=task.due_at,
            business=business,
            review_current=current,
        )
        .join(Shop, and_(Shop.id == task.shop_id, Shop.owner_id == owner))
        .where(task.owner_id == owner)
    )


def agent_statement(owner: int, now: datetime) -> Select[Any]:
    agent = AgentExecution
    scope: Expr = agent.input["scope"]
    invalid = rules_changed(
        agent.owner_id,
        agent.shop_id,
        scope["channel"].as_string(),
        scope["data_identity"].as_string(),
        scope["rule_revision_id"].as_integer(),
    ) | (agent.valid_until <= now)
    state = case(
        (and_(agent.status == "running", agent.lease_until <= now), "result_unknown"),
        else_=agent.status,
    )
    last_step = (
        select(func.concat(AgentStep.node, " · ", AgentStep.status))
        .where(AgentStep.execution_id == agent.id)
        .order_by(AgentStep.id.desc())
        .limit(1)
        .correlate_except(AgentStep)
        .scalar_subquery()
    )
    return projection(
        "agent",
        agent,
        scope["data_identity"].as_string(),
        scope["channel"].as_string(),
        state,
        source_state(agent.source_status, invalid),
        label=agent.template,
        detail=func.concat("步骤 ", agent.steps_used, " · ", func.coalesce(last_step, "尚无步骤")),
    ).where(agent.owner_id == owner)


def listing_statement(owner: int) -> Select[Any]:
    listing = ListingVersion
    return projection(
        "listing",
        listing,
        listing.snapshot["product"]["source"]["data_identity"].as_string(),
        row_channel(listing.source_row_id, listing.owner_id, listing.shop_id),
        listing.status,
        listing.source_status,
        label=listing.snapshot["product"]["sku"].as_string(),
        detail=func.concat("版本 ", listing.number),
    ).where(listing.owner_id == owner)


def reply_statement(owner: int, now: datetime) -> Select[Any]:
    reply = ReplyDraft
    expired = exists(
        select(ReplyPolicy.draft_id)
        .join(SupportPolicy)
        .where(
            ReplyPolicy.draft_id == reply.id,
            SupportPolicy.owner_id == owner,
            SupportPolicy.shop_id == reply.shop_id,
            or_(SupportPolicy.valid_until <= now, SupportPolicy.valid_from > now),
        )
    )
    return projection(
        "reply",
        reply,
        reply.snapshot["message"]["source"]["data_identity"].as_string(),
        reply.snapshot["message"]["channel"].as_string(),
        reply.status,
        source_state(reply.source_status, expired),
        label=reply.snapshot["message"]["message_id"].as_string(),
    ).where(reply.owner_id == owner)


def grant_statement(owner: int, now: datetime) -> Select[Any]:
    grant = InternalAuthorization
    scope = grant.scope
    changed = rules_changed(
        grant.owner_id,
        grant.shop_id,
        scope["channel"].as_string(),
        scope["data_identity"].as_string(),
        scope["rule_revision_id"].as_integer(),
    )
    data_changed = (grant.source_revision != Shop.data_revision) | (grant.source_valid_until <= now)
    grant_status = case(
        (grant.revoked_at.is_not(None), "revoked"),
        (grant.expires_at <= now, "expired"),
        (data_changed, "source_changed"),
        (changed, "rules_changed"),
        (grant.used_count >= grant.max_uses, "exhausted"),
        else_="active",
    )
    return (
        projection(
            "authorization",
            grant,
            scope["data_identity"].as_string(),
            scope["channel"].as_string(),
            grant_status,
            case((data_changed | changed, "stale"), else_="current"),
            detail=func.concat("已用 ", grant.used_count, " / ", grant.max_uses),
            due=grant.expires_at,
        )
        .join(Shop, and_(Shop.id == grant.shop_id, Shop.owner_id == owner))
        .where(grant.owner_id == owner)
    )


def analysis_statements(owner: int) -> list[Select[Any]]:
    rows: list[Select[Any]] = []
    analysis = SavedAnalysis
    rows.append(
        projection(
            "analysis",
            analysis,
            analysis.scope["data_identity"].as_string(),
            analysis.scope["channel"].as_string(),
            literal("saved"),
            analysis.status,
            detail=analysis.scope["currency"].as_string(),
        ).where(analysis.owner_id == owner)
    )
    rows.append(
        projection(
            "analysis_todo",
            AnalysisTodo,
            analysis.scope["data_identity"].as_string(),
            analysis.scope["channel"].as_string(),
            AnalysisTodo.status,
            analysis.status,
            target=analysis.id,
            shop=analysis.shop_id,
        )
        .join(analysis, AnalysisTodo.analysis_id == analysis.id)
        .where(analysis.owner_id == owner)
    )
    return rows


def run_source_state(now: datetime) -> Expr:
    run = OperationRun
    scope = run.scope
    invalid = rules_changed(
        run.owner_id,
        run.shop_id,
        scope["channel"].as_string(),
        scope["data_identity"].as_string(),
        scope["rule_revision_id"].as_integer(),
    ) | (run.valid_until <= now)
    return source_state(run.source_status, invalid)


def run_statement(owner: int, now: datetime) -> Select[Any]:
    run = OperationRun
    scope = run.scope
    return projection(
        "operation_run",
        run,
        scope["data_identity"].as_string(),
        scope["channel"].as_string(),
        literal("saved"),
        run_source_state(now),
        detail=func.concat(
            "新增候选 ",
            run.snapshot["created_candidates"].as_integer(),
            " · 复用 ",
            run.snapshot["reused_candidates"].as_integer(),
            " · 截至 ",
            run.snapshot["data_as_of"].as_string(),
        ),
    ).where(run.owner_id == owner)


def mail_statement(owner: int, now: datetime) -> Select[Any]:
    run = OperationRun
    scope = run.scope
    mail = OutboundMessage
    mail_status = case(
        (
            and_(mail.status == "sending", mail.dispatch_at <= now - timedelta(seconds=60)),
            "unknown",
        ),
        else_=mail.status,
    )
    return (
        projection(
            "outbound",
            mail,
            scope["data_identity"].as_string(),
            scope["channel"].as_string(),
            mail_status,
            source_state(mail.source_status, run_source_state(now) != "current"),
            detail=func.concat("关联检查 #", mail.run_id),
        )
        .join(run, and_(run.id == mail.run_id, run.owner_id == owner, run.shop_id == mail.shop_id))
        .where(mail.owner_id == owner)
    )


def overview_statement(owner: int, now: datetime, shop_filter: int | None) -> Select[Any]:
    report = OverviewReport
    query = projection(
        "overview",
        report,
        report.scope["data_identity"].as_string(),
        literal(None),
        literal("saved"),
        source_state(report.status, report.valid_until <= now),
        detail=func.concat(
            report.scope["start_date"].as_string(), " 至 ", report.scope["end_date"].as_string()
        ),
        shop=literal(None),
    ).where(report.owner_id == owner)
    if shop_filter:
        query = query.where(
            exists(
                select(OverviewShop.report_id).where(
                    OverviewShop.report_id == report.id,
                    OverviewShop.shop_id == shop_filter,
                )
            )
        )
    return query


def statements(owner: int, now: datetime, shop_filter: int | None) -> list[Select[Any]]:
    return [
        task_statement(owner, now),
        agent_statement(owner, now),
        listing_statement(owner),
        reply_statement(owner, now),
        *analysis_statements(owner),
        run_statement(owner, now),
        mail_statement(owner, now),
        grant_statement(owner, now),
        overview_statement(owner, now, shop_filter),
    ]


def bucket(status: Expr, source: Expr, kind: Expr) -> Expr:
    return case(
        (status.in_(["unknown", "result_unknown"]), "unknown"),
        (source == "cleared", "history"),
        (source == "stale", "stale"),
        (status.in_(["blocked", "circuit_open", "failed"]), "failed"),
        (
            or_(
                status.in_(["pending_approval", "waiting_approval"]),
                and_(kind.in_(["listing", "outbound"]), status == "draft"),
            ),
            "approval",
        ),
        (
            status.in_(
                [
                    "ready",
                    "running",
                    "paused",
                    "waiting_input",
                    "waiting_configuration",
                    "open",
                    "deferred",
                    "draft",
                    "handoff",
                    "human_review",
                    "sending",
                ]
            ),
            "pending",
        ),
        else_="history",
    )


def seller_view(status: Expr, source: Expr, kind: Expr, business: Expr, current: Expr) -> Expr:
    """Mutually exclusive seller actions, independent of the original record's bucket."""
    return case(
        (status.in_(["unknown", "result_unknown"]), "attention"),
        (source == "cleared", None),
        (and_(kind == "operation_task", business == "ignored"), None),
        (and_(kind == "operation_task", current, business == "resolved"), None),
        (and_(kind == "operation_task", current, business == "still_anomalous"), "attention"),
        (and_(kind == "operation_task", business == "awaiting_source"), "update_data"),
        (source == "stale", "update_data"),
        (and_(kind == "agent", status == "succeeded"), "ai_completed"),
        (and_(kind == "operation_task", status == "completed"), "attention"),
        (bucket(status, source, kind).in_(["pending", "approval", "failed"]), "attention"),
        else_=None,
    )


class WorkbenchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def page(
        self,
        owner: int,
        query: WorkQuery,
        now: datetime,
        before: tuple[datetime, str, int] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int], list[dict[str, Any]]]:
        records = union_all(*statements(owner, now, query.shop_id)).subquery()
        c = records.c
        filtered = select(
            records,
            bucket(c.status, c.source_status, c.kind).label("bucket"),
            seller_view(
                c.status, c.source_status, c.kind, c.business_state, c.review_current
            ).label("view"),
        )
        if query.shop_id:
            filtered = filtered.where((c.shop_id == query.shop_id) | (c.kind == "overview"))
        if query.data_identity:
            filtered = filtered.where(c.data_identity == query.data_identity)
        if query.channel:
            filtered = filtered.where(c.channel == query.channel)
        recent = filtered.where(c.kind.in_(["agent", "operation_run"])).subquery()
        latest = self.session.execute(
            select(recent, Shop.name.label("shop_name"), Shop.timezone.label("timezone"))
            .join(Shop, and_(Shop.id == recent.c.shop_id, Shop.owner_id == owner))
            .order_by(recent.c.created_at.desc(), recent.c.kind.desc(), recent.c.id.desc())
            .limit(3)
        ).mappings()
        recent_rows = [dict(row) for row in latest]
        if query.kind:
            filtered = filtered.where(c.kind == query.kind)
        scoped = filtered.subquery()
        c = scoped.c
        counts: dict[str, int] = {}
        view_counts: dict[str, int] = {}
        for key, view, value in self.session.execute(
            select(c.bucket, c.view, func.count()).group_by(c.bucket, c.view)
        ):
            counts[key] = counts.get(key, 0) + int(value)
            if view:
                view_counts[view] = view_counts.get(view, 0) + int(value)
        stmt = select(
            scoped, Shop.name.label("shop_name"), Shop.timezone.label("timezone")
        ).outerjoin(
            Shop,
            and_(Shop.id == c.shop_id, Shop.owner_id == owner),
        )
        # A selected shop is checked by the service; each branch is independently owner scoped.
        if query.bucket:
            stmt = stmt.where(c.bucket == query.bucket)
        if query.view:
            stmt = stmt.where(c.view == query.view)
        if before:
            at, kind, identifier = before
            stmt = stmt.where(
                or_(
                    c.created_at < at,
                    and_(c.created_at == at, c.kind < kind),
                    and_(c.created_at == at, c.kind == kind, c.id < identifier),
                )
            )
        stmt = stmt.order_by(c.created_at.desc(), c.kind.desc(), c.id.desc()).limit(21)
        return (
            [dict(row) for row in self.session.execute(stmt).mappings()],
            counts,
            view_counts,
            recent_rows,
        )
