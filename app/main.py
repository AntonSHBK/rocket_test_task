from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import close_database
from app.routers import router
from app.settings import settings
from app.utils.exceptions import register_exception_handlers
from app.utils.logging import get_process_logger

logger = get_process_logger(
    process_name="api",
    log_dir=settings.log_dir,
    log_level=settings.log_level,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Application started")
    yield
    await close_database()
    logger.info("Application stopped")


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.mount(
        "/static",
        StaticFiles(directory=STATIC_DIR),
        name="static",
    )
    register_exception_handlers(application)
    application.include_router(router)
    return application


app = create_app()
