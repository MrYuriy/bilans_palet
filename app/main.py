import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exc import register_exception_handlers
from app.middleware.logging import log_requests
from app.routers.area import router as area_router
from app.routers.audit import router as audit_router
from app.routers.auth import router as auth_router
from app.routers.inventory import router as inventory_router
from app.routers.movement import router as movement_router
from app.routers.pallet_type import router as pallet_type_router
from app.routers.quality import router as quality_router
from app.routers.users import router as users_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application started")
    yield
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
app.include_router(area_router)
app.include_router(pallet_type_router)
app.include_router(quality_router)
app.include_router(movement_router)
app.include_router(inventory_router)
app.include_router(audit_router)
