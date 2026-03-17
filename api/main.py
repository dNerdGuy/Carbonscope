"""CarbonScope Platform — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.config import ALLOWED_ORIGINS, ENV, REQUIRE_SMTP_IN_PRODUCTION
from api.database import get_db, get_db_pool_status, init_db
from api.deps import require_admin
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
from api.routes.stripe_routes import router as stripe_router
from api.routes.pcaf_routes import router as pcaf_router
from api.routes.review_routes import router as review_router
from api.routes.mfa_routes import router as mfa_router
from api.routes.benchmark_routes import router as benchmark_router
from api.routes.events_routes import router as events_router

from api import __version__ as APP_VERSION

logger = logging.getLogger(__name__)

_start_time: float = 0.0
_metrics_lock = threading.Lock()
_request_count: int = 0
_request_errors: int = 0
_status_counts: dict[int, int] = {}


def _validate_production_smtp() -> None:
    """Validate SMTP policy at startup for production mode."""
    if ENV != "production":
        return

    smtp_configured = bool(
        os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD")
    )
    if smtp_configured:
        return

    msg = "SMTP not configured in production"
    if REQUIRE_SMTP_IN_PRODUCTION:
        raise RuntimeError(f"{msg}; set SMTP_HOST/SMTP_USER/SMTP_PASSWORD")
    logger.warning("%s — email notifications will be disabled", msg)


async def _check_redis_health() -> str:
    """Return Redis health state for /health endpoint."""
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        return "not_configured"

    try:
        from redis.asyncio import from_url

        client = from_url(redis_url)
        try:
            await asyncio.wait_for(client.ping(), timeout=1.0)
            return "connected"
        finally:
            close = getattr(client, "aclose", None)
            if callable(close):
                await close()
            else:
                close = getattr(client, "close", None)
                if callable(close):
                    await close()
    except Exception:
        return "unavailable"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables (dev only), start scheduler. Shutdown: stop scheduler."""
    if ENV != "production":
        # In production, use Alembic migrations instead of create_all
        await init_db()
    global _start_time
    _start_time = time.monotonic()
    logger.info("CarbonScope API %s started (env=%s)", APP_VERSION, ENV)

    _validate_production_smtp()

    from api.services.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    yield
    await stop_scheduler()


# Disable OpenAPI/Swagger UI in production (information-disclosure risk)
_docs_url = None if ENV == "production" else "/docs"
_redoc_url = None if ENV == "production" else "/redoc"
_openapi_url = None if ENV == "production" else "/openapi.json"

app = FastAPI(
    title="CarbonScope Platform API",
    description="Decentralized corporate carbon emission estimation powered by Bittensor",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Custom middleware (request ID, security headers, global error handler)
register_middleware(app)

# CORS — configurable origins with restricted methods/headers
if "*" in ALLOWED_ORIGINS:
    logger.warning(
        "CORS: wildcard origin ('*') is configured. Disabling allow_credentials to prevent insecure configuration."
    )
    _allow_credentials = False
else:
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-CSRF-Token"],
    expose_headers=["X-Request-ID", "X-Total-Count"],
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
app.include_router(stripe_router, prefix="/api/v1")
app.include_router(pcaf_router, prefix="/api/v1")
app.include_router(review_router, prefix="/api/v1")
app.include_router(mfa_router, prefix="/api/v1")
app.include_router(benchmark_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")


@app.get("/health/live")
async def health_live():
    """Liveness probe — always 200 if the process is running."""
    return {"status": "alive"}


@app.get("/health")
async def health():
    """Readiness probe — checks DB connectivity (no sensitive details)."""
    from sqlalchemy import text as sa_text

    db_ok = False
    try:
        async for session in get_db():
            await session.execute(sa_text("SELECT 1"))
            db_ok = True
            break
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "version": APP_VERSION,
    }


@app.get("/health/detail")
async def health_detail(_admin=Depends(require_admin)):
    """Detailed health check — admin-only. Exposes infrastructure status."""
    from sqlalchemy import text as sa_text

    checks: dict[str, str] = {}
    try:
        async for session in get_db():
            await session.execute(sa_text("SELECT 1"))
            break
        checks["database"] = "connected"
    except Exception:
        checks["database"] = "unavailable"

    smtp_host = os.getenv("SMTP_HOST", "")
    checks["email"] = "configured" if smtp_host else "not_configured"

    from api.config import ESTIMATION_MODE, BT_NETWORK
    checks["bittensor"] = f"{ESTIMATION_MODE}/{BT_NETWORK}"
    checks["db_pool"] = get_db_pool_status()
    checks["redis"] = await _check_redis_health()

    all_ok = checks["database"] == "connected" and checks["redis"] != "unavailable"
    return {"status": "ok" if all_ok else "degraded", "version": APP_VERSION, **checks}


@app.middleware("http")
async def _count_requests(request: Request, call_next):
    global _request_count, _request_errors
    with _metrics_lock:
        _request_count += 1
    response = await call_next(request)
    with _metrics_lock:
        status_bucket = response.status_code
        _status_counts[status_bucket] = _status_counts.get(status_bucket, 0) + 1
        if response.status_code >= 500:
            _request_errors += 1
    return response


@app.get("/metrics")
async def metrics(
    request: Request,
    _admin=Depends(require_admin),
):
    """Operational metrics endpoint.
    Returns Prometheus text format when Accept header contains 'text/plain'
    or PROMETHEUS_ENABLED is set, otherwise JSON."""
    uptime = time.monotonic() - _start_time if _start_time else 0

    accept = request.headers.get("accept", "")
    prometheus = (
        "text/plain" in accept
        or os.getenv("PROMETHEUS_ENABLED", "false").lower() in ("true", "1")
    )

    if prometheus:
        lines = [
            "# HELP carbonscope_uptime_seconds Seconds since API started.",
            "# TYPE carbonscope_uptime_seconds gauge",
            f"carbonscope_uptime_seconds {uptime:.1f}",
            "# HELP carbonscope_requests_total Total HTTP requests.",
            "# TYPE carbonscope_requests_total counter",
            f"carbonscope_requests_total {_request_count}",
            "# HELP carbonscope_errors_total Total HTTP 5xx responses.",
            "# TYPE carbonscope_errors_total counter",
            f"carbonscope_errors_total {_request_errors}",
            "# HELP carbonscope_http_requests_by_status HTTP requests by status code.",
            "# TYPE carbonscope_http_requests_by_status counter",
        ]
        for code, count in sorted(_status_counts.items()):
            lines.append(f'carbonscope_http_requests_by_status{{status="{code}"}} {count}')
        lines.append(f"# HELP carbonscope_info Application version info.")
        lines.append(f"# TYPE carbonscope_info gauge")
        lines.append(f'carbonscope_info{{version="{APP_VERSION}",env="{ENV}"}} 1')
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    return {
        "uptime_seconds": round(uptime, 1),
        "total_requests": _request_count,
        "total_errors": _request_errors,
        "status_codes": dict(sorted(_status_counts.items())),
        "version": APP_VERSION,
    }
