# CarbonScope — Bittensor Subnet for Decentralized Carbon Intelligence

CarbonScope is a Bittensor subnet where **miners** estimate corporate carbon emissions and **validators** score report quality using the GHG Protocol Corporate Standard against curated benchmarks.

## Architecture

```
Validator                          Miner
┌────────────────-┐    Synapse     ┌────────────────────-┐
│ Generate query  ├───────────────►│ Parse questionnaire │
│ (curated/       │  CarbonSynapse │ Calculate S1/S2/S3  │
│  synthetic)     │◄──────────────-┤ Fill breakdown      │
│ Score response  │   response     │ Assess confidence   │
│ Set weights     │                └───────────────────-─┘
└────────────────-┘
```

**Scoring Axes** (0.0–1.0 composite):
| Axis | Weight | Description |
|------|--------|-------------|
| Accuracy | 40% | Weighted MAPE against ground truth (S1=30%, S2=20%, S3=50%) |
| GHG Compliance | 25% | Arithmetic consistency, scope classification, non-negative |
| Completeness | 15% | All output fields present (emissions, breakdown, sources, etc.) |
| Anti-Hallucination | 15% | Sanity checks for physically impossible values |
| Benchmark | 5% | Scope-split alignment with industry norms |

## Project Structure

```
carbonscope/
├── carbonscope/                    # Bittensor subnet core
│   ├── protocol.py                # CarbonSynapse (bt.Synapse)
│   ├── scoring.py                 # Composite scoring engine
│   ├── utils.py                   # Unit conversions, GWP helpers
│   ├── emission_factors/          # Scope 1/2/3 calculation engines
│   │   ├── loader.py, scope1.py, scope2.py, scope3.py
│   ├── validation/                # GHG Protocol, sanity checks, benchmarks
│   └── test_cases/                # Curated + synthetic test generator
├── neurons/
│   ├── miner.py                   # Bittensor Axon server
│   └── validator.py               # Bittensor Dendrite client
├── api/                           # FastAPI platform backend
│   ├── main.py                    # App entry point (13 routers, lifespan scheduler)
│   ├── config.py                  # Env-based configuration + production enforcement
│   ├── database.py                # SQLAlchemy async (SQLite + PostgreSQL)
│   ├── models.py                  # 16 models (see Data Models below)
│   ├── schemas.py                 # Pydantic request/response schemas
│   ├── auth.py                    # JWT + bcrypt + refresh/reset tokens
│   ├── deps.py                    # Dependencies: auth, plan gates, credits, admin
│   ├── middleware.py               # Request ID, security headers, error handler
│   ├── limiter.py                 # Shared rate limiter
│   ├── routes/
│   │   ├── auth_routes.py         # Register, login, refresh, password reset
│   │   ├── company_routes.py      # Company CRUD, data upload CRUD
│   │   ├── carbon_routes.py       # Estimation (local/subnet), reports, dashboard
│   │   ├── ai_routes.py           # LLM parsing, prediction, recommendations
│   │   ├── supply_chain_routes.py # Supplier/buyer linking, Scope 3 propagation
│   │   ├── compliance_routes.py   # GHG Protocol, CDP, TCFD, SBTi reports
│   │   ├── webhook_routes.py      # Webhook CRUD + HMAC-signed dispatch
│   │   ├── audit_routes.py        # Audit log listing
│   │   ├── questionnaire_routes.py # Document upload, AI extraction, PDF export
│   │   ├── scenario_routes.py     # What-if scenario builder
│   │   ├── billing_routes.py      # Subscription, credits, plan management
│   │   ├── alert_routes.py        # Automated alerts + acknowledgement
│   │   └── marketplace_routes.py  # Anonymized data marketplace
│   └── services/
│       ├── subnet_bridge.py       # Bittensor + local estimation engine
│       ├── llm_parser.py          # Rule-based + LLM text extraction
│       ├── prediction.py          # Revenue/employee emission prediction
│       ├── recommendations.py     # 11 reduction strategies
│       ├── supply_chain.py        # Buyer↔supplier + Scope 3 Cat 1
│       ├── compliance.py          # GHG Protocol, CDP, TCFD, SBTi
│       ├── webhooks.py            # HMAC-SHA256 webhook dispatch
│       ├── audit.py               # Audit logging
│       ├── questionnaire.py       # Document parsing + AI Q&A extraction
│       ├── scenarios.py           # What-if computation engine
│       ├── pdf_export.py          # ReportLab PDF generation
│       ├── templates.py           # 5 questionnaire templates (CDP, TCFD, etc.)
│       ├── subscriptions.py       # Plan tiers, credits, billing
│       ├── alerts.py              # Emission monitoring + alert generation
│       ├── marketplace.py         # Data anonymization + marketplace logic
│       ├── email.py               # SMTP email notifications (sync)
│       ├── email_async.py         # Async email via aiosmtplib
│       ├── url_validator.py       # SSRF protection for webhook URLs
│       └── scheduler.py           # Alert checks + monthly credit reset
├── alembic/                       # Database migrations
│   ├── env.py                     # Async migration runner
│   └── versions/                  # Migration scripts
├── frontend/                      # Next.js 15 + React 19 dashboard
│   └── src/
│       ├── lib/api.ts             # Typed API client (55+ functions)
│       ├── lib/auth-context.tsx   # JWT auth context provider
│       ├── components/            # Navbar, ScopeChart, Toast, ConfirmDialog, Skeleton
│       └── app/                   # App Router pages (20 routes)
├── data/emission_factors/         # EPA, eGRID, IEA, DEFRA JSON datasets
├── .github/workflows/ci.yml      # GitHub Actions CI/CD pipeline
├── alembic.ini                    # Alembic configuration
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── setup.py
```

## Data Models (16)

| Model                 | Description                                                          |
| --------------------- | -------------------------------------------------------------------- |
| Company               | Organization profile (industry, region, revenue, employees)          |
| User                  | Authenticated member (email, role: admin/member)                     |
| DataUpload            | Raw operational data (year, JSON provided_data)                      |
| EmissionReport        | Calculated emissions (S1/S2/S3, breakdown, confidence, miner scores) |
| SupplyChainLink       | Buyer↔supplier relationship (spend, category, status)                |
| Webhook               | HTTP webhook endpoint (URL, events, HMAC secret)                     |
| WebhookDelivery       | Webhook delivery log (status code, duration, response)               |
| AuditLog              | Action audit trail (user, action, resource)                          |
| Questionnaire         | Uploaded document (PDF/DOCX/XLSX/CSV, extracted text)                |
| QuestionnaireQuestion | Extracted question with AI draft + human answer                      |
| Scenario              | What-if analysis (parameters, computed results)                      |
| Subscription          | Company plan tier (free/pro/enterprise, Stripe IDs)                  |
| CreditLedger          | Credit transactions (grants, deductions, balance)                    |
| Alert                 | Automated alerts (emission increase, confidence drop)                |
| DataListing           | Marketplace listing (anonymized data, price in credits)              |
| DataPurchase          | Marketplace purchase record                                          |

## Prerequisites

- Python 3.10+
- Node.js 18+ (for the frontend)
- Bittensor SDK >= 6.0.0
- PostgreSQL (recommended for production; SQLite works for dev)

## Environment Variables

| Variable                      | Default                              | Description                                    |
| ----------------------------- | ------------------------------------ | ---------------------------------------------- |
| `ENV`                         | `development`                        | Environment mode (development/production/test) |
| `DATABASE_URL`                | `sqlite+aiosqlite:///carbonscope.db` | Async DB URL (SQLite or PostgreSQL)            |
| `SECRET_KEY`                  | `change-me-in-production`            | JWT signing key (**enforced** in production)   |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60`                                 | JWT token lifetime                             |
| `ALLOWED_ORIGINS`             | `http://localhost:3000`              | Comma-separated CORS origins                   |
| `RATE_LIMIT_AUTH`             | `10/minute`                          | Rate limit for auth endpoints                  |
| `RATE_LIMIT_DEFAULT`          | `60/minute`                          | Rate limit for general endpoints               |
| `LOG_LEVEL`                   | `INFO`                               | Logging level                                  |
| `ESTIMATION_MODE`             | `local`                              | `local` (dev) or `subnet` (Bittensor network)  |
| `BT_NETWORK`                  | `test`                               | Bittensor network (test, finney)               |
| `BT_NETUID`                   | `1`                                  | Bittensor subnet UID                           |
| `BT_WALLET_NAME`              | `api_client`                         | Bittensor wallet name                          |
| `BT_WALLET_HOTKEY`            | `default`                            | Bittensor wallet hotkey                        |
| `BT_QUERY_TIMEOUT`            | `30.0`                               | Bittensor query timeout (seconds)              |
| `SMTP_HOST`                   | —                                    | SMTP server (set to enable email)              |
| `SMTP_PORT`                   | `587`                                | SMTP port                                      |
| `SMTP_USER`                   | —                                    | SMTP username                                  |
| `SMTP_PASSWORD`               | —                                    | SMTP password                                  |
| `EMAIL_FROM`                  | `noreply@carbonscope.io`             | Sender email address                           |
| `OPENAI_API_KEY`              | —                                    | OpenAI API key (optional, LLM parsing)         |
| `ANTHROPIC_API_KEY`           | —                                    | Anthropic API key (optional, LLM parsing)      |

## Setup

```bash
# Clone and install
git clone <repo-url> && cd carbonscope
pip install -e ".[dev]"

# Or install dependencies directly
pip install -r requirements.txt
```

### Database Setup

```bash
# Development (SQLite — auto-creates on startup)
uvicorn api.main:app --reload --port 8000

# Production (PostgreSQL)
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/carbonscope
alembic upgrade head    # Run migrations
uvicorn api.main:app --port 8000
```

### Database Migrations (Alembic)

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "description of changes"

# Apply migrations
alembic upgrade head

# Downgrade one revision
alembic downgrade -1

# View current revision
alembic current
```

## Running on Testnet

### 1. Create wallets

```bash
btcli wallet create --wallet.name miner --wallet.hotkey default
btcli wallet create --wallet.name validator --wallet.hotkey default
```

### 2. Get testnet TAO

```bash
btcli wallet faucet --wallet.name miner --subtensor.network test
btcli wallet faucet --wallet.name validator --subtensor.network test
```

### 3. Register on subnet

```bash
WALLET_NAME=miner ./scripts/register.sh
WALLET_NAME=validator ./scripts/register.sh
```

### 4. Run miner & validator

```bash
./scripts/run_miner.sh
./scripts/run_validator.sh
```

## Running Tests

```bash
pytest tests/ -v               # All 307 tests
pytest tests/test_carbon_api.py -v  # Specific file
pytest tests/ -q --tb=short    # Short output
pytest tests/ --cov=api --cov-report=term-missing  # With coverage
```

### Test Coverage

| File                                 | Coverage                                                   |
| ------------------------------------ | ---------------------------------------------------------- |
| `test_auth_api.py`                   | Registration, login, profile CRUD, password change         |
| `test_company_api.py`                | Company CRUD, data upload pagination, PATCH, soft delete   |
| `test_carbon_api.py`                 | Estimation, report listing, pagination, soft delete        |
| `test_new_routes.py`                 | Webhooks CRUD, delivery logs, report export (CSV/JSON)     |
| `test_new_features.py`               | Questionnaire upload, AI extraction, scenarios, PDF export |
| `test_compliance.py`                 | GHG Protocol, CDP, TCFD, SBTi report generation            |
| `test_ai_services.py`                | LLM parser, prediction engine, recommendations             |
| `test_emission_factors.py`           | Scope 1/2/3 emission factor calculations                   |
| `test_scoring.py`                    | Validator composite scoring engine                         |
| `test_generator.py`                  | Test case generation (curated + synthetic)                 |
| `test_utils.py`                      | Unit conversion utilities                                  |
| `test_e2e_security.py`               | Cross-tenant isolation, rate limiting, auth flows          |
| `test_billing_alerts_marketplace.py` | Subscriptions, credits, alerts, marketplace, scheduler     |
| `test_coverage_gaps.py`              | Refresh tokens, soft deletes, pagination, webhook toggle   |
| `test_v060_features.py`              | SSRF, refresh rotation, password reset, middleware, admin  |

## Docker Deployment

```bash
# Quick start
docker compose up --build -d
curl http://localhost:8000/health

# Production
export SECRET_KEY=$(openssl rand -hex 32)
export ENV=production
docker compose up --build -d
```

## Platform API (v0.6.0)

### Start the API server

```bash
uvicorn api.main:app --reload --port 8000
```

Interactive docs: `http://localhost:8000/docs`

### API Endpoints (75+)

#### Auth (8 endpoints)

| Method | Endpoint                       | Description                       |
| ------ | ------------------------------ | --------------------------------- |
| POST   | `/api/v1/auth/register`        | Register user + company           |
| POST   | `/api/v1/auth/login`           | Get JWT access + refresh tokens   |
| GET    | `/api/v1/auth/me`              | Get current user profile          |
| PATCH  | `/api/v1/auth/me`              | Update name / email               |
| POST   | `/api/v1/auth/change-password` | Change password                   |
| POST   | `/api/v1/auth/refresh`         | Rotate refresh token for new pair |
| POST   | `/api/v1/auth/forgot-password` | Request password reset email      |
| POST   | `/api/v1/auth/reset-password`  | Reset password with token         |

#### Company & Data (7)

| Method | Endpoint            | Description                   |
| ------ | ------------------- | ----------------------------- |
| GET    | `/api/v1/company`   | Get company profile           |
| PATCH  | `/api/v1/company`   | Update company profile        |
| POST   | `/api/v1/data`      | Upload operational data       |
| GET    | `/api/v1/data`      | List data uploads (paginated) |
| GET    | `/api/v1/data/{id}` | Get specific upload           |
| PATCH  | `/api/v1/data/{id}` | Update upload                 |
| DELETE | `/api/v1/data/{id}` | Soft-delete upload            |

#### Carbon Estimation & Reports (6)

| Method | Endpoint                 | Description                                    |
| ------ | ------------------------ | ---------------------------------------------- |
| POST   | `/api/v1/estimate`       | Run emission estimation (local or subnet)      |
| GET    | `/api/v1/reports`        | List reports (paginated, sortable, filterable) |
| GET    | `/api/v1/reports/{id}`   | Get specific report                            |
| DELETE | `/api/v1/reports/{id}`   | Soft-delete report                             |
| GET    | `/api/v1/reports/export` | Export reports as CSV or JSON                  |
| GET    | `/api/v1/dashboard`      | Company dashboard summary                      |

#### AI Enhancement (4)

| Method | Endpoint                          | Description                           |
| ------ | --------------------------------- | ------------------------------------- |
| POST   | `/api/v1/ai/parse-text`           | Extract emissions data from free text |
| POST   | `/api/v1/ai/predict`              | Predict missing emission categories   |
| POST   | `/api/v1/ai/audit-trail`          | Generate audit trail for a report     |
| GET    | `/api/v1/ai/recommendations/{id}` | Get reduction recommendations         |

#### Questionnaires (10)

| Method | Endpoint                                        | Description                        |
| ------ | ----------------------------------------------- | ---------------------------------- |
| POST   | `/api/v1/questionnaires/upload`                 | Upload PDF/DOCX/XLSX/CSV document  |
| GET    | `/api/v1/questionnaires`                        | List uploaded questionnaires       |
| GET    | `/api/v1/questionnaires/{id}`                   | Get questionnaire with questions   |
| POST   | `/api/v1/questionnaires/{id}/extract`           | AI-extract questions from document |
| PATCH  | `/api/v1/questionnaires/{qid}/questions/{qnid}` | Update question answer/status      |
| DELETE | `/api/v1/questionnaires/{id}`                   | Delete questionnaire               |
| GET    | `/api/v1/questionnaires/{id}/export/pdf`        | Export questionnaire as PDF        |
| GET    | `/api/v1/questionnaires/templates`              | List template library              |
| GET    | `/api/v1/questionnaires/templates/{id}`         | Get template details               |
| POST   | `/api/v1/questionnaires/templates/{id}/apply`   | Create questionnaire from template |

#### Scenarios (5)

| Method | Endpoint                         | Description              |
| ------ | -------------------------------- | ------------------------ |
| POST   | `/api/v1/scenarios`              | Create what-if scenario  |
| GET    | `/api/v1/scenarios`              | List scenarios           |
| GET    | `/api/v1/scenarios/{id}`         | Get scenario details     |
| POST   | `/api/v1/scenarios/{id}/compute` | Compute scenario results |
| DELETE | `/api/v1/scenarios/{id}`         | Delete scenario          |

#### Supply Chain (6)

| Method | Endpoint                                     | Description                           |
| ------ | -------------------------------------------- | ------------------------------------- |
| POST   | `/api/v1/supply-chain/links`                 | Link a supplier                       |
| GET    | `/api/v1/supply-chain/suppliers`             | List your suppliers                   |
| GET    | `/api/v1/supply-chain/buyers`                | List companies buying from you        |
| GET    | `/api/v1/supply-chain/scope3-from-suppliers` | Scope 3 Cat 1 from verified suppliers |
| PATCH  | `/api/v1/supply-chain/links/{id}`            | Update link status                    |
| DELETE | `/api/v1/supply-chain/links/{id}`            | Remove supplier link                  |

#### Compliance (1)

| Method | Endpoint                    | Description                                    |
| ------ | --------------------------- | ---------------------------------------------- |
| POST   | `/api/v1/compliance/report` | Generate compliance report (GHG/CDP/TCFD/SBTi) |

#### Billing & Subscriptions (5)

| Method | Endpoint                        | Description                       |
| ------ | ------------------------------- | --------------------------------- |
| GET    | `/api/v1/billing/subscription`  | Get current subscription          |
| POST   | `/api/v1/billing/subscription`  | Change plan (free/pro/enterprise) |
| GET    | `/api/v1/billing/credits`       | Get credit balance                |
| GET    | `/api/v1/billing/plans`         | List available plans + limits     |
| POST   | `/api/v1/billing/credits/grant` | Admin: grant credits manually     |

#### Alerts (3)

| Method | Endpoint                          | Description                        |
| ------ | --------------------------------- | ---------------------------------- |
| GET    | `/api/v1/alerts`                  | List alerts (filterable by unread) |
| POST   | `/api/v1/alerts/{id}/acknowledge` | Acknowledge alert                  |
| POST   | `/api/v1/alerts/check`            | Trigger alert check manually       |

#### Data Marketplace (5)

| Method | Endpoint                                     | Description                                    |
| ------ | -------------------------------------------- | ---------------------------------------------- |
| POST   | `/api/v1/marketplace/listings`               | Create anonymized data listing (Pro+)          |
| GET    | `/api/v1/marketplace/listings`               | Browse marketplace (filter by industry/region) |
| POST   | `/api/v1/marketplace/listings/{id}/purchase` | Purchase listing with credits (Pro+)           |
| GET    | `/api/v1/marketplace/my-listings`            | List your own marketplace listings             |
| POST   | `/api/v1/marketplace/listings/{id}/withdraw` | Withdraw a listing from the marketplace        |

#### Webhooks (5)

| Method | Endpoint                           | Description                 |
| ------ | ---------------------------------- | --------------------------- |
| POST   | `/api/v1/webhooks/`                | Register webhook endpoint   |
| GET    | `/api/v1/webhooks/`                | List webhooks               |
| PATCH  | `/api/v1/webhooks/{id}`            | Toggle webhook active state |
| DELETE | `/api/v1/webhooks/{id}`            | Remove webhook              |
| GET    | `/api/v1/webhooks/{id}/deliveries` | List delivery logs          |

#### Audit & Health (2)

| Method | Endpoint              | Description                    |
| ------ | --------------------- | ------------------------------ |
| GET    | `/api/v1/audit-logs/` | List audit logs (paginated)    |
| GET    | `/health`             | Health check (DB connectivity) |

### Subscription Plans

| Feature          | Free | Pro ($99/mo) | Enterprise ($499/mo) |
| ---------------- | ---- | ------------ | -------------------- |
| Monthly Credits  | 100  | 1,000        | 10,000               |
| Reports/month    | 3    | Unlimited    | Unlimited            |
| Scenarios        | 5    | Unlimited    | Unlimited            |
| Questionnaires   | 3    | Unlimited    | Unlimited            |
| PDF Export       | ✗    | ✓            | ✓                    |
| Supply Chain     | ✗    | ✓            | ✓                    |
| Webhooks         | ✗    | ✓            | ✓                    |
| Data Marketplace | ✗    | ✓            | ✓                    |

## Emission Factor Datasets

| Dataset                   | Source         | Coverage                            |
| ------------------------- | -------------- | ----------------------------------- |
| EPA Stationary Combustion | US EPA         | 10 fuel types                       |
| EPA Mobile Combustion     | US EPA         | 8 vehicle types                     |
| eGRID Subregions          | US EPA         | 27 US subregions + state mapping    |
| IEA Grid Factors          | IEA            | 68 countries + regional averages    |
| DEFRA                     | UK BEIS        | UK-specific factors                 |
| Transport                 | GLEC Framework | Freight + passenger modes           |
| Industry Averages         | Multiple       | 9 industries with scope splits      |
| GWP AR6                   | IPCC           | CO2, CH4, N2O, SF6 + 9 refrigerants |

## GHG Protocol Coverage

- **Scope 1**: Stationary combustion, mobile combustion, fugitive emissions (refrigerant leaks)
- **Scope 2**: Location-based method, market-based method (with REC offset), purchased steam/heating
- **Scope 3**: Categories 1, 4, 5, 6, 7 (activity-based) + industry-default gap-filling for remaining categories

## Compliance Frameworks

- **GHG Protocol Corporate Standard** — Full inventory with all 15 Scope 3 categories
- **CDP Climate Change** — Questionnaire modules C0–C7
- **TCFD** — 4-pillar disclosure (Governance, Strategy, Risk Management, Metrics & Targets)
- **SBTi** — 11-year 1.5°C-aligned reduction pathway (4.2% annual Scope 1+2 reduction)

## Questionnaire Templates

5 pre-built templates for major sustainability frameworks:

- **CDP Climate Change** — 30 questions covering governance, risk management, emissions
- **EcoVadis Assessment** — 20 questions on environment, labor, supply chain
- **TCFD Disclosure** — 15 questions across 4 pillars
- **GHG Protocol Inventory** — 25 questions for complete emission inventory
- **CSRD/ESRS** — 35 questions for EU sustainability reporting

## Frontend

The Next.js 15 dashboard provides:

- **Dashboard** — KPI cards, scope breakdown chart, year-over-year trends
- **Data Upload** — Structured entry for Scope 1/2/3 activity data
- **Reports** — Paginated list with sorting, filtering, CSV/JSON export + PDF
- **Recommendations** — AI-generated reduction strategies per report
- **Questionnaires** — Document upload, AI extraction, human review, PDF export
- **Scenarios** — Interactive what-if builder with visual results
- **Supply Chain** — Supplier network management, Scope 3 propagation
- **Compliance** — Generate GHG Protocol / CDP / TCFD / SBTi reports
- **Marketplace** — Browse, purchase, create, and withdraw data listings
- **Alerts** — Emission threshold alerts with acknowledgement
- **Billing** — Subscription plans, credit balance, plan management
- **Audit Log** — Activity trail viewer with pagination
- **Settings** — User profile, password change, company profile, webhooks
- **Forgot / Reset Password** — Email-based password recovery flow
- **Mobile Responsive** — Hamburger menu navigation on small screens
- **Toast Notifications** — Success/error/info feedback system
- **Accessibility** — Skip-to-content, focus indicators, reduced motion support

```bash
cd frontend && npm install && npm run dev   # http://localhost:3000
```

## Troubleshooting

| Issue                                   | Solution                                                            |
| --------------------------------------- | ------------------------------------------------------------------- |
| `SECRET_KEY is using the default value` | Set `SECRET_KEY` env var (required in production: `ENV=production`) |
| `RuntimeError: SECRET_KEY must be set`  | Production mode enforces a real secret key                          |
| CORS errors                             | Add frontend URL to `ALLOWED_ORIGINS`                               |
| 429 Too Many Requests                   | Adjust `RATE_LIMIT_AUTH`/`RATE_LIMIT_DEFAULT`                       |
| Frontend can't reach backend            | Ensure backend on port 8000, check Next.js rewrites                 |
| SQLite locked under load                | Switch `DATABASE_URL` to PostgreSQL                                 |
| Bittensor timeout                       | Check wallet registration and `BT_QUERY_TIMEOUT`                    |

## License

MIT
