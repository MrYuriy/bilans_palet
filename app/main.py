import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exc import register_exception_handlers
from app.middleware.logging import log_requests
from app.routers.audit import router as audit_router
from app.routers.auth import router as auth_router
from app.routers.balance import router as balance_router
from app.routers.carrier_group import router as carrier_group_router
from app.routers.carrier_type import router as carrier_type_router
from app.routers.inventory import router as inventory_router
from app.routers.movement import router as movement_router
from app.routers.pages import STATIC_DIR
from app.routers.pages import router as pages_router
from app.routers.setting import router as setting_router
from app.routers.users import router as users_router
from app.services.day_close_service import day_close_loop

# Without this the app's own INFO messages (requests, closed days) are dropped:
# uvicorn configures only its own loggers.
logging.basicConfig(
    level=settings.app.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    day_close = None
    if settings.app.DAY_CLOSE_ENABLED:
        day_close = asyncio.create_task(
            day_close_loop(AsyncSessionLocal, settings.app.DAY_CLOSE_INTERVAL_SECONDS)
        )
    logger.info("Application started")
    yield
    if day_close is not None:
        day_close.cancel()
        with suppress(asyncio.CancelledError):
            await day_close
    logger.info("Application stopped")


app = FastAPI(
    title=settings.app.PROJECT_NAME,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(log_requests)

register_exception_handlers(app)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(carrier_group_router)
app.include_router(carrier_type_router)
app.include_router(movement_router)
app.include_router(inventory_router)
app.include_router(audit_router)
app.include_router(setting_router)
app.include_router(balance_router)
app.include_router(pages_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
