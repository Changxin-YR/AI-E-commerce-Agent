import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.dependencies import UowDependency
from app.api.errors import register_error_handlers
from app.api.middleware import register_request_middleware
from app.api.routes import (
    agent,
    analytics,
    auth,
    authorizations,
    business_rules,
    imports,
    inventory,
    listings,
    operations,
    outbound,
    overview,
    product_quality,
    profile,
    profit,
    schedules,
    support,
    workbench,
)
from app.core.config import Settings
from app.core.errors import BusinessError
from app.repositories.database import create_database_engine, create_session_factory
from app.services.scheduler import serve


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    engine = create_database_engine(resolved_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        stop = asyncio.Event()
        worker = (
            asyncio.create_task(serve(application.state.session_factory, stop))
            if resolved_settings.scheduler_enabled
            else None
        )
        try:
            yield
        finally:
            stop.set()
            if worker:
                await worker
            engine.dispose()

    application = FastAPI(title="SoloOps API", version="0.1.0", lifespan=lifespan)
    application.state.settings = resolved_settings
    application.state.session_factory = create_session_factory(engine)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=resolved_settings.trusted_hosts)
    register_error_handlers(application)
    register_request_middleware(application, resolved_settings)
    application.include_router(auth.router, prefix="/api")
    application.include_router(profile.router, prefix="/api")
    application.include_router(imports.router, prefix="/api")
    application.include_router(analytics.router, prefix="/api")
    application.include_router(listings.router, prefix="/api")
    application.include_router(support.router, prefix="/api")
    application.include_router(inventory.router, prefix="/api")
    application.include_router(operations.router, prefix="/api")
    application.include_router(outbound.router, prefix="/api")
    application.include_router(overview.router, prefix="/api")
    application.include_router(agent.router, prefix="/api")
    application.include_router(authorizations.router, prefix="/api")
    application.include_router(profit.router, prefix="/api")
    application.include_router(business_rules.router, prefix="/api")
    application.include_router(workbench.router, prefix="/api")
    application.include_router(schedules.router, prefix="/api")
    application.include_router(product_quality.router, prefix="/api")

    @application.get("/api/health/live", tags=["健康检查"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/health/ready", tags=["健康检查"])
    def ready(uow: UowDependency) -> dict[str, str]:
        try:
            uow.ping()
        except SQLAlchemyError as error:
            raise BusinessError("database_unavailable", "数据库暂时不可用", 503) from error
        return {"status": "ok", "database": "mysql"}

    return application
