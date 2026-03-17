# Architecture

> System design, data flow, database schema, and service architecture for CarbonScope.

---

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Bittensor Subnet Layer](#bittensor-subnet-layer)
- [FastAPI Backend](#fastapi-backend)
- [Frontend Dashboard](#frontend-dashboard)
- [Database Schema](#database-schema)
- [Authentication & Authorization](#authentication--authorization)
- [Service Layer](#service-layer)
- [Data Flow](#data-flow)
- [Security Architecture](#security-architecture)
- [Deployment Architecture](#deployment-architecture)

---

## System Overview

CarbonScope is a three-tier application built on top of the Bittensor decentralized network:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Client Layer                                     │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Next.js 15 Dashboard (React 19, Tailwind CSS 4, Recharts)       │   │
│  │  26 App Router pages · Typed API client · JWT auth context       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                        API Layer                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Backend (Python 3.10+)                                  │   │
│  │  19 Route Modules · 26 Services · 100+ Endpoints                 │   │
│  │  JWT Auth · Rate Limiting · CORS · Security Headers              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                        Data Layer                                       │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────────┐    │
│  │  PostgreSQL /  │  │  Bittensor     │  │  Emission Factor        │    │
│  │  SQLite (dev)  │  │  Subnet        │  │  Datasets (JSON)        │    │
│  │  24 models     │  │  Miners +      │  │  EPA, eGRID, IEA,       │    │
│  │  Alembic mgr.  │  │  Validators    │  │  DEFRA, GLEC, IPCC      │    │
│  └────────────────┘  └────────────────┘  └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### High-Level Component Diagram

```
                           ┌─────────────────────┐
                           │    Web Browser      │
                           │  (Next.js Frontend) │
                           └──────────┬──────────┘
                                      │ HTTPS
                                      ▼
                           ┌─────────────────────┐
                           │   Nginx / Reverse   │
                           │   Proxy (TLS)       │
                           └──────────┬──────────┘
                              ┌───────┴────────┐
                              ▼                ▼
                   ┌─────────────────┐ ┌──────────────┐
                   │  FastAPI        │ │  Next.js     │
                   │  Backend        │ │  Server      │
                   │  :8000          │ │  :3000       │
                   └───────┬─────┬──-┘ └──────────────┘
                      ┌────┘     └────┐
                      ▼               ▼
          ┌─────────────────┐ ┌───────────────────┐
          │  PostgreSQL     │ │  Bittensor        │
          │  Database       │ │  Network          │
          │  :5432          │ │  (Dendrite RPC)   │
          └─────────────────┘ └───────────────────┘
```

---

## Bittensor Subnet Layer

### Synapse Protocol

The `CarbonSynapse` extends `bt.Synapse` and defines the communication contract between validators and miners:

```
Validator                                    Miner
┌────────────────────┐   CarbonSynapse      ┌──────────────────────┐
│                    │   (questionnaire,     │                      │
│  1. Generate query │   context)            │  3. Parse input      │
│     - Curated 70%  ├────────────────────►  │  4. Calculate S1     │
│     - Synthetic 30%│                       │  5. Calculate S2     │
│                    │   CarbonSynapse       │  6. Calculate S3     │
│  2. Send via       │   (emissions,         │  7. Build breakdown  │
│     Dendrite       │   breakdown,          │  8. Assess confidence│
│                    │◄────────────────────  │  9. Track sources    │
│  8. Score response │   confidence,         │                      │
│  9. Update EMA     │   sources,            └──────────────────────┘
│ 10. Set weights    │   assumptions)
└────────────────────┘
```

#### Request Payload (Validator → Miner)

```python
questionnaire = {
    "company": str,              # Company name/ID
    "industry": str,             # e.g., manufacturing, technology, retail
    "services_used": list[str],  # Relevant services
    "provided_data": {
        "fuel_use_liters": float,         # Scope 1: Fuel consumption
        "fuel_type": str,                 # Scope 1: Fuel category
        "natural_gas_m3": float,          # Scope 1: Natural gas usage
        "electricity_kwh": float,         # Scope 2: Electricity consumption
        "vehicle_km": float,              # Scope 1: Fleet distance
        "employee_count": int,            # Scope 3: Commuting basis
        "revenue_usd": float,             # Scope 3: Spend-based estimation
        "supplier_spend_usd": float,      # Scope 3 Cat 1
        "shipping_ton_km": float,         # Scope 3 Cat 4
        "office_sqm": float,              # Scope 2: Building energy
        "business_travel_usd": float,     # Scope 3 Cat 6
        "waste_kg": float,                # Scope 3 Cat 5
        "refrigerant_type": str,          # Scope 1: Fugitive emissions
        "refrigerant_kg_leaked": float,   # Scope 1: Refrigerant leak
        "rec_kwh": float,                 # Scope 2: Renewable credits
    },
    "region": str,                # ISO-2 country code / US state / eGRID subregion
    "year": int,                  # Reporting year
}
```

#### Response Payload (Miner → Validator)

```python
emissions = {
    "scope1": float,   # kgCO₂e — direct emissions
    "scope2": float,   # kgCO₂e — purchased energy
    "scope3": float,   # kgCO₂e — value chain
    "total": float,    # kgCO₂e — sum of all scopes
}

breakdown = {
    "scope1_detail": {
        "stationary_combustion": float,
        "mobile_combustion": float,
        "fugitive_emissions": float,
    },
    "scope2_detail": {
        "location_based": float,
        "market_based": float,
    },
    "scope3_detail": {
        "cat1_purchased_goods": float,
        "cat4_upstream_transport": float,
        "cat5_waste": float,
        "cat6_business_travel": float,
        "cat7_commuting": float,
    },
}
```

### Scoring Engine

The validator scores each miner response using a 5-axis composite score:

```
Final Score = (0.40 × Accuracy)
            + (0.25 × GHG Compliance)
            + (0.15 × Completeness)
            + (0.15 × Anti-Hallucination)
            + (0.05 × Benchmark)
```

| Axis                   | Logic                                                                                       |
| :--------------------- | :------------------------------------------------------------------------------------------ |
| **Accuracy**           | Weighted MAPE: `1 - Σ(weight_i × min(APE_i, 1.0))` where S1=30%, S2=20%, S3=50%             |
| **GHG Compliance**     | Checks: `total == S1+S2+S3`, all values ≥ 0, scope categories are correct                   |
| **Completeness**       | 5 binary checks: emissions dict, breakdown dict, confidence, sources list, assumptions list |
| **Anti-Hallucination** | Rejects physically impossible values (negative, extreme outliers outside industry ranges)   |
| **Benchmark**          | Compares scope-split ratios against industry averages from reference databases              |

### Weight Setting

- **Algorithm:** Exponential Moving Average (EMA) with α = 0.1
- **Update frequency:** Every network tempo blocks (fallback: every 100 blocks)
- **Formula:** `score[uid] = (1 - α) × score[uid] + α × latest_score`
- **Normalization:** Scores normalized to sum to 1.0 before on-chain `set_weights()` call
- **Circuit breaker:** 3 consecutive failures → exponential backoff (2s → 60s max)

---

## FastAPI Backend

### Application Lifecycle

```
App Startup
    │
    ├── Create async DB engine (SQLite or PostgreSQL)
    ├── Initialize tables (development only — skip in production)
    ├── Start background scheduler
    │       ├── Alert check task (periodic)
    │       └── Monthly credit reset task
    └── Register 19 route modules at /api/v1/

App Shutdown
    └── Stop background scheduler
```

### Middleware Stack (execution order)

```
Request ──► RequestIDMiddleware ──► RequestBodyLimitMiddleware ──► RequestLoggingMiddleware
        ──► SecurityHeadersMiddleware ──► CORS Middleware ──► Rate Limiter
        ──► Route Handler ──► Global Exception Handler ──► Response
```

| Middleware                      | Purpose                                                          |
| :------------------------------ | :--------------------------------------------------------------- |
| **RequestIDMiddleware**         | Generates/propagates `X-Request-ID` header for tracing           |
| **RequestBodyLimitMiddleware**  | Rejects payloads > 10 MB before route processing                 |
| **RequestLoggingMiddleware**    | Logs `METHOD PATH STATUS DURATION [request_id]`                  |
| **SecurityHeadersMiddleware**   | Injects CSP, X-Frame-Options, HSTS, X-Content-Type-Options, etc. |
| **CORSMiddleware**              | `ALLOWED_ORIGINS` enforcement with credentials support           |
| **SlowAPI Rate Limiter**        | IP-based rate limiting (auth: 10/min, default: 60/min)           |
| **Global Exception Handler**    | Catches unhandled exceptions → 500 JSON with request ID          |

### Route Modules (19)

| Module                 | Prefix            | Endpoints | Auth Required |
| :--------------------- | :---------------- | :-------: | :-----------: |
| `auth_routes`          | `/auth`           |    10     |    Partial    |
| `company_routes`       | (none)            |     7     |      Yes      |
| `carbon_routes`        | (none)            |     8     |      Yes      |
| `ai_routes`            | `/ai`             |     4     |      Yes      |
| `questionnaire_routes` | `/questionnaires` |    11     |      Yes      |
| `scenario_routes`      | `/scenarios`      |     6     |      Yes      |
| `supply_chain_routes`  | `/supply-chain`   |     7     |      Yes      |
| `compliance_routes`    | `/compliance`     |     1     |      Yes      |
| `billing_routes`       | `/billing`        |     6     |      Yes      |
| `alert_routes`         | `/alerts`         |     3     |      Yes      |
| `marketplace_routes`   | `/marketplace`    |     6     |      Yes      |
| `webhook_routes`       | `/webhooks`       |     5     |      Yes      |
| `audit_routes`         | `/audit-logs`     |     1     |     Admin     |
| `stripe_routes`        | `/stripe`         |     1     |    Webhook    |
| `benchmark_routes`     | `/benchmarks`     |     2     |      Yes      |
| `mfa_routes`           | `/mfa`            |     5     |      Yes      |
| `pcaf_routes`          | `/pcaf`           |     6     |      Yes      |
| `review_routes`        | `/reviews`        |     4     |      Yes      |
| `events_routes`        | `/events`         |     1     |      Yes      |

### Service Layer (26 modules)

| Service              | Responsibility                                                          |
| :------------------- | :---------------------------------------------------------------------- |
| `subnet_bridge.py`   | Bridges FastAPI to Bittensor network; local estimation fallback         |
| `llm_parser.py`      | LLM-powered text extraction (OpenAI/Anthropic with rule-based fallback) |
| `prediction.py`      | Industry-based statistical prediction for missing data                  |
| `recommendations.py` | 11 reduction strategies with cost-benefit analysis                      |
| `supply_chain.py`    | Buyer↔supplier linking, Scope 3 Category 1 aggregation                  |
| `compliance.py`      | GHG Protocol, CDP, TCFD, SBTi report templates                          |
| `webhooks.py`        | HMAC-SHA256 signing, delivery with exponential backoff                  |
| `audit.py`           | Action logging (resource type, IDs, details)                            |
| `questionnaire.py`   | PDF/DOCX/XLSX/CSV parsing via pdfplumber, python-docx, openpyxl         |
| `pdf_export.py`      | ReportLab PDF generation for reports and compliance                     |
| `scenarios.py`       | Parameter-based emission projection engine                              |
| `subscriptions.py`   | Plan tiers, credit deduction, monthly reset                             |
| `alerts.py`          | Emission change detection, alert creation                               |
| `marketplace.py`     | Data anonymization, listing/purchase workflow                           |
| `templates.py`       | 5 pre-built questionnaire templates                                     |
| `email.py`           | Async SMTP email notifications (aiosmtplib)                             |
| `event_bus.py`       | In-process SSE pub/sub for real-time push to connected clients          |
| `scheduler.py`       | Background task scheduling + SSE event publishing                       |
| `url_validator.py`   | SSRF protection for webhook URLs                                        |
| `reviews.py`         | Data review workflow (create, list, approve/reject/request_changes)     |
| `benchmarks.py`      | Industry benchmark comparison with percentile ranking                   |
| `mfa.py`             | TOTP encryption/decryption helpers for MFA secrets at rest              |
| `ai.py`              | AI-powered analysis, parsing orchestration, multi-provider support      |
| `carbon.py`          | Core carbon calculation logic and emission factor lookups               |
| `company.py`         | Company CRUD, tenant-scoped data operations                             |
| `pcaf.py`            | PCAF financed emissions portfolio & asset calculations                  |

### Dependency Injection

| Dependency                   | Purpose                                                        |
| :--------------------------- | :------------------------------------------------------------- |
| `get_db()`                   | Async SQLAlchemy session (auto-commit/rollback)                |
| `get_current_user()`         | JWT validation (Bearer token + cookie), revocation check, CSRF |
| `require_admin()`            | Admin role enforcement                                         |
| `require_plan(feature)`      | Subscription plan feature gating                               |
| `require_credits(operation)` | Credit balance check + automatic deduction                     |

---

## Frontend Dashboard

### Technology Stack

| Technology   | Version | Purpose                         |
| :----------- | :------ | :------------------------------ |
| Next.js      | 15.5    | React framework with App Router |
| React        | 19.2    | UI library                      |
| Tailwind CSS | 4.2     | Utility-first styling           |
| Recharts     | 2.15    | Chart visualization             |
| Vitest       | 4.0     | Unit testing framework          |
| TypeScript   | 5.9     | Type safety                     |

### Page Routes (26)

```
/                        → Dashboard (KPI cards, scope charts, trends)
/upload                  → Data upload (structured Scope 1/2/3 entry)
/reports                 → Report listing (sort, filter, export)
/reports/[id]            → Report detail (breakdown, sources, PDF export)
/recommendations         → Report index for AI reduction strategies
/recommendations/[reportId] → AI reduction strategies for a specific report
/questionnaires          → Questionnaire management
/questionnaires/[id]     → Questionnaire detail (review questions)
/scenarios               → Scenario listing, creation, compute
/supply-chain            → Supplier network
/compliance              → Compliance report generation
/marketplace             → Data marketplace
/marketplace/seller      → Seller dashboard (revenue, sales)
/alerts                  → Alert management
/billing                 → Subscription & credits
/audit-log               → Activity trail viewer
/settings                → User & company settings
/login                   → Authentication
/register                → Account creation
/forgot-password         → Password reset flow
/reset-password          → Password reset with token
/mfa                     → MFA setup & management
/pcaf                    → PCAF financed emissions portfolios
/benchmarks              → Industry benchmark comparisons
/reviews                 → Data review & approval workflow
```

### API Client Architecture

The frontend uses a typed API client (`lib/api.ts`) with 65+ functions that:

1. Automatically attaches JWT Bearer tokens from `localStorage`
2. Handles 401 responses with automatic token refresh
3. Retries failed requests after refresh
4. Provides type-safe request/response interfaces

---

## Database Schema

### Entity-Relationship Overview

```
┌──────────┐     ┌──────────┐     ┌───────────────┐
│ Company  │────<│   User   │     │ DataUpload    │
│          │     │          │     │               │
│          │────<│          │     │  company_id   │>────┐
└────┬─────┘     └──────────┘     └───────────────┘     │
     │                                                   │
     ├────<┌───────────────┐     ┌───────────────┐      │
     │     │EmissionReport │     │   Scenario    │      │
     │     │  company_id   │<────│base_report_id │      │
     │     └───────────────┘     │  company_id   │>─────┤
     │                           └───────────────┘      │
     ├────<┌───────────────┐                             │
     │     │SupplyChainLink│  (buyer_company_id +       │
     │     │               │   supplier_company_id)      │
     │     └───────────────┘                             │
     │                                                   │
     ├────<┌───────────────┐     ┌───────────────┐      │
     │     │   Webhook     │────<│WebhookDelivery│      │
     │     │  company_id   │     │  webhook_id   │      │
     │     └───────────────┘     └───────────────┘      │
     │                                                   │
     ├────<┌───────────────┐     ┌───────────────────┐  │
     │     │Questionnaire  │────<│QuestionnaireQ     │  │
     │     │  company_id   │     │questionnaire_id   │  │
     │     └───────────────┘     └───────────────────┘  │
     │                                                   │
     ├────<┌───────────────┐                             │
     │     │ Subscription  │  (unique per company)       │
     │     │  company_id   │                             │
     │     └───────────────┘                             │
     │                                                   │
     ├────<┌───────────────┐                             │
     │     │ CreditLedger  │                             │
     │     │  company_id   │                             │
     │     └───────────────┘                             │
     │                                                   │
     ├────<┌───────────────┐                             │
     │     │    Alert      │                             │
     │     │  company_id   │                             │
     │     └───────────────┘                             │
     │                                                   │
     ├────<┌───────────────┐     ┌───────────────┐      │
     │     │ DataListing   │────<│ DataPurchase  │      │
     │     │seller_company │     │buyer_company  │>─────┘
     │     └───────────────┘     └───────────────┘
     │
     └────<┌───────────────┐
           │   AuditLog    │
           │  company_id   │
           └───────────────┘
```

### Constraints & Indexes

| Constraint  | Table            | Rule                                        |
| :---------- | :--------------- | :------------------------------------------ |
| CHECK       | EmissionReport   | `scope1 >= 0`, `scope2 >= 0`, `scope3 >= 0` |
| CHECK       | EmissionReport   | `confidence >= 0.0 AND confidence <= 1.0`   |
| CHECK       | CreditLedger     | `balance_after >= 0`                        |
| UNIQUE      | Subscription     | One subscription per company                |
| UNIQUE      | SupplyChainLink  | One link per buyer-supplier pair            |
| UNIQUE      | User             | Email address                               |
| FOREIGN KEY | All child tables | Cascade to parent company/user              |

### Soft Deletes

The following models support soft deletion via `deleted_at` timestamp:

- Company, User, DataUpload, EmissionReport, SupplyChainLink, Webhook, Questionnaire, Scenario, Subscription, DataListing, FinancedPortfolio

Soft-deleted records are excluded from queries by default but retained in the database for audit purposes.

---

## Authentication & Authorization

### Token Lifecycle

```
Register/Login
    │
    ├── Issue JWT Access Token (60 min, HS256, JTI claim)
    └── Issue Refresh Token (30 days, SHA-256 hashed in DB)

Access Token Expired
    │
    └── POST /auth/refresh (refresh_token in body)
        ├── Validate + consume old refresh token (single-use)
        ├── Issue new access token
        └── Issue new refresh token (rotation)

Logout
    │
    ├── Add access token JTI to RevokedToken table
    └── Revoke all refresh tokens for user
```

### Authorization Layers

| Layer                 | Mechanism                                                       |
| :-------------------- | :-------------------------------------------------------------- |
| **Authentication**    | JWT Bearer token or httpOnly cookie (`access_token`)            |
| **Token Revocation**  | JTI-based blacklist checked on every request                    |
| **CSRF Protection**   | Double-submit cookie pattern for state-changing methods         |
| **Role-Based Access** | `admin` / `member` roles; admin-only routes for audit logs      |
| **Plan Gating**       | Feature access controlled by subscription tier                  |
| **Credit Gating**     | Operations deduct credits; 402 if insufficient balance          |
| **Tenant Isolation**  | All queries scoped to `company_id`; cross-tenant access blocked |
| **Account Lockout**   | 5 failed login attempts → 15-minute lockout                     |

---

## Data Flow

### Emission Estimation Flow

```
User uploads data                   API receives DataUpload
       │                                    │
       ▼                                    ▼
POST /api/v1/estimate              Check credits (10 credits)
       │                                    │
       ▼                                    ▼
┌──────────────────┐           ┌──────────────────────┐
│ ESTIMATION_MODE  │           │                      │
│                  │           │  Mode == "subnet"?   │
│  local │ subnet  │           │                      │
└───┬────┴────┬────┘           └──────┬───────┬───────┘
    │         │                   Yes │       │ No
    ▼         ▼                       ▼       ▼
┌────────┐ ┌──────────────┐  ┌───────────┐ ┌──────────┐
│ Local  │ │ Bittensor    │  │ Query     │ │ Local    │
│ Engine │ │ Dendrite     │  │ Miners    │ │ Calc     │
│        │ │ → Miners     │  │ Score     │ │ Engine   │
│ S1/S2/ │ │ → Score      │  │ Select    │ │          │
│ S3 calc│ │ → Select     │  │ Best      │ │ S1/S2/S3 │
└───┬────┘ └──────┬───────┘  └─────┬─────┘ └────┬─────┘
    │              │               │              │
    └──────────────┴───────────────┴──────────────┘
                        │
                        ▼
              Store EmissionReport
                        │
                        ▼
              Fire webhook events
              Log to AuditLog
              Return to client
```

### Questionnaire Processing Flow

```
Upload PDF/DOCX/XLSX/CSV
         │
         ▼
  Parse document content
  (pdfplumber / python-docx / openpyxl)
         │
         ▼
  Extract questions (AI or rule-based)
         │
         ▼
  Generate AI draft answers
         │
         ▼
  Human review & approval
         │
         ▼
  Export final PDF report
```

---

## Security Architecture

See [SECURITY.md](SECURITY.md) for the complete security policy and vulnerability reporting process.

### Security Controls Summary

| Control                    | Implementation                                                      |
| :------------------------- | :------------------------------------------------------------------ |
| **Authentication**         | JWT HS256 with JTI, bcrypt password hashing                         |
| **Token Security**         | Single-use refresh rotation, JTI revocation blacklist               |
| **Password Policy**        | ≥ 8 chars, uppercase + lowercase + digit + special character        |
| **Account Lockout**        | 5 failed attempts → 15-minute lockout                               |
| **CSRF**                   | Double-submit cookie for state-changing requests                    |
| **Rate Limiting**          | SlowAPI with IP-based bucketing (proxy-aware)                       |
| **Security Headers**       | CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| **SSRF Protection**        | URL validation blocks private IPs, localhost, and internal networks |
| **Tenant Isolation**       | All queries scoped to company_id; no cross-tenant data access       |
| **Soft Deletes**           | Data retained for audit; hard delete only via GDPR endpoint         |
| **Audit Logging**          | All state-changing operations logged with user, action, resource    |
| **Webhook Security**       | HMAC-SHA256 signature on all payloads                               |
| **Production Enforcement** | SECRET_KEY validation, SQLite rejection, structured logging         |
| **MFA (TOTP)**             | Optional two-factor via TOTP; encrypted secrets at rest (Fernet)    |
| **Request Body Limit**     | 10 MB payload cap enforced before route processing                  |
| **PII Masking**            | Email addresses redacted in production logs                         |

---

## Deployment Architecture

### Single-Server Deployment

```
                    ┌──────────────────────────┐
                    │       Nginx              │
                    │   TLS Termination        │
                    │   /:3000  /api/:8000     │
                    └──────────┬───────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │   Next.js    │ │   FastAPI    │ │  PostgreSQL  │
     │   :3000      │ │   :8000     │ │   :5432      │
     │   (PM2)      │ │  (Uvicorn   │ │              │
     │              │ │   4 workers) │ │              │
     └──────────────┘ └──────────────┘ └──────────────┘
```

### Docker Composition

```
┌─────────────────────────────────────────────┐
│              docker-compose.prod.yml          │
│                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │    db    │  │ backend  │  │ frontend │  │
│  │ Postgres │  │ FastAPI  │  │ Next.js  │  │
│  │ 16-alpine│  │ Uvicorn  │  │ Standalone│  │
│  │ 512M/1CPU│  │ 1G/2CPU  │  │ 512M/1CPU│  │
│  └──────────┘  └──────────┘  └──────────┘  │
│       │              │              │        │
│       └── pgdata ────┘              │        │
│              depends_on: db         │        │
│                     depends_on: backend      │
└─────────────────────────────────────────────┘
```

> **Full deployment instructions:** See [DEPLOYMENT.md](DEPLOYMENT.md) for Nginx, systemd, TLS, and scaling guides.

### Kubernetes Deployment

Production Kubernetes manifests in `k8s/` include:

| Resource             | Purpose                                                             |
| :------------------- | :------------------------------------------------------------------ |
| **backend.yaml**     | Deployment (2 replicas) + Service; startup/readiness/liveness probes |
| **frontend.yaml**    | Deployment (2 replicas) + Service; readOnly root filesystem          |
| **postgres.yaml**    | StatefulSet with persistent volume                                  |
| **redis.yaml**       | Deployment for optional caching layer                               |
| **hpa.yaml**         | HPA for backend (2-8 pods, CPU/memory) + frontend (2-4 pods)        |
| **pdb.yaml**         | PodDisruptionBudgets for zero-downtime rollouts                     |
| **ingress.yaml**     | Ingress with TLS termination                                        |
| **monitoring.yaml**  | Prometheus ServiceMonitor + PrometheusRule alerts                    |
| **network-policy.yaml** | Namespace-scoped network isolation                                |
| **cronjob-backup.yaml** | Scheduled PostgreSQL backups to S3                                |
| **external-secrets.yaml** | AWS Secrets Manager integration via ExternalSecrets operator    |

#### Health Probes

| Probe         | Path            | Purpose                               |
| :------------ | :-------------- | :------------------------------------ |
| **Liveness**  | `/health/live`  | Process alive (no dependency checks)  |
| **Readiness** | `/health`       | DB connected, ready to serve traffic  |
| **Startup**   | `/health/live`  | Allows 60s for cold start before liveness kicks in |
