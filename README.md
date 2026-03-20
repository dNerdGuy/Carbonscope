<p align="center">
  <img src="https://img.shields.io/badge/CarbonScope-Decentralized%20Carbon%20Intelligence-00C853?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJ3aGl0ZSI+PHBhdGggZD0iTTEyIDJDNi40OCAyIDIgNi40OCAyIDEyczQuNDggMTAgMTAgMTAgMTAtNC40OCAxMC0xMFMxNy41MiAyIDEyIDJ6bTAgMThjLTQuNDIgMC04LTMuNTgtOC04czMuNTgtOCA4LTggOCAzLjU4IDggOC0zLjU4IDgtOCA4eiIvPjwvc3ZnPg==" alt="CarbonScope">
</p>

<h1 align="center">CarbonScope</h1>

<p align="center">  
  <strong>Decentralized Carbon Intelligence on Bittensor</strong><br>
  <em>Enterprise-grade carbon accounting platform powered by decentralized AI</em>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/node-18%2B-339933?style=flat-square&logo=node.js&logoColor=white" alt="Node 18+">
  <img src="https://img.shields.io/badge/version-0.27.0-orange?style=flat-square" alt="Version 0.27.0">
  <img src="https://img.shields.io/badge/tests-778%20backend%20%7C%20215%20frontend-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/endpoints-100%2B-7B61FF?style=flat-square" alt="100+ API Endpoints">
  <img src="https://img.shields.io/badge/Bittensor-Subnet-000000?style=flat-square" alt="Bittensor Subnet">
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> · 
  <a href="docs/API.md">API Reference</a> · 
  <a href="docs/ARCHITECTURE.md">Architecture</a> · 
  <a href="docs/DEPLOYMENT.md">Deploy</a> · 
  <a href="docs/CONTRIBUTING.md">Contribute</a> · 
  <a href="docs/CHANGELOG.md">Changelog</a>
</p>

---

## Overview

CarbonScope is a **Bittensor subnet** that combines decentralized AI with enterprise carbon accounting. Miners estimate corporate carbon emissions across Scope 1, 2, and 3 categories, while validators score report quality against the **GHG Protocol Corporate Standard** using curated benchmarks.

The platform ships with a production-ready **FastAPI** backend (100+ endpoints), a **Next.js 15** dashboard, and a complete carbon management suite — covering emission estimation, compliance reporting, supply chain tracking, AI-powered document processing, and a data marketplace.

### Why CarbonScope?

- **Decentralized Accuracy** — Leverage a network of competing miners for unbiased emission estimates
- **GHG Protocol Compliant** — Built from the ground up around the Corporate Standard
- **8 Emission Factor Datasets** — EPA, eGRID, IEA, DEFRA, GLEC, IPCC AR6, and industry averages
- **Full Scope Coverage** — Scope 1 (direct), Scope 2 (energy), Scope 3 (value chain) with category-level breakdowns
- **Enterprise Features** — Multi-tenant architecture, RBAC, audit logging, webhook integrations, and subscription billing

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Running on Testnet](#running-on-testnet)
- [Running Tests](#running-tests)
- [Platform API](#platform-api)
- [Data Models](#data-models)
- [Subscription Plans](#subscription-plans)
- [Emission Factor Datasets](#emission-factor-datasets)
- [GHG Protocol Coverage](#ghg-protocol-coverage)
- [Compliance Frameworks](#compliance-frameworks)
- [Questionnaire Templates](#questionnaire-templates)
- [Frontend Dashboard](#frontend-dashboard)
- [Docker Deployment](#docker-deployment)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Changelog](#changelog)
- [License](#license)

---

## Architecture

```
  ┌──────────────────────┐
  │   Next.js Dashboard  │
  │      (React 19)      │
  └──────────┬───────────┘
             │ HTTPS / REST
             v
  ┌─────────────────────────────────────────┐
  │            FastAPI Backend              │
  │      19 Route Modules · 100+ Endpoints   │
  │   JWT Auth · Rate Limiting · Audit Logs │
  └──────────┬─────────────────────┬────────┘
             │                     │
             │ SQLAlchemy          │ Subnet Queries (optional)
             v                     v
  ┌──────────────────────┐   ┌─────────────────────────────────────────┐
  │  PostgreSQL Database │   │          Bittensor Network             │
  └──────────────────────┘   │  Validator (Dendrite) ◄──► Miner (Axon)│
                             │       scoring/weights      S1/S2/S3     │
                             └─────────────────────────────────────────┘
```

**Validators** send `CarbonSynapse` queries containing company operational data. **Miners** respond with full emission estimates including Scope 1/2/3 breakdowns, confidence scores, data sources, and assumptions. Validators score responses across five axes and set on-chain weights accordingly.

### Scoring Axes

| Axis                   | Weight | Description                                                       |
| :--------------------- | :----: | :---------------------------------------------------------------- |
| **Accuracy**           |  40%   | Weighted MAPE against ground truth (S1 30%, S2 20%, S3 50%)       |
| **GHG Compliance**     |  25%   | Arithmetic consistency, scope classification, non-negative values |
| **Completeness**       |  15%   | All output fields present (emissions, breakdown, sources, etc.)   |
| **Anti-Hallucination** |  15%   | Sanity checks for physically impossible values                    |
| **Benchmark**          |   5%   | Scope-split alignment with industry norms                         |

> **Deep Dive:** See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed system design, data flow diagrams, database schema, and service architecture.

---

## Key Features

| Category              | Highlights                                                                                                       |
| :-------------------- | :--------------------------------------------------------------------------------------------------------------- |
| **Carbon Accounting** | Scope 1/2/3 estimation via Bittensor subnet or local engine; 8 emission factor datasets; GHG Protocol compliance |
| **AI Enhancement**    | LLM-powered text extraction, emission prediction, audit trail generation, reduction recommendations              |
| **Questionnaires**    | Upload PDF/DOCX/XLSX/CSV → AI-extract questions → human review → PDF export; 5 pre-built templates               |
| **Supply Chain**      | Buyer↔supplier linking, Scope 3 Category 1 aggregation, verification workflow                                    |
| **Compliance**        | Generate reports for GHG Protocol, CDP, TCFD, and SBTi frameworks                                                |
| **What-If Scenarios** | Create parameter-based scenarios, compute projected emissions                                                    |
| **Data Marketplace**  | Anonymized data listings, credit-based purchasing (Pro+ plans)                                                   |
| **Billing**           | Three subscription tiers (Free / Pro / Enterprise), credit ledger, automated monthly grants                      |
| **Webhooks**          | HMAC-SHA256 signed payloads, exponential-backoff retries, delivery logs                                          |
| **Security**          | JWT + refresh token rotation, bcrypt, CSRF double-submit, rate limiting, SSRF protection, cross-tenant isolation |

---

## Quick Start

### Prerequisites

| Requirement   | Version  | Purpose                                      |
| :------------ | :------- | :------------------------------------------- |
| Python        | 3.10+    | Backend & Bittensor subnet                   |
| Node.js       | 18+      | Frontend dashboard                           |
| Bittensor SDK | ≥ 10.1.0 | Subnet communication                         |
| PostgreSQL    | 15+      | Production database (SQLite for development) |

### 1. Install the Backend

```bash
# Clone the repository
git clone <repo-url> && cd carbonscope

# Option A: Editable install (recommended for development)
pip install -e ".[dev]"

# Option B: Pinned dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your preferred settings
```

### 3. Start the Backend

```bash
# Development (SQLite — auto-creates tables on startup)
uvicorn api.main:app --reload --port 8000

# Production (PostgreSQL — run migrations first)
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/carbonscope
alembic upgrade head
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Start the Frontend

```bash
cd frontend
npm install
npm run dev         # → http://localhost:3000
```

### 5. Explore the API

Once the backend is running, visit the interactive documentation:

| URL                            | Description                                |
| :----------------------------- | :----------------------------------------- |
| `http://localhost:8000/docs`   | Swagger UI — interactive endpoint explorer |
| `http://localhost:8000/redoc`  | ReDoc — structured API reference           |
| `http://localhost:8000/health` | Health check endpoint                      |

### Database Migrations (Alembic)

```bash
alembic revision --autogenerate -m "description"   # Generate migration
alembic upgrade head                                # Apply all migrations
alembic downgrade -1                                # Rollback one revision
alembic current                                     # Show current revision
```

> **Production Deployment:** See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for Nginx, Docker, systemd, TLS, and scaling guides.

---

## Environment Variables

| Variable                      | Default                              | Description                                                       |
| :---------------------------- | :----------------------------------- | :---------------------------------------------------------------- |
| `ENV`                         | `development`                        | Environment mode (`development` / `production` / `test`)          |
| `DATABASE_URL`                | `sqlite+aiosqlite:///carbonscope.db` | Async database URL (SQLite or PostgreSQL)                         |
| `DB_SLOW_QUERY_MS`            | `500`                                | Log warning when a DB query duration meets/exceeds this threshold |
| `SECRET_KEY`                  | `change-me-in-production`            | JWT signing key (**enforced ≥ 32 chars** in production)           |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60`                                 | JWT access token lifetime                                         |
| `ALLOWED_ORIGINS`             | `http://localhost:3000`              | Comma-separated CORS origins                                      |
| `RATE_LIMIT_AUTH`             | `10/minute`                          | Auth endpoint rate limit                                          |
| `RATE_LIMIT_DEFAULT`          | `60/minute`                          | General endpoint rate limit                                       |
| `TRUST_PROXY`                 | `false`                              | Honor `X-Forwarded-For` (set `true` behind reverse proxy)         |
| `LOG_LEVEL`                   | `INFO`                               | Logging level (`DEBUG` / `INFO` / `WARNING` / `ERROR`)            |
| `LOG_JSON`                    | `false`                              | Structured JSON logging (auto-enabled in production)              |
| `ESTIMATION_MODE`             | `local`                              | `local` (built-in engine) or `subnet` (Bittensor network)         |
| `BT_NETWORK`                  | `test`                               | Bittensor network (`test`, `finney`)                              |
| `BT_NETUID`                   | `1`                                  | Bittensor subnet UID                                              |
| `BT_WALLET_NAME`              | `api_client`                         | Bittensor wallet name                                             |
| `BT_WALLET_HOTKEY`            | `default`                            | Bittensor wallet hotkey                                           |
| `BT_QUERY_TIMEOUT`            | `30.0`                               | Bittensor query timeout (seconds)                                 |
| `SMTP_HOST`                   | —                                    | SMTP server hostname (enables email notifications)                |
| `SMTP_PORT`                   | `587`                                | SMTP port                                                         |
| `SMTP_USER` / `SMTP_PASSWORD` | —                                    | SMTP credentials                                                  |
| `EMAIL_FROM`                  | `noreply@carbonscope.io`             | Sender email address                                              |
| `REQUIRE_SMTP_IN_PRODUCTION`  | `false`                              | Fail startup in production when SMTP credentials are missing      |
| `OPENAI_API_KEY`              | —                                    | OpenAI API key (optional — enables LLM text parsing)              |
| `ANTHROPIC_API_KEY`           | —                                    | Anthropic API key (optional — enables LLM text parsing)           |
| `COOKIE_DOMAIN`               | —                                    | Cookie domain for cross-subdomain auth                            |
| `COOKIE_SECURE`               | `true` (production)                  | HTTPS-only cookies                                                |
| `COOKIE_SAMESITE`             | `lax`                                | Cookie SameSite policy                                            |
| `APP_VERSION`                 | —                                    | App version string (Sentry releases, OTEL)                        |
| `SENTRY_DSN`                  | —                                    | Sentry DSN for error tracking & APM                               |
| `SENTRY_TRACES_SAMPLE_RATE`   | `0.1`                                | Fraction of requests traced (0.0–1.0)                             |
| `REDIS_URL`                   | —                                    | Redis URL (distributed rate limiting & caching)                   |
| `PROMETHEUS_ENABLED`          | `false`                              | Expose `/metrics` in Prometheus text format                       |
| `STRIPE_SECRET_KEY`           | —                                    | Stripe API key (subscription billing)                             |
| `STRIPE_WEBHOOK_SECRET`       | —                                    | Stripe webhook signature secret                                   |
| `POSTGRES_PASSWORD`           | —                                    | PostgreSQL password (used by `docker-compose.prod.yml`)           |

> A complete template is available in [`.env.example`](.env.example).

---

## Bittensor Economic Model

CarbonScope operates as a Bittensor subnet where miners compete to produce the highest-quality carbon emission estimates. Rewards are distributed in TAO based on a multi-axis scoring system.

### How Miners Earn TAO

1. **Validators send queries** — Validators broadcast `CarbonSynapse` requests (industry, region, year, data) to miners on the subnet.
2. **Miners return estimates** — Each miner runs its emission-factor pipeline and returns scope-level emissions, a confidence score, and methodology metadata.
3. **Validators score responses** — Every response is evaluated across four weighted axes:

| Axis         | Weight | Description                                             |
| ------------ | ------ | ------------------------------------------------------- |
| Accuracy     | 0.40   | Deviation from validator's own ground-truth calculation |
| Compliance   | 0.25   | Adherence to GHG Protocol methodology                   |
| Completeness | 0.20   | Coverage of all requested scopes and categories         |
| Timeliness   | 0.15   | Response latency (faster is better)                     |

4. **EMA scoring** — Miner scores are smoothed over time using an exponential moving average (α = 0.1) to reduce noise and reward consistent quality.
5. **Weight setting** — Validators call `set_weights()` on the chain proportional to each miner's EMA score. Miners with zero scores receive weight 0 (effectively banned until quality improves).
6. **TAO distribution** — Yuma Consensus distributes TAO from the subnet's emission pool in proportion to the on-chain weights. Higher weights → more TAO.

### Reward Optimization Tips

- **Keep emission factor datasets current** — accuracy is the dominant scoring axis (40%).
- **Respond quickly** — timeliness contributes 15% of the score; cache emission factors in memory.
- **Cover all scopes** — missing scope categories reduce the completeness score.
- **Stay online** — the EMA smoothing means intermittent availability causes persistent score decay.

### Validator Economics

Validators earn their dividends from the Yuma Consensus mechanism. Running a validator requires staked TAO and incurs compute costs for dendrite queries and weight-setting transactions.

---

## Running on Testnet

### 1. Create Wallets

```bash
btcli wallet create --wallet.name miner --wallet.hotkey default
btcli wallet create --wallet.name validator --wallet.hotkey default
```

### 2. Get Testnet TAO

```bash
btcli wallet faucet --wallet.name miner --subtensor.network test
btcli wallet faucet --wallet.name validator --subtensor.network test
```

### 3. Register on Subnet

```bash
WALLET_NAME=miner ./scripts/register.sh
WALLET_NAME=validator ./scripts/register.sh
```

### 4. Run Miner & Validator

```bash
./scripts/run_miner.sh      # Starts the Axon server (port 8091)
./scripts/run_validator.sh   # Starts the Dendrite client
```

> **Configuration:** All scripts accept environment variables for customization. See `scripts/` for details.

---

## Local Subtensor Testnet

For fully offline/isolated development, you can run a local Subtensor node instead of connecting to the public testnet.

### 1. Start Local Subtensor

```bash
# Clone and run the Subtensor node locally (requires Docker)
git clone https://github.com/opentensor/subtensor.git
cd subtensor
docker compose up -d --build
```

The local chain runs at `ws://127.0.0.1:9946`.

### 2. Create & Fund Wallets

```bash
btcli wallet create --wallet.name owner --wallet.hotkey default
btcli wallet create --wallet.name miner --wallet.hotkey default
btcli wallet create --wallet.name validator --wallet.hotkey default

# Fund from the local faucet (fast, unlimited)
btcli wallet faucet --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9946
btcli wallet faucet --wallet.name miner --subtensor.chain_endpoint ws://127.0.0.1:9946
btcli wallet faucet --wallet.name validator --subtensor.chain_endpoint ws://127.0.0.1:9946
```

### 3. Create a Local Subnet

```bash
btcli subnet create --wallet.name owner --subtensor.chain_endpoint ws://127.0.0.1:9946
# Note the returned netuid (usually 1)
```

### 4. Register Miner & Validator

```bash
btcli subnet register --wallet.name miner --netuid 1 --subtensor.chain_endpoint ws://127.0.0.1:9946
btcli subnet register --wallet.name validator --netuid 1 --subtensor.chain_endpoint ws://127.0.0.1:9946
```

### 5. Run CarbonScope on Local Chain

```bash
# Terminal 1 — Miner
python3 neurons/miner.py \
  --netuid 1 \
  --wallet.name miner \
  --subtensor.chain_endpoint ws://127.0.0.1:9946 \
  --axon.port 8091

# Terminal 2 — Validator
python3 neurons/validator.py \
  --netuid 1 \
  --wallet.name validator \
  --subtensor.chain_endpoint ws://127.0.0.1:9946
```

### 6. Tear Down

```bash
cd subtensor && docker compose down -v
```

---

## Running Tests

### Backend Tests (768)

```bash
pytest tests/ -v                                      # Full suite
pytest tests/test_carbon_api.py -v                    # Specific file
pytest tests/ --cov=api --cov-report=term-missing     # With coverage
pytest tests/ -k "test_auth" -v                       # Pattern matching
```

### Frontend Tests (214)

```bash
cd frontend
npm test                  # Run full Vitest suite
npm run test:watch        # Watch mode for development
```

<details>
<summary><strong>Backend Test Coverage (46 test files)</strong></summary>

| File                                 | Coverage                                                    |
| :----------------------------------- | :---------------------------------------------------------- |
| `test_auth_api.py`                   | Registration, login, profile CRUD, password change, lockout |
| `test_company_api.py`                | Company CRUD, data upload pagination, PATCH, soft delete    |
| `test_carbon_api.py`                 | Estimation, report listing, pagination, soft delete         |
| `test_new_routes.py`                 | Webhooks CRUD, delivery logs, report export (CSV/JSON)      |
| `test_new_features.py`               | Questionnaire upload, AI extraction, scenarios, PDF export  |
| `test_compliance.py`                 | GHG Protocol, CDP, TCFD, SBTi report generation             |
| `test_ai_services.py`                | LLM parser, prediction engine, recommendations              |
| `test_ai_routes.py`                  | AI endpoints: parse-text, predict, audit-trail              |
| `test_emission_factors.py`           | Scope 1/2/3 emission factor calculations                    |
| `test_scoring.py`                    | Validator composite scoring engine                          |
| `test_generator.py`                  | Test case generation (curated + synthetic)                  |
| `test_utils.py`                      | Unit conversion utilities                                   |
| `test_e2e_security.py`               | Cross-tenant isolation, rate limiting, auth flows           |
| `test_billing_alerts_marketplace.py` | Subscriptions, credits, alerts, marketplace, scheduler      |
| `test_coverage_gaps.py`              | Refresh tokens, soft deletes, pagination, webhook toggle    |
| `test_v060_features.py`              | SSRF, refresh rotation, password reset, middleware, admin   |
| `test_audit_routes.py`               | Audit log listing, filtering by action/resource/user        |
| `test_concurrency.py`                | Concurrent credit deduction race conditions                 |
| `test_middleware_and_crud.py`        | Request logging, security headers, CRUD operations          |
| `test_phase1_security.py`            | Token revocation, brute force lockout, CSRF                 |
| `test_phase3_features.py`            | Soft delete, constraints, JSON logging                      |
| `test_phase4_polish.py`              | Enum types, validators, password strength                   |
| `test_phase5_security.py`            | Admin RBAC, cookie auth, rate limiter proxy                 |
| `test_phase6_business_logic.py`      | Credit gating, pagination, GDPR delete, ledger              |
| `test_questionnaire_routes.py`       | Questionnaire CRUD, questions, templates, extraction        |
| `test_scenario_routes.py`            | Scenario CRUD, compute, pagination                          |
| `test_supply_chain_routes.py`        | Supply chain links, Scope 3 calculation, verification       |
| `test_webhook_routes.py`             | Webhook CRUD, toggle, delivery logs, pagination             |
| `test_phase21_coverage.py`           | Webhook retry exhaustion, marketplace emails, LLM fallback  |
| `test_miner.py`                      | Miner input validation, rate limiting, error classification |
| `test_validator.py`                  | Validator scoring, EMA persistence, weight setting          |
| `test_phase13_14_hardening.py`       | Redis limiter, scheduler locks, token cleanup, indexes      |
| `test_stripe_routes.py`              | Stripe webhook signature verification, event handling       |
| `test_phase24_features.py`           | PCAF, reviews, MFA service, CSRD/ISSB/SECR compliance       |
| `test_phase25_hardening.py`          | Audit logging, rate limiting on all routes                  |
| `test_phase26_mfa_races.py`          | MFA login enforcement, registration race conditions         |
| `test_phase27_security_hardening.py` | TOTP encryption, cascade deletes, soft delete, indexes      |
| `test_reviews_service.py`            | Review service: create, list, get, state machine            |
| `test_benchmarks_service.py`         | Benchmark comparison, percentile ranking, boundaries        |
| `test_pdf_export.py`                 | PDF generation for reports and questionnaires               |
| `test_url_validator.py`              | SSRF protection: scheme, hostname, private IP, DNS          |
| `test_templates.py`                  | Questionnaire template catalog: list, get, parametrized     |
| `test_startup_policy.py`             | Production startup enforcement, config validation           |
| `test_events_routes.py`              | SSE event bus, subscription, publish, streaming             |
| `test_gdpr_hard_delete.py`           | GDPR hard delete cascade, data purge verification           |
| `test_team_routes.py`                | Multi-tenant team management, invitations, roles            |

</details>

<details>
<summary><strong>Frontend Test Coverage (35 test files, 214 tests)</strong></summary>

| File                           | Coverage                                              |
| :----------------------------- | :---------------------------------------------------- |
| `Breadcrumbs.test.tsx`         | Rendering, links, accessibility, separators           |
| `ConfirmDialog.test.tsx`       | Open/close, confirm/cancel, variants, custom labels   |
| `DataTable.test.tsx`           | Sorting, pagination, empty states, mobile cards       |
| `FormField.test.tsx`           | Labels, errors, hints, children, accessibility        |
| `Navbar.test.tsx`              | Navigation links, active states, mobile menu          |
| `Skeleton.test.tsx`            | Skeleton variants, animation, sizing                  |
| `Toast.test.tsx`               | Toast types, auto-dismiss, manual close               |
| `api.test.ts`                  | ApiError, auth headers, error handling                |
| `api-new-methods.test.ts`      | Credit ledger, delete account, supply chain, webhooks |
| `auto-refresh.test.ts`         | Token refresh on 401, retry logic                     |
| `LoginPage.test.tsx`           | Form submission, validation, error handling           |
| `ForgotPasswordPage.test.tsx`  | Form render, submit, loading state, error handling    |
| `RegisterPage.test.tsx`        | Form render, submit, 409/429 errors, generic error    |
| `DashboardPage.test.tsx`       | KPI cards, API data rendering, empty states           |
| `RecommendationsPage.test.tsx` | Strategy listing, navigation, data display            |
| `SellerDashboardPage.test.tsx` | Revenue summary, sales table, pagination              |
| `PCAFPage.test.tsx`            | Portfolio list, asset table, data rendering           |
| `ReviewsPage.test.tsx`         | Review list, create form, status display              |
| `MFAPage.test.tsx`             | MFA status, setup, QR code, disable flow              |
| `BenchmarksPage.test.tsx`      | Benchmark metrics, industry comparison                |
| `SettingsPage.test.tsx`        | Profile, company, webhooks, password sections         |
| `UploadPage.test.tsx`          | Form rendering, submit/error, scope labels            |
| `CompliancePage.test.tsx`      | Framework buttons, generate, error handling           |
| `BillingPage.test.tsx`         | Plan display, credits, plan change, error handling    |
| `ReportsPage.test.tsx`         | Sort controls, export CSV/JSON, year filter           |
| `AlertsPage.test.tsx`          | Alert list, severity, run check, unread filter        |
| `AuditLogsPage.test.tsx`       | Table rendering, empty state, error, accessibility    |
| `QuestionnairesPage.test.tsx`  | Tabs, list, templates, apply template                 |
| `AuthContext.test.tsx`         | JWT decoding, localStorage, login/logout/register     |
| `MarketplacePage.test.tsx`     | Listing count, filter, create modal, fetch error      |
| `ScenariosPage.test.tsx`       | Create form, scenario creation, status filter         |
| `SupplyChainPage.test.tsx`     | Scope 3 summary, add supplier, fetch error            |
| `ResetPasswordPage.test.tsx`   | Password mismatch, weak password, successful reset    |
| `useEventSource.test.ts`       | SSE hook lifecycle, reconnect, event handling         |
| `validation.test.ts`           | Input validation helpers, edge cases                  |

</details>

---

## Platform API

The platform exposes **100+ RESTful endpoints** across 19 route modules. All endpoints are prefixed with `/api/v1/` and documented via OpenAPI.

### Endpoint Summary

| Category              | Endpoints | Highlights                                                             |
| :-------------------- | :-------: | :--------------------------------------------------------------------- |
| **Auth**              |    10     | Register, login, logout, JWT + refresh rotation, password reset/forgot |
| **Company & Data**    |     7     | Company CRUD, data upload with pagination and soft delete              |
| **Carbon Estimation** |     8     | Local/subnet estimation, reports, dashboard, CSV/JSON/PDF export       |
| **AI Enhancement**    |     4     | Text parsing, emission prediction, audit trail, recommendations        |
| **Questionnaires**    |    11     | Upload, AI extraction, templates, human review, PDF export             |
| **Scenarios**         |     6     | What-if scenario builder with compute engine                           |
| **Supply Chain**      |     7     | Supplier linking, Scope 3 propagation, verification                    |
| **Compliance**        |     1     | GHG Protocol / CDP / TCFD / SBTi report generation                     |
| **Billing**           |     6     | Subscription management, credits, plan comparison, ledger              |
| **Alerts**            |     3     | Emission threshold monitoring, acknowledgement                         |
| **Marketplace**       |     8     | Anonymized data listings, credit-based purchase, seller dashboard      |
| **Webhooks**          |     5     | HMAC-signed webhooks, delivery logs with retry info                    |
| **Stripe**            |     1     | Stripe webhook endpoint for subscription events                        |
| **PCAF**              |     6     | Financed emissions portfolios, asset management, calculations          |
| **Reviews**           |     4     | Data review workflow (create, list, approve/reject)                    |
| **MFA**               |     5     | TOTP setup, verify, disable, status check                              |
| **Benchmarks**        |     2     | Industry benchmark comparison and percentile ranking                   |
| **Events (SSE)**      |     1     | Server-Sent Events subscription for real-time push                     |
| **Audit & Health**    |     4     | Audit logs (admin), health check, liveness probe, detailed health      |

> **Full Reference:** See [API.md](docs/API.md) for the complete endpoint reference with request/response examples.

---

## Data Models

The platform uses **24 SQLAlchemy models** with full async support, soft deletes, and CHECK constraints.

| Model                     | Description                                                                       |
| :------------------------ | :-------------------------------------------------------------------------------- |
| **Company**               | Organization profile (industry, region, revenue, employees)                       |
| **User**                  | Authenticated member (email, bcrypt password, role: admin/member, lockout fields) |
| **DataUpload**            | Raw operational data (year, JSON `provided_data`)                                 |
| **EmissionReport**        | Calculated emissions (S1/S2/S3, breakdown, confidence, miner scores)              |
| **SupplyChainLink**       | Buyer↔supplier relationship (spend, category, verification status)                |
| **Webhook**               | HTTP callback endpoint (URL, event types, HMAC secret)                            |
| **WebhookDelivery**       | Delivery log (status code, duration, retry info)                                  |
| **AuditLog**              | Action audit trail (user, action, resource type/id, detail)                       |
| **Questionnaire**         | Uploaded document (PDF/DOCX/XLSX/CSV, extraction status)                          |
| **QuestionnaireQuestion** | Extracted question with AI draft + human-reviewed answer                          |
| **Scenario**              | What-if analysis (parameters, base report, computed results)                      |
| **Subscription**          | Company plan tier (free/pro/enterprise, billing status)                           |
| **CreditLedger**          | Credit transaction log (grants, deductions, running balance)                      |
| **Alert**                 | Automated alert (emission increase, confidence drop, target exceeded)             |
| **DataListing**           | Marketplace listing (anonymized data, price in credits)                           |
| **DataPurchase**          | Marketplace purchase transaction record                                           |
| **RefreshToken**          | Persistent refresh token (SHA-256 hashed, single-use rotation)                    |
| **RevokedToken**          | Access token blacklist (JTI-based, for logout)                                    |
| **PasswordResetToken**    | Short-lived password reset token (15-minute expiry)                               |
| **FinancedPortfolio**     | PCAF financed emissions portfolio (asset class, methodology)                      |
| **FinancedAsset**         | Individual financed asset within a portfolio (attribution, emissions)             |
| **DataReview**            | Data review workflow record (status, reviewer, comments)                          |
| **MFASecret**             | Encrypted TOTP secret for multi-factor authentication (Fernet at rest)            |
| **IndustryBenchmark**     | Industry benchmark data for percentile comparison                                 |

> **Schema Details:** See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for database relationships, constraints, and ER diagrams.

---

## Subscription Plans

| Feature            | Free | Pro ($99/mo) | Enterprise ($499/mo) |
| :----------------- | :--: | :----------: | :------------------: |
| Monthly Credits    | 100  |    1,000     |        10,000        |
| Reports / month    |  3   |  Unlimited   |      Unlimited       |
| Scenarios          |  5   |  Unlimited   |      Unlimited       |
| Questionnaires     |  3   |  Unlimited   |      Unlimited       |
| PDF Export         |  —   |      ✓       |          ✓           |
| Supply Chain       |  —   |      ✓       |          ✓           |
| Webhooks           |  —   |      ✓       |          ✓           |
| Data Marketplace   |  —   |      ✓       |          ✓           |
| Compliance Reports |  —   |      ✓       |          ✓           |
| Priority Support   |  —   |      —       |          ✓           |

### Credit Costs

| Operation                   |  Credits |
| :-------------------------- | -------: |
| Emission Estimate           |       10 |
| Questionnaire AI Extraction |        8 |
| PDF Export                  |        5 |
| Scenario Compute            |        3 |
| Marketplace Purchase        | Variable |

---

## Emission Factor Datasets

| Dataset                   | Source           | Coverage                                        |
| :------------------------ | :--------------- | :---------------------------------------------- |
| EPA Stationary Combustion | US EPA           | 10 fuel types (coal, natural gas, diesel, etc.) |
| EPA Mobile Combustion     | US EPA           | 8 vehicle types (passenger, light truck, etc.)  |
| eGRID Subregions          | US EPA           | 27 US subregions + state-to-subregion mapping   |
| IEA Grid Factors          | IEA              | 68 countries + regional averages                |
| DEFRA                     | UK BEIS          | UK-specific emission factors                    |
| Transport                 | GLEC Framework   | Freight + passenger transport modes             |
| Industry Averages         | Multiple sources | 9 industries with scope-split ratios            |
| GWP AR6                   | IPCC             | CO₂, CH₄, N₂O, SF₆ + 9 common refrigerants      |

---

## GHG Protocol Coverage

| Scope       | Categories                                                                                                              | Method                                                                 |
| :---------- | :---------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------- |
| **Scope 1** | Stationary combustion, mobile combustion, fugitive emissions (refrigerant leaks)                                        | Activity-based (EPA factors)                                           |
| **Scope 2** | Grid electricity, purchased steam/heating                                                                               | Location-based (eGRID/IEA) + market-based (with REC offsets)           |
| **Scope 3** | Cat 1 (purchased goods), Cat 4 (upstream transport), Cat 5 (waste), Cat 6 (business travel), Cat 7 (employee commuting) | Activity-based + industry-default gap-filling for remaining categories |

---

## Compliance Frameworks

| Framework                           | Description                                                                    |
| :---------------------------------- | :----------------------------------------------------------------------------- |
| **GHG Protocol Corporate Standard** | Full inventory with all 15 Scope 3 categories                                  |
| **CDP Climate Change**              | Questionnaire modules C0–C7                                                    |
| **TCFD**                            | 4-pillar disclosure (Governance, Strategy, Risk Management, Metrics & Targets) |
| **SBTi**                            | 11-year 1.5°C-aligned reduction pathway (4.2% annual S1+S2 reduction)          |

---

## Questionnaire Templates

Five pre-built templates for major sustainability frameworks:

| Template                   | Questions | Focus                                            |
| :------------------------- | --------: | :----------------------------------------------- |
| **CDP Climate Change**     |        30 | Governance, risk management, emissions reporting |
| **EcoVadis Assessment**    |        20 | Environment, labor practices, supply chain       |
| **TCFD Disclosure**        |        15 | Four-pillar climate risk disclosure              |
| **GHG Protocol Inventory** |        25 | Complete emission inventory questionnaire        |
| **CSRD/ESRS**              |        35 | EU sustainability reporting standards            |

---

## Frontend Dashboard

The **Next.js 15** dashboard (React 19, Tailwind CSS 4, Recharts) provides a complete carbon management interface:

| Page                 | Description                                                 |
| :------------------- | :---------------------------------------------------------- |
| **Dashboard**        | KPI cards, scope breakdown chart, year-over-year trends     |
| **Data Upload**      | Structured entry for Scope 1/2/3 activity data              |
| **Reports**          | Paginated list with sorting, filtering, CSV/JSON/PDF export |
| **Recommendations**  | AI-generated reduction strategies ranked by impact          |
| **Questionnaires**   | Document upload → AI extraction → human review → PDF export |
| **Scenarios**        | Interactive what-if builder with visual results             |
| **Supply Chain**     | Supplier network management, Scope 3 propagation            |
| **Compliance**       | Generate GHG Protocol / CDP / TCFD / SBTi reports           |
| **Marketplace**      | Browse, purchase, create, and withdraw data listings        |
| **Seller Dashboard** | Revenue summary, sales table, active listings               |
| **Alerts**           | Emission threshold alerts with acknowledgement              |
| **Billing**          | Subscription plans, credit balance, plan management         |
| **Audit Log**        | Activity trail viewer with pagination and filters           |
| **Settings**         | User profile, password change, company profile, webhooks    |

**UI Features:** Toast notifications, confirmation dialogs, loading skeletons, breadcrumb navigation, mobile-responsive card tables, copy-to-clipboard, URL query state sync, dark/light theme toggle, accessibility (skip-to-content, focus indicators, reduced motion, ARIA labels).

> **Setup & Components:** See [frontend/README.md](frontend/README.md) for frontend development details.

---

## Docker Deployment

### Development

```bash
docker compose up --build -d
curl http://localhost:8000/health
```

### Production

```bash
cp .env.example .env                # Edit with production values
export POSTGRES_PASSWORD=$(openssl rand -hex 16)
docker compose -f docker-compose.prod.yml up --build -d
```

The production stack includes PostgreSQL 16, resource limits, `no-new-privileges` security, and non-root container execution.

> **Full Guide:** See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for Nginx reverse proxy, TLS certificates, systemd services, scaling strategies, and the pre-launch checklist.

---

## Project Structure

```
carbonscope/
├── api/                            # FastAPI platform backend
│   ├── main.py                     # App entry point (19 routers, lifespan scheduler)
│   ├── config.py                   # Env-based configuration + production enforcement
│   ├── database.py                 # SQLAlchemy async (SQLite + PostgreSQL)
│   ├── models.py                   # 24 models (see Data Models)
│   ├── schemas.py                  # Pydantic request/response schemas
│   ├── auth.py                     # JWT + bcrypt + refresh/reset tokens
│   ├── deps.py                     # Dependencies: auth, plan gates, credits, admin
│   ├── middleware.py               # Request ID, security headers, error handler
│   ├── limiter.py                  # SlowAPI rate limiter
│   ├── routes/                     # 19 route modules (see Platform API)
│   └── services/                   # 26 service modules (see Architecture)
├── carbonscope/                    # Bittensor subnet core
│   ├── protocol.py                 # CarbonSynapse (bt.Synapse)
│   ├── scoring.py                  # 5-axis composite scoring engine
│   ├── utils.py                    # Unit conversions, GWP helpers
│   ├── emission_factors/           # Scope 1/2/3 calculation engines
│   ├── validation/                 # GHG Protocol, sanity checks, benchmarks
│   └── test_cases/                 # Curated + synthetic test generator
├── neurons/
│   ├── miner.py                    # Bittensor Axon server
│   └── validator.py                # Bittensor Dendrite client
├── frontend/                       # Next.js 15 + React 19 dashboard
│   └── src/
│       ├── app/                    # App Router pages (26 routes)
│       ├── components/             # Reusable UI components
│       └── lib/                    # API client, auth context, utilities
├── alembic/                        # Database migrations
├── data/emission_factors/          # EPA, eGRID, IEA, DEFRA JSON datasets
├── scripts/                        # Shell scripts (register, run miner/validator)
├── tests/                          # 768 backend tests (pytest, 46 files)
├── docker-compose.yml              # Development stack
├── docker-compose.prod.yml         # Production stack (PostgreSQL)
├── Dockerfile                      # Multi-stage (backend + frontend)
├── requirements.txt                # Pinned Python dependencies
├── pyproject.toml                  # Build configuration
└── alembic.ini                     # Alembic migration config
```

---

## Troubleshooting

| Issue                                   | Solution                                                                                                                  |
| :-------------------------------------- | :------------------------------------------------------------------------------------------------------------------------ |
| `SECRET_KEY is using the default value` | Set a real `SECRET_KEY` env var (required in production: ≥ 32 chars, high entropy)                                        |
| `RuntimeError: SECRET_KEY must be set`  | Production mode enforces a real secret key — generate one with `python -c "import secrets; print(secrets.token_hex(32))"` |
| CORS errors in browser                  | Add your frontend URL to `ALLOWED_ORIGINS` (comma-separated)                                                              |
| 429 Too Many Requests                   | Adjust `RATE_LIMIT_AUTH` / `RATE_LIMIT_DEFAULT` env vars                                                                  |
| Frontend can't reach backend            | Ensure backend is on port 8000 and check Next.js rewrites in `next.config.js`                                             |
| SQLite locked under load                | Switch `DATABASE_URL` to PostgreSQL for concurrent access                                                                 |
| Bittensor timeout                       | Check wallet registration with `btcli wallet overview` and increase `BT_QUERY_TIMEOUT`                                    |
| Tests fail with 429                     | Rate limiter state accumulates across test files — the autouse fixture in `conftest.py` clears it                         |
| `alembic upgrade head` fails            | Ensure `DATABASE_URL` is set and the database is reachable                                                                |
| Docker build fails                      | Check Docker daemon is running and you have sufficient disk space                                                         |

---

## Kubernetes Deployment

Production Kubernetes manifests are in `k8s/`. See [k8s/README.md](k8s/README.md) for setup instructions.

```bash
# Quick deploy
kubectl apply -f k8s/
```

---

## Operations Runbook

### Backup & Recovery

```bash
# PostgreSQL backup (run daily via cron)
docker exec carbonscope-db-1 pg_dump -U carbonscope carbonscope | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore from backup
gunzip -c backup_20260313.sql.gz | docker exec -i carbonscope-db-1 psql -U carbonscope carbonscope
```

### Database Migrations

```bash
# Apply pending migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# Check current revision
alembic current
```

### Monitoring

| Endpoint           | Purpose                                                                     |
| :----------------- | :-------------------------------------------------------------------------- |
| `GET /health/live` | Liveness check — returns `200` if process is running (no dependency checks) |
| `GET /health`      | Readiness check — returns `200` with version and DB connectivity status     |
| `GET /metrics`     | Prometheus text format — request counts, error rates, status codes          |

Connect Prometheus to scrape `/metrics` every 15s. Import the Grafana dashboard from `docs/grafana-dashboard.json` (if available) or create panels for `carbonscope_requests_total`, `carbonscope_errors_total`, and `carbonscope_http_requests_by_status`.

### Sentry / APM

Set `SENTRY_DSN` to enable error tracking and performance monitoring. Adjust `SENTRY_TRACES_SAMPLE_RATE` (default `0.1` = 10% of requests traced).

### Scaling

| Component | Scaling Strategy                                                                                |
| :-------- | :---------------------------------------------------------------------------------------------- |
| Backend   | Horizontal — run multiple `uvicorn` workers behind Nginx (`--workers N`) or multiple containers |
| Frontend  | Horizontal — stateless Next.js containers behind Nginx                                          |
| Database  | Vertical first, then read replicas. Use `pgbouncer` for connection pooling                      |
| Redis     | Single instance for rate limiting; Redis Sentinel or Cluster for HA                             |
| Scheduler | Run exactly **one** instance (the background scheduler is not distributed)                      |

### Incident Response

1. **Check health**: `curl https://your-domain/health`
2. **Check logs**: `docker compose -f docker-compose.prod.yml logs --tail=100 backend`
3. **Check metrics**: `curl https://your-domain/metrics | grep errors`
4. **Check Sentry**: Review error dashboard for stack traces
5. **Restart service**: `docker compose -f docker-compose.prod.yml restart backend`
6. **Rollback deployment**: `docker compose -f docker-compose.prod.yml pull && docker compose up -d`

---

## Documentation

| Document                                 | Description                                                                |
| :--------------------------------------- | :------------------------------------------------------------------------- |
| [README.md](README.md)                   | Project overview, quick start, and feature summary (this file)             |
| [API.md](docs/API.md)                    | Complete API reference — all 100+ endpoints with request/response examples |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md)  | System design, data flow, database schema, service architecture            |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md)      | Production deployment guide (Nginx, Docker, systemd, TLS, scaling)         |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md)  | Development workflow, code style, testing, and PR process                  |
| [CHANGELOG.md](docs/CHANGELOG.md)        | Version history and release notes                                          |
| [SECURITY.md](docs/SECURITY.md)          | Security policy, vulnerability reporting, and security architecture        |
| [frontend/README.md](frontend/README.md) | Frontend setup, components, testing, and development guide                 |

---

## Changelog

See [CHANGELOG.md](docs/CHANGELOG.md) for the full version history.

**Latest — v0.26.0** (Round 4 Hardening): AuditLog immutability (CASCADE→SET NULL), TOTP HKDF key derivation, GDPR delete safety (check other company users), JWT removed from login response body, CSP unsafe-inline removed, JWT expiry validation in middleware, confirmation dialogs (PCAF/billing/reviews), K8s zero-downtime rolling updates, validator score HMAC integrity, coverage threshold enforcement, backend hardening (body-limit chunked fix, admin-gated routes, webhook HTTPS enforcement). See [CHANGELOG.md](docs/CHANGELOG.md) for the full history.

---

## License

This project is licensed under the [MIT License](LICENSE).
