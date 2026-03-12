"""CarbonScope Platform — FastAPI application entry point."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.config import ALLOWED_ORIGINS, ENV
from api.database import get_db, init_db
from api.limiter import limiter
from api.middleware import register_middleware
from api.routes.auth_routes import router as auth_router
from api.routes.company_routes import router as company_router
from api.routes.carbon_routes import router as carbon_router
from api.routes.ai_routes import router as ai_router
from api.routes.supply_chain_routes import router as supply_chain_router
from api.routes.compliance_routes import router as compliance_router
from api.routes.webhook_routes import router as webhook_router
from api.routes.audit_routes import router as audit_router
from api.routes.questionnaire_routes import router as questionnaire_router
from api.routes.scenario_routes import router as scenario_router
from api.routes.billing_routes import router as billing_router
from api.routes.alert_routes import router as alert_router
from api.routes.marketplace_routes import router as marketplace_router

logger = logging.getLogger(__name__)

_start_time: float = 0.0
_request_count: int = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables (dev only), start scheduler. Shutdown: stop scheduler."""
    if ENV != "production":
        # In production, use Alembic migrations instead of create_all
        await init_db()
    global _start_time
    _start_time = time.monotonic()
    logger.info("CarbonScope API v0.7.0 started (env=%s)", ENV)

    from api.services.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    yield
    await stop_scheduler()


app = FastAPI(
    title="CarbonScope Platform API",
    description="Decentralized corporate carbon emission estimation powered by Bittensor",
    version="0.7.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Custom middleware (request ID, security headers, global error handler)
register_middleware(app)

# CORS — configurable origins with restricted methods/headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

# Routes
app.include_router(auth_router, prefix="/api/v1")
app.include_router(company_router, prefix="/api/v1")
app.include_router(carbon_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(supply_chain_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(webhook_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(questionnaire_router, prefix="/api/v1")
app.include_router(scenario_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(alert_router, prefix="/api/v1")
app.include_router(marketplace_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check — tests DB connectivity."""
    from sqlalchemy import text as sa_text

    db_ok = True
    try:
        async for session in get_db():
            await session.execute(sa_text("SELECT 1"))
            break
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": "0.7.0",
        "database": "connected" if db_ok else "unavailable",
    }


@app.middleware("http")
async def _count_requests(request: Request, call_next):
    global _request_count
    _request_count += 1
    return await call_next(request)


@app.get("/metrics")
async def metrics():
    """Basic operational metrics."""
    uptime = time.monotonic() - _start_time if _start_time else 0
    return {
        "uptime_seconds": round(uptime, 1),
        "total_requests": _request_count,
        "version": "0.7.0",
    }
