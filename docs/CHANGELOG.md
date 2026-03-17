# Changelog

All notable changes to CarbonScope are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.23.2] — 2026-03-16 — Patch: Release Metadata Version Synchronization

### Fixed

- Synchronized backend/runtime version identifiers to `0.23.2` across:
  - `pyproject.toml` project version
  - `setup.py` package version
  - `api/__init__.py` runtime `__version__`

### Notes

- This patch ensures tagged release metadata and runtime-reported version remain consistent.

## [0.23.1] — 2026-03-16 — Maintenance: Frontend Test Formatting, Docs & Git Hygiene

### Changed

- Reformatted frontend Playwright and unit test files for consistent style and readability.
- Reformatted frontend auth/validation utility signatures to improve line-wrapping consistency.
- Refreshed README environment variable table formatting for clearer presentation.

### Added

- Repository ignore rules for generated frontend artifacts (`playwright-report/`, `test-results/`, `tsconfig.tsbuildinfo`) to keep commits clean.

### Validation

- Frontend lint: passed.
- Frontend unit tests: 147/147 passed.
- Frontend E2E tests: 132/132 passed.

## [0.23.0] — 2026-03-15 — Phases 50–59: Audit Hardening & Frontend Security

### Fixed — Phase 50: Bittensor Critical Fixes

- Atomic score persistence with file-rename in validator
- Circuit breaker auto-reset after recovery window
- EMA alpha validation (0 < α ≤ 1)
- Hotkey deregistration detection in miner
- Non-mutating Pydantic field validators in protocol
- Request hash computation on CarbonEstimateRequest
- Bounded rate limiter with TTL-based cleanup

### Fixed — Phase 51: Auth Hardening

- JWT issuer claim validation on decode
- Audit log on profile update
- Consolidated double-commit patterns in auth routes

### Fixed — Phase 52: Model & Migration Hardening

- `updated_at` added to 8 models (DataUpload, EmissionReport, etc.)
- AuditLog.user_id CASCADE ondelete
- Indexes on DataPurchase.created_at, Scenario.company_id, SupplyChainLink.status, DataListing.seller_company_id
- Alembic migration k8l9m0n1o2p3

### Changed — Phase 53: Service Extraction

- Extracted audit `list_logs` and benchmark `list_benchmarks` to service layer
- Fixed MFA double-commit patterns

### Added — Phase 54: Rate Limiting & Validation

- Rate limiter decorators on 7 carbon_routes endpoints
- `PasswordChange.current_password` min_length validation

### Fixed — Phase 55: Paginated Response Consistency

- Supply chain `get_link` extracted to service layer
- Consistent paginated shape for suppliers/buyers endpoints

### Fixed — Phase 56: Frontend Security

- Removed `unsafe-eval` from CSP in next.config.js and nginx.conf
- Replaced `atob()` with `Buffer.from()` for cross-platform JWT decode
- Added Next.js middleware for route guards

### Changed — Phase 57: Schema & Validation Tightening

- `UserRegister.company_name` strip validator rejects whitespace-only
- `MFA_PENDING_TOKEN_EXPIRE_MINUTES` configurable via environment
- `EMISSION_INCREASE_THRESHOLD` / `CONFIDENCE_DROP_THRESHOLD` configurable

### Fixed — Phase 58: K8s & Nginx Hardening

- TOTP_ENCRYPTION_KEY added to k8s/secrets.yaml template
- Warning comments on placeholder secrets
- IPv6 listen directives in nginx
- Auth header redaction map in nginx logging

### Changed — Phase 59: Version Bump

- Version bumped to 0.23.0

---

## [0.22.0] — 2026-03-15 — Phases 39–49: Code Quality, Security & Service Layer

### Fixed — Phase 39: Critical Backend Fixes

- **Thread-safe metrics**: `_request_count`/`_request_errors`/`_status_counts` protected by `threading.Lock`.
- **APP_VERSION from source**: `api/__init__.__version__` replaces hardcoded string.
- **Unauthenticated `/metrics`**: monitoring endpoint no longer requires JWT.
- **EmissionReport FK SET NULL**: `data_upload_id` foreign key uses `ondelete="SET NULL"`.
- **DRY password validator**: shared `_check_password_strength()` used by both registration schemas.
- Alembic migration `i6j7k8l9m0n1`.

### Changed — Phase 40: Service Layer Extraction

- **`api/services/carbon.py`**: extracted 8 functions from carbon_routes.py.
- **`api/services/company.py`**: extracted 7 functions from company_routes.py.
- **`api/services/ai.py`**: extracted 4 functions from ai_routes.py.
- **`ServiceError` base class** in `api/services/__init__.py` with `status_code`.
- `ReviewError` now inherits from `ServiceError`.
- All refactored routes use thin handler → `ServiceError` → `HTTPException` pattern.

### Added — Phase 41: CI/CD Completeness

- **`tsc --noEmit`** step in frontend CI job.
- **Playwright E2E** CI job with artifact upload on failure.
- **`.pre-commit-config.yaml`**: trailing-whitespace, ruff, frontend-lint, frontend-typecheck hooks.

### Changed — Phase 42: Documentation Sync

- SECURITY.md supported versions updated.
- CONTRIBUTING.md test counts: 729 backend, 142 frontend.
- API.md: Stripe Webhooks section added.
- `.env.example`: `VALIDATOR_SCORES_PATH` added.

### Added — Phase 43: Performance Indexes & Schema Hardening

- Database indexes on `WebhookDelivery.status_code`, `PasswordResetToken.email`, `DataReview.status`.
- JSON depth validator (`_check_json_depth`) on `DataUploadCreate.provided_data` and `ScenarioCreate.parameters`.
- Alembic migration `j7k8l9m0n1o2`.

### Added — Phase 44: GitHub Templates

- `CODEOWNERS`, `PULL_REQUEST_TEMPLATE.md`, issue templates (`bug.yml`, `feature.yml`).

### Changed — Phase 45: pyproject.toml Sync

- Tightened all dependency minimum version bounds to match requirements.txt pinned versions.

### Added — Phase 46: Security Headers

- `Cross-Origin-Embedder-Policy: require-corp` header.
- `Cross-Origin-Opener-Policy: same-origin` header.
- `X-Permitted-Cross-Domain-Policies: none` header.

### Changed — Phase 47: Service Extraction (Scenario & Marketplace)

- Moved scenario CRUD (create/list/get/update/delete) to `api/services/scenarios.py`.
- Added `ScenarioError(ServiceError)` for consistent error propagation.
- Added `get_listing_by_id()` to marketplace service; removed inline query from route.

### Changed — Phase 48: Schema Validation Hardening

- `max_length=2000` on all free-text input fields: description (DataListingCreate, ScenarioCreate, ScenarioUpdate), notes (DataUploadCreate, DataUploadUpdate, ReportUpdate, SupplyChainLinkCreate, DataReviewAction, FinancedAssetCreate).

---

## [0.21.0] — 2026-03-14 — Phases 27–32: Security, Services, Coverage & Infrastructure

### Added — Phase 27: Security Hardening & Data Integrity

- **TOTP encryption at rest**: MFA secrets encrypted via Fernet (TOTP_ENCRYPTION_KEY) before storage; decrypted on verify/validate/disable.
- **`updated_at` column** on User model (auto-updates on write).
- **CASCADE deletes** on all 16 company-referencing ForeignKeys (subscription, credits, webhooks, reports, uploads, etc.).
- **Soft delete** (`deleted_at`) on DataListing and Webhook models.
- **Database indexes** on `data_reviews.report_id` and `webhook_deliveries.webhook_id`.
- **CORS safety check**: disables `allow_credentials` when origin is `*`.
- **Redis production gate**: rate limiter raises RuntimeError if REDIS_URL missing in production.
- **SECRET_KEY warning**: logs warning when key < 32 chars in non-production envs.
- Alembic migration `h5i6j7k8l9m0` for all schema changes.
- 10 new backend tests (test_phase27_security_hardening.py).

### Added — Phase 28: Service Layer Extraction

- **`api/services/reviews.py`**: extracted create_review, list_reviews, get_review, perform_action from review routes.
- **`api/services/benchmarks.py`**: extracted compare_to_industry, \_pct_diff, \_rank_label from benchmark routes.
- Refactored review_routes.py and benchmark_routes.py to delegate to service layer.
- 21 new backend tests (test_reviews_service.py: 11, test_benchmarks_service.py: 10).

### Added — Phase 29: Backend Test Coverage Gaps

- **test_pdf_export.py** (11 tests): direct tests for generate_report_pdf/generate_questionnaire_pdf.
- **test_url_validator.py** (20 tests): SSRF protection — scheme blocking, hostname blocking, private IP blocking, DNS resolution, IPv6 loopback.
- **test_templates.py** (10 tests): questionnaire template catalog — list, get, parametrized template retrieval.
- **Questionnaire endpoint gap tests**: apply_template (3 tests), update_question (4 tests) added to test_questionnaire_routes.py.

### Added — Phase 30: Frontend Test Expansion

- **7 new test files** (49+ new tests):
  - SettingsPage.test.tsx (7 tests): profile fields, company save, webhook section, password section.
  - UploadPage.test.tsx (5 tests): form rendering, submit/error, scope labels.
  - CompliancePage.test.tsx (5 tests): framework buttons, generate, error handling.
  - AlertsPage.test.tsx (7 tests): alert list, severity, run check, unread filter.
  - AuditLogsPage.test.tsx (6 tests): table rendering, empty state, error, accessibility.
  - QuestionnairesPage.test.tsx (6 tests): tabs, list, templates, apply template.
  - AuthContext.test.tsx (7 tests): JWT decoding, localStorage, login/logout/register flows, provider requirement.
- Frontend tests: **142 passed** (25 files), up from 99 (18 files).

### Added — Phase 31: Frontend Infrastructure

- **Security headers** in next.config.js: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, Strict-Transport-Security, Content-Security-Policy.
- **E2E protected routes** expanded from 4 to 16 routes (all authenticated pages).

### Changed — Phase 32: Documentation Sync

- ARCHITECTURE.md: service layer table updated to 21 modules (added reviews, benchmarks, mfa).
- CHANGELOG.md: comprehensive entry for Phases 27–32.

### Test Summary

- Backend: **722 passed** (40+ files), up from 650.
- Frontend (vitest): **142 passed** (25 files), up from 99.
- E2E (playwright): 16 protected route checks + smoke tests.
- 7 pre-existing supply_chain_routes failures (cross-test contamination, pass individually).

---

## [0.20.0] — 2026-03-14 — Phase 26: MFA Enforcement, Race Conditions & Migrations

### Fixed — MFA Login Enforcement

- Login now checks MFA enrollment: if enabled, issues a short-lived `mfa_pending` token (5-min TTL) instead of full access tokens.
- `get_current_user` rejects `mfa_pending` tokens with HTTP 403 — users must complete MFA before accessing any endpoint.
- New `get_mfa_pending_user` dependency accepts only `mfa_pending` tokens for the `/auth/mfa/validate` endpoint.
- `/auth/mfa/validate` rewritten: accepts pending token + TOTP code, issues full access + refresh tokens, sets auth cookies.

### Fixed — Race Conditions

- **Registration**: duplicate email/username now caught via `IntegrityError` → HTTP 409 instead of 500.
- **Marketplace purchase**: duplicate purchase caught via `IntegrityError` → `ValueError` instead of crash.
- Credit deduction already safe (`SELECT FOR UPDATE`) — no change needed.

### Added — Alembic Migration

- Migration `g4h5i6j7k8l9` adds 5 Phase 24 tables: `financed_portfolios`, `financed_assets`, `data_reviews`, `mfa_secrets`, `industry_benchmarks` with full FKs, indexes, and constraints.

### Added — Frontend Tests

- 4 new test files (16 tests): PCAFPage, ReviewsPage, MFAPage, BenchmarksPage.
- Frontend tests: **99** passed (18 files), up from 83.

### Added — Backend Tests

- 7 new tests in `test_phase26_mfa_races.py`: MFA login enforcement (6), duplicate registration race (1).
- Fixed `test_mfa_validate_after_enable` to use new mfa_pending flow.
- Total backend tests: **647** (36 files). Total frontend tests: **99** (18 files).

---

## [0.19.0] — 2026-03-14 — Phase 25: Security Hardening & Frontend Parity

### Added — Audit Logging

- Audit trail on **all write operations**: register, login, MFA setup/verify/disable, PCAF create portfolio/add asset/delete asset, compliance report generation, review creation, admin credit grants, subscription updates.
- Consistent `audit.record()` + `db.commit()` pattern across 8 route modules.

### Added — Rate Limiting

- Rate limiting applied to **all 18 route modules** (previously only 5 had coverage).
- Added `@limiter.limit(RATE_LIMIT_DEFAULT)` + `Request` parameter to: company (7), supply chain (7), alert (3), webhook (5), AI (2), questionnaire (9), scenario (5), marketplace (7), audit (1) endpoints.
- Change-password endpoint now rate-limited.

### Fixed — Security

- **`/metrics` endpoint** gated behind authentication (was publicly accessible).
- **Webhook update** now requires admin role (`require_admin` instead of `get_current_user`).
- **Session invalidation**: password change and password reset now revoke all refresh tokens.
- **`/plans` endpoint** now requires authentication.
- Fixed critical `NameError` in carbon_routes.py — `logger` was used but never imported.

### Added — Frontend Pages

- **PCAF page** (`/pcaf`): Portfolio management, asset CRUD, summary metrics (total emissions, data quality, asset count).
- **Reviews page** (`/reviews`): Data review workflow with submit/approve/reject actions, status badges, create-from-report.
- **MFA page** (`/mfa`): MFA status display, TOTP setup flow (secret, backup codes), verify, disable.
- **Benchmarks page** (`/benchmarks`): Industry benchmarks comparison, peer ranking, industry selector.
- API client extended with PCAF (7 functions), Reviews (4), MFA (5), Benchmarks (2) and associated TypeScript interfaces.

### Added — Testing

- 26 new backend tests in `test_phase25_hardening.py`: auth gates (4), audit logging (5), session invalidation (1), webhook auth (1), cross-company isolation (2), rate limiting (11), PCAF audit (1), review audit (1).
- Total backend tests: **640** (35 files). Total frontend tests: 83 (14 files).

### Changed — Documentation

- Updated version badge, test counts, service counts, and page counts across README, ARCHITECTURE, CONTRIBUTING.
- Updated changelog with Phase 25 summary.

---

## [0.18.0] — 2026-03-14 — Phase 24: Competitive Feature Parity

### Added — Compliance Frameworks

- **CSRD (ESRS E1)** compliance report generator — transition plans (E1_1), emission reduction targets (E1_4), gross GHG emissions (E1_6), removals & offsets (E1_7), internal carbon pricing (E1_8), energy consumption (E1_9), intensity metrics (per employee, per $M revenue).
- **ISSB (IFRS S2)** compliance report generator — governance disclosures (paragraphs 6–7), strategy & risk/opportunity analysis (paragraph 10), risk management processes (paragraphs 25–26), cross-industry metrics (paragraph 29), emission reduction targets (paragraph 33).
- **SECR (UK)** compliance report generator — UK GHG emissions breakdown (Scope 1+2 total), energy consumption, mandatory intensity ratio, DEFRA/BEIS methodology, energy efficiency narrative.
- Compliance framework validation now accepts 7 frameworks: `ghg_protocol`, `cdp`, `tcfd`, `sbti`, `csrd`, `issb`, `secr`.

### Added — PCAF Financed Emissions

- `PCAFAssetClass` enum with 7 PCAF-defined asset classes (listed equity, corporate bonds, business loans, project finance, commercial real estate, mortgages, sovereign debt).
- `FinancedPortfolio` and `FinancedAsset` ORM models with automatic attribution factor and financed emissions calculation.
- PCAF calculation service (`api/services/pcaf.py`) — attribution factor, financed emissions, portfolio summary with weighted data quality scores and per-asset-class breakdown.
- 6 PCAF API endpoints: create/list portfolios, portfolio summary, add/list/delete assets.
- Pro/Enterprise plan gating on write operations; read operations available to all authenticated users.

### Added — Data Review & Approval Workflows

- `DataReview` model with `ReviewStatus` state machine (draft → submitted → approved/rejected, with resubmit from rejected).
- 4 review endpoints: create review, list reviews (with status filter), get review, perform action (submit/approve/reject).
- Admin-only approval/rejection with audit logging integration.
- Duplicate review prevention per report (409 Conflict).

### Added — Multi-Factor Authentication (TOTP)

- Pure Python RFC 4226/6238 TOTP implementation — no external dependency (no pyotp).
- `MFASecret` model storing TOTP secret, enablement state, and SHA-256 hashed backup codes.
- 5 MFA endpoints: status check, setup (returns secret + provisioning URI + 8 backup codes), verify (activates MFA), validate (login 2FA check), disable.
- ±1 time-step window for clock drift tolerance.

### Added — Industry Benchmarking

- `IndustryBenchmark` model with unique constraint on (industry, region, year).
- 2 benchmark endpoints: list benchmarks (with industry/region/year filters), compare company emissions to industry average with percentile ranking (top_10/top_25/median/bottom_25/bottom_10).

### Added — Testing

- 47 new tests across 13 test classes covering all Phase 24 features (CSRD/ISSB/SECR, PCAF, reviews, MFA, benchmarks).
- Total backend tests: 611 (36 files). Total frontend tests: 83 (14 files).

### Changed — Infrastructure

- 18 route modules registered (was 14): added pcaf_routes, review_routes, mfa_routes, benchmark_routes.
- 21 service modules (was 19): added pcaf.py, mfa.py.
- 5 new ORM models, 2 new enums, ~14 new Pydantic schemas.

---

## [0.17.1] — 2026-03-13 — Phase 23: Gap Analysis & Documentation

### Fixed — Backend

- Added `request: Request` parameter to all rate-limited endpoints (scenario compute, marketplace purchase, questionnaire upload/extract) — required by slowapi.
- Added rate limit decorators on compute-heavy endpoints: scenario compute (5/min), marketplace purchase (10/min), questionnaire upload (5/min), questionnaire extract (5/min).
- Consolidated email service: synchronous `email.py` replaced with async `aiosmtplib`-based implementation.

### Fixed — Frontend

- Replaced `alert()` with `useToast()` in marketplace purchase flow.
- Added `htmlFor`/`id` accessibility labels on marketplace create form (4 input pairs) and settings webhook section (2 input pairs).
- Added `PageSkeleton` loading state on upload page (was returning `null` during auth check).

### Fixed — Configuration

- Added `APP_VERSION` and `TRUST_PROXY` to `.env.example`.

### Fixed — Documentation

- Updated test counts: 564 backend (35 files) → 83 frontend (14 files) across README, CONTRIBUTING, frontend/README.
- Updated route module count: 13 → 14 (added `stripe_routes`) across README, ARCHITECTURE, CONTRIBUTING.
- Updated endpoint count: 75+ → 80+ across README, ARCHITECTURE, API.md.
- Updated page route count: 18 → 22 across ARCHITECTURE, CONTRIBUTING, frontend/README.
- Updated Bittensor SDK requirement: ≥ 6.0.0 → ≥ 10.1.0 across README, DEPLOYMENT.
- Updated API.md: expanded rate limits table (9 scopes), added marketplace seller endpoints (my-sales, my-revenue), fixed version strings in health/metrics responses.
- Updated SECURITY.md: added v0.16.x and v0.17.x to supported versions, expanded rate limiting table with all 9 rate-limited scopes.
- Updated DEPLOYMENT.md: Kubernetes rollout example uses v0.17.0 image tag.
- Updated CHANGELOG.md: added Phase 23 entry, fixed release dates.
- Updated frontend/README.md: test counts (83), page routes (22), added seller dashboard and new page entries.
- Added missing env vars to README table: `APP_VERSION`, `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `REDIS_URL`, `PROMETHEUS_ENABLED`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `POSTGRES_PASSWORD`.

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
- **Bare except blocks**: Narrowed to specific exceptions in `webhooks.py`, `email.py`, `marketplace_routes.py`.
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
