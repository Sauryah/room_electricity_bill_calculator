"""FastAPI entry point for the Room Bill Splitter backend."""
import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.client import (
    create_user,
    get_user_by_username,
    init_schema,
    update_user_password,
)
from app.routes.auth import router as auth_router
from app.routes.calculate import router as calculate_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Room Bill Splitter API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()] or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All endpoints under /api so they pass through Kubernetes ingress.
api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(calculate_router)


@api_router.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(api_router)


def _seed_admin() -> None:
    """Create the admin user from env vars; idempotent and self-healing."""
    username = settings.ADMIN_USERNAME.strip().lower()
    password = settings.ADMIN_PASSWORD

    existing = get_user_by_username(username)
    if existing is None:
        create_user(username=username, password_hash=hash_password(password))
        logger.info("Seeded admin user '%s'", username)
        return

    if not verify_password(password, existing["password_hash"]):
        update_user_password(username, hash_password(password))
        logger.info("Updated admin password for '%s'", username)


@app.on_event("startup")
def on_startup() -> None:
    init_schema()
    _seed_admin()
    logger.info("Backend startup complete")
