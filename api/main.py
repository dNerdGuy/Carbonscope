"""CarbonScope Platform — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import init_db
from api.routes.auth_routes import router as auth_router
from api.routes.company_routes import router as company_router
from api.routes.carbon_routes import router as carbon_router
from api.routes.ai_routes import router as ai_router
from api.routes.supply_chain_routes import router as supply_chain_router
from api.routes.compliance_routes import router as compliance_router
from api.routes.webhook_routes import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables. Shutdown: no-op."""
    await init_db()
    yield


app = FastAPI(
    title="CarbonScope Platform API",
    description="Decentralized corporate carbon emission estimation powered by Bittensor",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS — allow Next.js frontend in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth_router, prefix="/api/v1")
app.include_router(company_router, prefix="/api/v1")
app.include_router(carbon_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(supply_chain_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(webhook_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}
