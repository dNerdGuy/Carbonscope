# Changelog

All notable changes to CarbonScope are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.17.0] — 2026-03-13 — Phase 22: Completion & Polish

### Added — Frontend

- Responsive card layout for `DataTable` on mobile (`<640px`) — stacked label/value pairs replacing table rows.
- Copy-to-clipboard with "Copied!" toast feedback on webhook URLs in settings page.
- URL query state sync on marketplace page (`?industry=&region=`) and scenarios page (`?status=`).
- Status filter dropdown on scenarios page (draft/computed/archived).
- `listScenarios` API client now supports `status` parameter.

### Added — Documentation

- Bittensor economic model docs in README — TAO earning mechanics, 4-axis scoring table, reward optimization tips, validator economics.
- Local Subtensor testnet deployment guide in README — step-by-step for offline development.

### Added — Testing & Infrastructure

- E2E Playwright test scaffolding — `playwright.config.ts`, smoke tests (login, register, navigation), protected route redirect tests.
- Bittensor subnet load/stress test script (`scripts/load_test_subnet.py`) — synapse + HTTP modes, latency percentiles, ramp-up support.

---

## [0.16.0] — 2026-03-13 — Phase 18–21: Frontend Polish, Infrastructure, Protocol & Docs

### Added — Frontend Polish (Phase 18)

- Skeleton loading states across 6 pages (dashboard, reports/[id], recommendations, marketplace, seller, alerts) and DataTable component.
- Lazy-loaded `ScopeChart` via `next/dynamic` on dashboard and report detail pages.
- Real-time form validation on registration page (email, password, confirmPassword).
- Accessibility: `htmlFor`/`id` on all 16 upload page inputs; `sr-only` labels and `aria-label` on reports page sort/filter controls.
- CSS variable theming for ScopeChart tooltips (`var(--card)`, `var(--card-border)`, `var(--muted)`).

### Added — Infrastructure Hardening (Phase 19)

- `k8s/hpa.yaml` — HorizontalPodAutoscaler for backend (2–8 replicas) and frontend (2–4 replicas).
- `k8s/pdb.yaml` — PodDisruptionBudget (minAvailable: 1) for both deployments.
- `k8s/network-policy.yaml` — Default deny ingress + allow rules for backend, frontend, postgres, redis.
- `k8s/resource-quota.yaml` — Namespace quotas (8 CPU / 8Gi requests, 16 CPU / 16Gi limits, 30 pods).
- Trivy vulnerability scan step in CI (CRITICAL+HIGH, exit-code 1).
- `/tmp` emptyDir volumes on both deployments for `readOnlyRootFilesystem` compatibility.
- HA documentation section in `k8s/README.md`.

### Added — Bittensor Protocol Polish (Phase 20)

- `request_hash` field on CarbonSynapse with SHA-256 `compute_request_hash()` method.
- Scoring weight sum assertion at module level.
- Configurable CLI params: validator (`--ema_alpha`, `--circuit_breaker_*`), miner (`--rate_limit_max`, `--rate_limit_window`).
- `log_dataset_versions()` — logs emission factor file sizes at miner startup.
- 5 new industry field weight profiles (energy, financial_services, construction, food_beverage, healthcare).

### Fixed — Bittensor Protocol (Phase 20)

- Zero-score miners now receive explicit weight 0 instead of uniform equal weights.

### Added — Documentation & Testing (Phase 21)

- API versioning strategy section in `API.md` (URL path versioning, 6-month deprecation window).
- Kubernetes deployment runbook in `DEPLOYMENT.md` (initial deploy, rolling update, monitoring, troubleshooting).
- Incident response procedure in `SECURITY.md` (P0–P3 severity levels, response steps, communication protocol).
- Updated `SECURITY.md` supported versions table.
- 9 new tests: webhook retry exhaustion (4), marketplace email resilience (1), LLM extraction fallback (4).

### Changed

- Backend readiness probe `initialDelaySeconds` bumped from 10 to 30.
- Version bumped to **0.16.0** across `api/main.py`, `pyproject.toml`, `setup.py`, `README.md`, `API.md`, CI.

---

## [0.15.0] — 2026-03-13 — Phase 15+16: Backend Bug Fixes & Bittensor Hardening

### Fixed

- **Credit deduction timing**: Moved deduction to post-success (was pre-execution). All 6 credit-gated routes updated.
- **Webhook pagination**: Pushed LIMIT/OFFSET into SQL query; `list_webhooks` now returns `tuple[list, int]`.
- **Thread-safe lazy init**: Added `threading.Lock` + double-checked locking in `llm_parser.py` and `subnet_bridge.py`.
- **Bare except blocks**: Narrowed to specific exceptions in `webhooks.py`, `email_async.py`, `marketplace_routes.py`.
- **Import order**: Fixed `from __future__` import position in `scope1.py`.

### Added

- Rate limits on billing subscription (5/min) and Stripe webhook (60/min).
- `aiosmtplib>=3.0.0` dependency.
- SMTP configuration warning at startup in production.
- Miner input validation via Pydantic (`QuestionnaireInput`, `ProvidedDataInput`) with field bounds and whitelists.
- Miner error classification: `ValidationError` → confidence=-1.0, internal error → confidence=-2.0.
- Synapse field validators: confidence clamping, emissions floor, breakdown key filtering.
- Per-hotkey rate limiting on miner (10 requests / 60s per validator).
- Miner registration verification at startup.
- Validator dendrite query retry with exponential backoff (3 attempts).
- Weight setting retry (3 attempts with 1s/2s/4s delays).
- EMA score persistence to JSON file (loaded on startup, saved on each update).
- Silent fallback logging in `scope1.py` (3 sites) and `loader.py` (1 site).
- Pinned `bittensor==10.1.0` in `pyproject.toml`.
- 37 new unit tests: `test_miner.py` (20 tests) and `test_validator.py` (17 tests).

---

## [0.14.0] — 2026-03-14 — Phase 14: Final Production Polish

### Added

- **Expired token cleanup scheduler** — new `_run_token_cleanup` background task purges expired rows from `revoked_tokens`, `refresh_tokens`, and `password_reset_tokens` tables daily with distributed locking
- **Redis in dev docker-compose** — `docker-compose.yml` now includes a `redis:7-alpine` service with healthcheck; backend receives `REDIS_URL` for rate limiting and scheduler locks in local dev
- **Phase 13–14 test suite** — `test_phase13_14_hardening.py` covers Redis limiter config, scheduler `_acquire_lock` (with/without Redis, error fallback), `RequestIDFilter` contextvar injection, `JSONFormatter` request_id output, `confidence.improved` webhook dispatch, token cleanup logic, and database index verification

### Fixed

- **API.md stale version references** — all `"version": "0.8.0"` refs updated to current release
- **`redis` missing from requirements** — added `redis==5.2.1` to `requirements.txt` and `redis>=5.0.0` to `pyproject.toml` / `setup.py`
- **Redundant `sa_select` import** in `carbon_routes.py` — removed duplicate import, now uses top-level `select`
- **OpenAPI docs exposed in production** — `/docs`, `/redoc`, and `/openapi.json` now disabled when `APP_ENV=production`

### Changed

- `api/services/scheduler.py` — imports `RefreshToken`, `RevokedToken`, `PasswordResetToken`; adds fourth background task for token cleanup
- `setup.py` — dependency list fully synced with `pyproject.toml`
- Version bumped to **0.14.0** across `api/main.py`, `pyproject.toml`, `setup.py`, `README.md`, `API.md`, `.github/workflows/ci.yml`

---

## [0.13.0] — 2026-03-13 — Phase 13: Production Hardening

### Added

- **Redis-backed rate limiting** — `slowapi.Limiter` now uses `REDIS_URL` as `storage_uri` when available, sharing rate limit state across all replicas; falls back to in-memory for local development
- **Scheduler distributed locking** — background tasks (alert checks, credit resets, webhook retries) acquire a Redis advisory lock before executing, preventing duplicate runs across replicas
- **Request ID log correlation** — all log records now include `request_id` via a `contextvars`-based `RequestIDFilter`, threaded through both JSON and plaintext formatters; set by `RequestIDMiddleware` on every request
- **Database performance indexes** — Alembic migration `f3a4b5c6d7e8` adds `ix_users_company_id`, `ix_audit_logs_created_at`, `ix_credit_ledger_created_at`, `ix_alerts_created_at` for production query performance
- **`confidence.improved` webhook event** — automatically dispatched when a new emission report has higher confidence than the previous report for the same company and year, including `old_confidence`, `new_confidence`, and `improvement` delta

### Changed

- `api/logging_config.py` — dev log format now includes `[%(request_id)s]` placeholder; `RequestIDFilter` added before `SensitiveFilter`
- `api/middleware.py` — `RequestIDMiddleware` now sets `request_id_var` contextvar alongside `request.state.request_id`

---

## [0.12.0] — 2026-03-13 — Phase 12: Production Infrastructure & Testing

### Added

- **PostgreSQL CI integration tests** — GitHub Actions `test` job now spins up a PostgreSQL 16 service container and runs the full test suite against both SQLite and PostgreSQL, plus validates Alembic migrations against both databases
- **Kubernetes deployment manifests** — complete `k8s/` directory with Namespace, ConfigMap, Secrets, PVC-backed PostgreSQL and Redis, backend (2 replicas with init-container for migrations), frontend (2 replicas), and NGINX Ingress with TLS via cert-manager
- **OpenTelemetry distributed tracing** — optional tracing via `OTEL_EXPORTER_OTLP_ENDPOINT` env var; instruments FastAPI and SQLAlchemy with OTLP gRPC exporter, service name/version/environment resource attributes
- **Frontend page-level tests** — 4 new test files (LoginPage, DashboardPage, RecommendationsPage, SellerDashboardPage) covering form submission, API data rendering, empty states, error handling, and navigation — total frontend tests now 82 across 14 files
- **Optional dependency comments** in `requirements.txt` for `sentry-sdk` and OpenTelemetry packages with pinned versions

### Changed

- `pyproject.toml` version synced to `0.12.0` (was stuck at `0.8.0`)
- README version badge updated to `0.12.0`
- README now includes Kubernetes deployment section

---

## [0.11.0] — 2026-03-13 — Phase 11: Enterprise Hardening & Observability

### Added

- **Sentry APM integration** — optional error tracking and performance monitoring via `SENTRY_DSN` env var, with FastAPI and SQLAlchemy integrations, configurable trace sampling (`SENTRY_TRACES_SAMPLE_RATE`), PII scrubbing enabled by default
- **Docker healthchecks** — `HEALTHCHECK` directives in both backend (Python urllib) and frontend (wget) Dockerfile stages; Nginx service in `docker-compose.prod.yml` now has healthcheck (`wget --spider` on port 80)
- **`safety` scanner** added to CI security job alongside pip-audit and bandit
- **Frontend build step** added to CI pipeline — `npm run build` now runs after lint and tests to catch build errors before merge
- **Operations runbook** in README — backup/recovery procedures, database migration commands, monitoring setup (Prometheus/Grafana), Sentry configuration, scaling strategies, and incident response checklist

### Fixed

- Removed unused `JSONResponse` import from `api/main.py`
- README version badge updated to 0.10.0 (was stale at 0.8.0)
- README changelog pointer updated to reference current version

### Changed

- `.env.example` — added `SENTRY_DSN` and `SENTRY_TRACES_SAMPLE_RATE` variables
- `APP_VERSION` bumped to `0.11.0`

---

## [0.10.0] — 2026-03-13 — Phase 10: Frontend Polish & Webhook Coverage

### Added

- **Dark mode / light mode toggle** — persistent theme switcher in navbar with `ThemeProvider` context, `localStorage` persistence, system preference detection, and full light-mode CSS variables (`[data-theme="light"]`). All existing CSS variables adapt automatically.
- **Error boundaries on all detail routes** — added `error.tsx` for `reports/[id]`, `marketplace/seller`, `questionnaires/[id]`, and `recommendations/[reportId]` (previously only top-level routes had them)
- **Webhook event dispatches** — wired 3 of 4 missing webhook event types:
  - `supply_chain.link_created` — fires when a supplier is added
  - `supply_chain.link_verified` — fires when a link status is set to "verified"
  - `estimate.completed` — fires alongside `report.created` with confidence data

### Changed

- `.input` CSS class now uses `var(--card)` background instead of hardcoded dark hex, enabling proper light mode support

---

## [0.9.1] — 2026-03-14 — Phase 9: Frontend Features & Test Coverage

### Added

- **PDF export button** on report detail page — one-click download of any emission report as PDF via `exportReportPdf()` API client
- **Marketplace seller dashboard page** — `/marketplace/seller` frontend page shows revenue summary (total credits, sales count, active listings) and paginated sales table
- **Marketplace seller API client** — `getMyMarketplaceSales()` and `getMyMarketplaceRevenue()` functions with full TypeScript types (`SellerRevenue` interface)
- **Seller dashboard link** on main marketplace page for easy navigation
- **Stripe webhook unit tests** — signature verification tests (valid, missing secret, stale timestamp, wrong signature) plus endpoint integration tests (503 when unconfigured, 400 on invalid sig, 200 on unhandled event)
- **Marketplace seller endpoint tests** — `TestMarketplaceSeller` class covering empty sales, empty revenue, revenue with active listing, and pagination params

### Fixed

- `APP_VERSION` bumped to `0.9.0` in `api/main.py` to match the v0.9.0 changelog entry

---

## [0.9.0] — 2026-03-13 — Phase 8: DevOps, Observability & Integrations

### Added

- **Prometheus metrics** — `/metrics` endpoint now returns Prometheus text format (with `Accept: text/plain` or `PROMETHEUS_ENABLED=true`), including `carbonscope_uptime_seconds`, `carbonscope_requests_total`, `carbonscope_errors_total`, `carbonscope_http_requests_by_status`, and `carbonscope_info`
- **Stripe webhook routes** — `POST /api/v1/stripe/webhooks` handles `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`, and `checkout.session.completed` events with HMAC-SHA256 signature verification and replay protection
- **Marketplace seller dashboard** — `GET /api/v1/marketplace/my-sales` lists purchases of your listings; `GET /api/v1/marketplace/my-revenue` returns total revenue, sales count, and active listing count
- **Marketplace email notifications** — Buyer receives purchase confirmation email; seller receives sale notification email on each marketplace transaction
- **Recommendations index page** — `/recommendations` frontend page lists all reports and links to per-report reduction recommendations
- **Nginx reverse proxy** — Production docker-compose now includes Nginx with TLS termination, HTTP→HTTPS redirect, rate limiting, and security headers
- **Redis** service in production docker-compose for distributed rate limiting and caching
- **CI/CD Docker push** — GitHub Actions now builds and pushes images to GitHub Container Registry (`ghcr.io`) with SHA, branch, and semver tagging via Docker Buildx with GHA cache
- **Release automation** — GitHub Release auto-created on version tags (`v*`)
- `.env.example` updated with `REDIS_URL` and `PROMETHEUS_ENABLED` variables

### Fixed

- Version mismatch — `/health` and `/metrics` endpoints now report the correct application version via `APP_VERSION` constant instead of hardcoded strings

### Improved

- Metrics endpoint now tracks per-status-code request counts and 5xx error totals
- Production deployment: backend and frontend no longer expose ports directly; all traffic routes through Nginx

---

## [0.8.0] — 2026-02-15 — Phase 7: Frontend Quality

### Added

- **ConfirmDialog** component wired into all delete actions (reports, uploads, questionnaires, scenarios, supply chain links, webhooks)
- **Breadcrumbs** component on all detail pages for improved navigation
- **FormField** component applied across all auth pages (login, register, forgot-password, reset-password)
- **Error boundaries** added to 5 key routes for graceful error handling
- 7 new frontend tests (ConfirmDialog, Breadcrumbs, FormField interactions)

### Improved

- Consistent delete confirmation UX across the entire dashboard
- Navigation experience with breadcrumb trails on nested pages
- Form field accessibility with label associations and error display

---

## [0.7.0] — 2026-01-20 — Phase 6: Business Logic & GDPR

### Added

- **Credit gating** for all paid operations (estimate, PDF export, questionnaire extraction, scenario compute)
- **Credit ledger** endpoint with paginated transaction history
- **GDPR account deletion** — soft-delete user account via `DELETE /auth/me`
- **Pagination** across all listing endpoints with consistent `{items, total, limit, offset}` response format
- `CreditLedger` model with `balance_after >= 0` CHECK constraint
- Business logic tests for credit deduction race conditions

### Fixed

- Credit balance can no longer go negative under concurrent requests
- Pagination defaults applied consistently across all route modules

---

## [0.6.0] — 2025-12-10 — Phase 5: Security & Auth Hardening

### Added

- **Admin RBAC** — `require_admin()` dependency for admin-only endpoints
- **Cookie-based authentication** — httpOnly `access_token` cookie alongside Bearer token
- **CSRF protection** — Double-submit cookie pattern (`X-CSRF-Token` header vs. `csrf_token` cookie)
- **SSRF protection** — URL validation on webhook URLs (block private/internal IPs)
- **Rate limiter proxy awareness** — Honor `X-Forwarded-For` when `TRUST_PROXY=true`
- **Password strength validation** — Minimum 8 characters with complexity requirements
- `RevokedToken` model for JWT blacklisting on logout
- `PasswordResetToken` model with 15-minute expiry
- `RefreshToken` model with single-use rotation

### Security

- Access tokens revoked on logout via JTI-based blacklist
- Refresh tokens are single-use (consumed and replaced on each refresh)
- Password reset tokens expire after 15 minutes and are single-use
- Account lockout after 5 failed login attempts (15-minute lock)

---

## [0.5.0] — 2025-11-01 — Phase 4: Enum & Validation Polish

### Added

- Enum type refinements for model fields (industry, region, plan, role)
- Stricter Pydantic validators for request schemas
- Improved password strength checks with informative error messages

### Fixed

- Enum consistency between SQLAlchemy models and Pydantic schemas
- Edge cases in validation for edge-case inputs

---

## [0.4.0] — 2025-09-15 — Phase 3: Soft Delete & Constraints

### Added

- **Soft delete** via `deleted_at` timestamp across all major models (DataUpload, EmissionReport, Questionnaire, Scenario, SupplyChainLink)
- **CHECK constraints** on database models:
  - `EmissionReport`: `scope1 >= 0`, `scope2 >= 0`, `scope3 >= 0`, `0.0 <= confidence <= 1.0`
  - `CreditLedger`: `balance_after >= 0`
  - `Subscription`: unique per company
- **JSON structured logging** — auto-enabled in production (`LOG_JSON=true`)

### Changed

- All `DELETE` endpoints now perform soft-delete instead of hard delete
- List queries automatically exclude soft-deleted records

---

## [0.3.0] — 2025-08-01 — Phase 2: CRUD & Retry Improvements

### Added

- **Data upload PATCH** endpoint for updating operational data
- **Report PATCH** endpoint for updating year and notes
- **Webhook toggle** endpoint (enable/disable without deleting)
- Retry logic for Bittensor subnet queries (3 attempts with exponential backoff)
- Improved error messages for CRUD validation failures

### Fixed

- Data upload validation for missing required fields
- Retry behavior on Bittensor network timeout

---

## [0.2.0] — 2025-06-15 — Phase 1: Auth Hardening

### Added

- **Refresh token rotation** — Single-use refresh tokens with automatic rotation
- **Password reset flow** — `POST /auth/forgot-password` + `POST /auth/reset-password`
- **Token revocation** — Access tokens can be revoked on logout
- **Account lockout** — 5 failed login attempts triggers 15-minute lockout
- Async email service (`aiosmtplib`) for password reset notifications
- `RefreshToken`, `RevokedToken`, `PasswordResetToken` database models
- Alembic migration for auth hardening tables

---

## [0.1.0] — 2025-05-01 — Initial Release

### Added

- **Bittensor subnet** — `CarbonSynapse` protocol, miner, and validator
- **5-axis scoring engine** — Accuracy (40%), GHG Compliance (25%), Completeness (15%), Anti-Hallucination (15%), Benchmark (5%)
- **8 emission factor datasets** — EPA, eGRID, IEA, DEFRA, GLEC, IPCC AR6, industry averages
- **Scope 1/2/3 calculation engines** — Activity-based with gap-filling for Scope 3
- **FastAPI backend** — 75+ endpoints across 13 route modules
- **Authentication** — JWT with bcrypt password hashing
- **Company management** — Company CRUD, data upload with pagination
- **Carbon estimation** — Local engine and Bittensor subnet bridge
- **AI features** — LLM text parsing, emission prediction, audit trail generation, reduction recommendations
- **Questionnaires** — Document upload (PDF/DOCX/XLSX/CSV), AI extraction, human review, PDF export
- **5 templates** — CDP Climate Change, EcoVadis, TCFD, GHG Protocol Inventory, CSRD/ESRS
- **What-if scenarios** — Parameter-based scenario builder with compute engine
- **Supply chain** — Buyer↔supplier linking, Scope 3 Category 1 aggregation, verification workflow
- **Compliance reporting** — GHG Protocol, CDP, TCFD, SBTi report generation
- **Billing** — Free/Pro/Enterprise tiers, credit ledger, monthly grants
- **Alerts** — Automated emission monitoring with acknowledgement
- **Data marketplace** — Anonymized data listings, credit-based purchasing
- **Webhooks** — HMAC-SHA256 signed payloads, delivery logs, exponential-backoff retries
- **Audit logging** — Action audit trail with filtering
- **Middleware** — Request ID tracing, structured logging, security headers (CSP, HSTS, X-Frame-Options)
- **Rate limiting** — IP-based (10/min auth, 60/min default)
- **Next.js 15 dashboard** — 18 pages, 8 components, typed API client
- **Database** — 19 SQLAlchemy models, Alembic migrations, async PostgreSQL + SQLite support
- **Docker** — Multi-stage Dockerfile, development + production Compose files
- **Tests** — 491+ backend tests, 65+ frontend tests
- **Documentation** — README, Architecture, API Reference, Deployment Guide
