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
├── carbonscope/
│   ├── __init__.py
│   ├── protocol.py              # CarbonSynapse (bt.Synapse)
│   ├── scoring.py               # Composite scoring engine
│   ├── utils.py                 # Unit conversions, GWP helpers
│   ├── emission_factors/
│   │   ├── loader.py            # JSON dataset loader + grid factor cascade
│   │   ├── scope1.py            # Stationary/mobile combustion, fugitive
│   │   ├── scope2.py            # Location-based, market-based, steam
│   │   └── scope3.py            # 15 categories, spend-based, gap-filling
│   ├── validation/
│   │   ├── ghg_protocol.py      # GHG Protocol compliance checker
│   │   ├── sanity_checks.py     # Anti-hallucination detection
│   │   └── benchmark.py         # Industry benchmark alignment
│   └── test_cases/
│       └── generator.py         # 5 curated cases + synthetic generator
├── neurons/
│   ├── miner.py                 # Bittensor Axon server
│   └── validator.py             # Bittensor Dendrite client
├── api/                         # FastAPI platform backend
│   ├── main.py                  # App entry point + CORS + lifespan
│   ├── config.py                # Environment-based configuration
│   ├── database.py              # SQLAlchemy async engine + sessions
│   ├── models.py                # Company, User, DataUpload, EmissionReport, SupplyChainLink, Webhook
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── auth.py                  # JWT + password hashing (bcrypt)
│   ├── deps.py                  # FastAPI dependencies (current user)
│   ├── routes/
│   │   ├── auth_routes.py       # POST /register, /login
│   │   ├── company_routes.py    # GET/PATCH /company, CRUD /data
│   │   ├── carbon_routes.py     # POST /estimate, GET /reports, /dashboard
│   │   ├── ai_routes.py         # LLM parsing, prediction, recommendations
│   │   ├── supply_chain_routes.py  # Supplier/buyer linking, Scope 3 propagation
│   │   ├── compliance_routes.py # GHG Protocol, CDP, TCFD, SBTi reports
│   │   └── webhook_routes.py    # Webhook CRUD + HMAC-signed dispatch
│   └── services/
│       ├── subnet_bridge.py     # Bittensor dendrite client + local estimation
│       ├── llm_parser.py        # Rule-based + LLM unstructured text extraction
│       ├── prediction.py        # Revenue/employee-based emission prediction
│       ├── recommendations.py   # 11 reduction strategies with priority scoring
│       ├── supply_chain.py      # Buyer↔supplier linking + Scope 3 Cat 1 calc
│       ├── compliance.py        # GHG Protocol, CDP, TCFD, SBTi generators
│       └── webhooks.py          # Webhook dispatch with HMAC-SHA256 signing
├── frontend/                    # Next.js 15 + React 19 dashboard
│   └── src/
│       ├── lib/api.ts           # Typed API client
│       ├── lib/auth-context.tsx  # JWT auth context provider
│       ├── components/          # Navbar, ScopeChart
│       └── app/                 # App Router pages
│           ├── dashboard/       # KPI cards, scope chart, YoY trends
│           ├── upload/          # Structured data entry by scope
│           ├── reports/         # Report list + detail view
│           ├── recommendations/ # AI-powered reduction strategies
│           ├── supply-chain/    # Supplier network + Scope 3 propagation
│           ├── compliance/      # Framework report generator
│           └── settings/        # Company profile + webhook management
├── data/emission_factors/       # EPA, eGRID, IEA, DEFRA JSON datasets
├── scripts/
│   ├── register.sh
│   ├── run_miner.sh
│   └── run_validator.sh
├── tests/
├── requirements.txt
└── setup.py
```

## Prerequisites

- Python 3.10+
- Bittensor SDK >= 6.0.0

## Setup

```bash
# Clone and install
git clone <repo-url> && cd carbonscope
pip install -e ".[dev]"

# Or install dependencies directly
pip install -r requirements.txt
```

## Running on Testnet

### 1. Create wallets

```bash
# Miner wallet
btcli wallet create --wallet.name miner --wallet.hotkey default

# Validator wallet
btcli wallet create --wallet.name validator --wallet.hotkey default
```

### 2. Get testnet TAO

```bash
btcli wallet faucet --wallet.name miner --subtensor.network test
btcli wallet faucet --wallet.name validator --subtensor.network test
```

### 3. Register on subnet

```bash
# Using the script:
WALLET_NAME=miner ./scripts/register.sh
WALLET_NAME=validator ./scripts/register.sh

# Or manually:
btcli subnet register --wallet.name miner --netuid 1 --subtensor.network test
btcli subnet register --wallet.name validator --netuid 1 --subtensor.network test
```

### 4. Run miner

```bash
./scripts/run_miner.sh

# Or directly:
python -m neurons.miner \
    --netuid 1 \
    --wallet.name miner \
    --subtensor.network test \
    --axon.port 8091
```

### 5. Run validator

```bash
./scripts/run_validator.sh

# Or directly:
python -m neurons.validator \
    --netuid 1 \
    --wallet.name validator \
    --subtensor.network test \
    --query_interval 60
```

## Running Tests

```bash
pytest tests/ -v
```

## Platform API

The FastAPI backend provides a company-facing REST API for carbon accounting.

### Start the API server

```bash
# Development
uvicorn api.main:app --reload --port 8000

# With environment variables
SECRET_KEY=your-secret DATABASE_URL=sqlite+aiosqlite:///carbonscope.db uvicorn api.main:app --port 8000
```

### API Endpoints

#### Core

| Method | Endpoint                | Description               |
| ------ | ----------------------- | ------------------------- |
| POST   | `/api/v1/auth/register` | Register user + company   |
| POST   | `/api/v1/auth/login`    | Get JWT token             |
| GET    | `/api/v1/company`       | Get company profile       |
| PATCH  | `/api/v1/company`       | Update company profile    |
| POST   | `/api/v1/data`          | Upload operational data   |
| GET    | `/api/v1/data`          | List data uploads         |
| POST   | `/api/v1/estimate`      | Run emission estimation   |
| GET    | `/api/v1/reports`       | List emission reports     |
| GET    | `/api/v1/reports/{id}`  | Get specific report       |
| GET    | `/api/v1/dashboard`     | Company dashboard summary |
| GET    | `/health`               | Health check              |

#### AI Enhancement

| Method | Endpoint                          | Description                           |
| ------ | --------------------------------- | ------------------------------------- |
| POST   | `/api/v1/ai/parse-text`           | Extract emissions data from free text |
| POST   | `/api/v1/ai/predict`              | Predict missing emission categories   |
| POST   | `/api/v1/ai/audit-trail`          | Generate audit trail for a report     |
| GET    | `/api/v1/ai/recommendations/{id}` | Get reduction recommendations         |

#### Supply Chain

| Method | Endpoint                                     | Description                           |
| ------ | -------------------------------------------- | ------------------------------------- |
| POST   | `/api/v1/supply-chain/links`                 | Link a supplier                       |
| GET    | `/api/v1/supply-chain/suppliers`             | List your suppliers                   |
| GET    | `/api/v1/supply-chain/buyers`                | List companies buying from you        |
| GET    | `/api/v1/supply-chain/scope3-from-suppliers` | Scope 3 Cat 1 from verified suppliers |
| PATCH  | `/api/v1/supply-chain/links/{id}`            | Update link status (verify/reject)    |
| DELETE | `/api/v1/supply-chain/links/{id}`            | Remove supplier link                  |

#### Compliance

| Method | Endpoint                    | Description                                    |
| ------ | --------------------------- | ---------------------------------------------- |
| POST   | `/api/v1/compliance/report` | Generate compliance report (GHG/CDP/TCFD/SBTi) |

#### Webhooks

| Method | Endpoint                | Description                 |
| ------ | ----------------------- | --------------------------- |
| POST   | `/api/v1/webhooks/`     | Register webhook endpoint   |
| GET    | `/api/v1/webhooks/`     | List webhooks               |
| PATCH  | `/api/v1/webhooks/{id}` | Toggle webhook active state |
| DELETE | `/api/v1/webhooks/{id}` | Remove webhook              |

Interactive docs available at `http://localhost:8000/docs` (Swagger UI).

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

## AI Enhancement Layer

- **LLM Text Parsing** — Extract structured emissions data from unstructured text (sustainability reports, invoices). Uses Claude/GPT when API keys are available, falls back to 14-regex rule-based extraction.
- **Missing Data Prediction** — Revenue-based and employee-based emission estimation with industry intensity factors across 9 industries. Provides uncertainty bounds (±20–50%).
- **Reduction Recommendations** — 11 prioritized strategies across Scope 1/2/3 with CO₂ savings, cost tiers, payback periods, and co-benefits. Priority scoring: impact 50%, cost 30%, ease 20%.

## Compliance Frameworks

- **GHG Protocol Corporate Standard** — Full inventory with all 15 Scope 3 categories
- **CDP Climate Change** — Questionnaire modules C0–C7
- **TCFD** — 4-pillar disclosure (Governance, Strategy, Risk Management, Metrics & Targets)
- **SBTi** — 11-year 1.5°C-aligned reduction pathway (4.2% annual Scope 1+2 reduction)

## Frontend

The Next.js 15 dashboard provides:

- **Dashboard** — KPI cards, scope breakdown chart, year-over-year trends
- **Data Upload** — Structured entry for Scope 1/2/3 activity data
- **Reports** — List and detail view with scope charts and confidence meters
- **Recommendations** — AI-generated reduction strategies per report
- **Supply Chain** — Supplier network management, Scope 3 Category 1 propagation
- **Compliance** — Generate and download GHG Protocol / CDP / TCFD / SBTi reports
- **Settings** — Company profile management + webhook configuration

### Start the frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

The frontend proxies `/api/*` requests to the FastAPI backend at `http://localhost:8000`.

## License

MIT
