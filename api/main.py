"""CarbonScope Platform — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.config import ALLOWED_ORIGINS
from api.database import get_db, init_db
from api.limiter import limiter
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

logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables. Shutdown: no-op."""
    await init_db()
    logger.info("CarbonScope API v0.4.0 started")
    yield


app = FastAPI(
    title="CarbonScope Platform API",
    description="Decentralized corporate carbon emission estimation powered by Bittensor",
    version="0.4.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — configurable origins with restricted methods/headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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
        "version": "0.4.0",
        "database": "connected" if db_ok else "unavailable",
    }
