from fastapi import FastAPI

from trd_bot.api.routes.health import router as health_router
from trd_bot.api.routes.research import router as research_router
from trd_bot.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        description=("Research and paper-analysis platform for crypto market data."),
    )

    application.include_router(
        health_router,
        prefix="/api/v1",
    )

    application.include_router(
        research_router,
        prefix="/api/v1",
    )

    return application


app = create_app()
