from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trd_bot.api.monitoring_lifecycle import build_monitoring_lifespan
from trd_bot.api.monitoring_middleware import ApiMetricsMiddleware
from trd_bot.api.routes.datasets import router as datasets_router
from trd_bot.api.routes.health import router as health_router
from trd_bot.api.routes.monitoring import (
    router as monitoring_router,
)
from trd_bot.api.routes.overview import router as overview_router
from trd_bot.api.routes.portfolios import router as portfolios_router
from trd_bot.api.routes.research import router as research_router
from trd_bot.core.config import get_settings
from trd_bot.monitoring import MonitoringObservationRecorder


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    monitoring_recorder = MonitoringObservationRecorder()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        description=("Research and paper-analysis platform for crypto market data."),
        lifespan=build_monitoring_lifespan(
            settings=settings,
            recorder=monitoring_recorder,
        ),
    )

    if settings.monitoring_collector_enabled:
        application.add_middleware(
            ApiMetricsMiddleware,
            recorder=monitoring_recorder,
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=[
            "GET",
            "POST",
        ],
        allow_headers=[
            "Accept",
            "Content-Type",
        ],
    )

    application.include_router(
        health_router,
        prefix="/api/v1",
    )

    application.include_router(
        datasets_router,
        prefix="/api/v1",
    )

    application.include_router(
        overview_router,
        prefix="/api/v1",
    )

    application.include_router(
        research_router,
        prefix="/api/v1",
    )

    application.include_router(
        portfolios_router,
        prefix="/api/v1",
    )

    application.include_router(
        monitoring_router,
        prefix="/api/v1",
    )

    return application


app = create_app()
