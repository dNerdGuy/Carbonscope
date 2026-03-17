# CarbonScope — API Reference

> Complete reference for the CarbonScope Platform API (97+ endpoints).

**Base URL:** `/api/v1/`  
**Auth:** JWT Bearer token (`Authorization: Bearer <token>`) or httpOnly cookie  
**Content-Type:** `application/json` (unless noted)  
**Interactive Docs:** `http://localhost:8000/docs` (Swagger UI) · `http://localhost:8000/redoc` (ReDoc)

---

## Table of Contents

- [Authentication](#authentication)
- [Company & Data](#company--data)
- [Carbon Estimation & Reports](#carbon-estimation--reports)
- [AI Enhancement](#ai-enhancement)
- [Questionnaires](#questionnaires)
- [What-If Scenarios](#what-if-scenarios)
- [Supply Chain](#supply-chain)
- [Compliance Reporting](#compliance-reporting)
- [PCAF Financed Emissions](#pcaf-financed-emissions)
- [Data Reviews](#data-reviews)
- [MFA (TOTP)](#mfa-totp)
- [Industry Benchmarks](#industry-benchmarks)
- [Billing & Subscriptions](#billing--subscriptions)
- [Alerts](#alerts)
- [Data Marketplace](#data-marketplace)
- [Webhooks](#webhooks)
- [Stripe Webhooks](#stripe-webhooks)
- [Audit Logs](#audit-logs)
- [Health & Metrics](#health--metrics)
- [Common Patterns](#common-patterns)
- [Error Responses](#error-responses)
- [Versioning Strategy](#versioning-strategy)

---

## Authentication

All auth endpoints are at `/api/v1/auth`.

### Register

```
POST /auth/register
```

Create a new user and company.

**Request Body** (`UserRegister`):

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!",
  "name": "Jane Doe",
  "company_name": "Acme Corp",
  "industry": "manufacturing",
  "region": "US"
}
```

**Response** `201` (`UserOut`):

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Jane Doe",
  "role": "admin",
  "company_id": 1,
  "is_active": true
}
```

---

### Login

```
POST /auth/login
```

Authenticate user and receive JWT access token + refresh token.

**Request Body** (`UserLogin`):

```json
{
  "email": "user@example.com",
  "password": "StrongPass123!"
}
```

**Response** `200` (`TokenWithRefresh`):

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "refresh_token": "a1b2c3d4e5..."
}
```

Also sets `access_token` and `csrf_token` httpOnly cookies.

---

### Get Current User

```
GET /auth/me
Authorization: Bearer <token>
```

**Response** `200` (`UserOut`):

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Jane Doe",
  "role": "admin",
  "company_id": 1,
  "is_active": true
}
```

---

### Update Profile

```
PATCH /auth/me
Authorization: Bearer <token>
```

**Request Body** (`UserProfileUpdate`):

```json
{
  "name": "Jane Smith",
  "email": "jane.smith@example.com"
}
```

**Response** `200` (`UserOut`)

---

### Change Password

```
POST /auth/change-password
Authorization: Bearer <token>
```

**Request Body** (`PasswordChange`):

```json
{
  "current_password": "OldPass123!",
  "new_password": "NewPass456!"
}
```

**Response** `204 No Content`

---

### Delete Account (GDPR)

```
DELETE /auth/me
Authorization: Bearer <token>
```

Soft-deletes the user account and anonymizes data.

**Response** `204 No Content`

---

### Refresh Token

```
POST /auth/refresh
```

Exchange a refresh token for a new access token + refresh token pair (single-use rotation).

**Request Body** (`RefreshRequest`):

```json
{
  "refresh_token": "a1b2c3d4e5..."
}
```

**Response** `200` (`TokenWithRefresh`)

---

### Logout

```
POST /auth/logout
Authorization: Bearer <token>
```

Revokes the current access token and all refresh tokens for the user.

**Response** `204 No Content`

---

### Forgot Password

```
POST /auth/forgot-password
```

Request a password reset email. Rate-limited.

**Request Body** (`ForgotPasswordRequest`):

```json
{
  "email": "user@example.com"
}
```

**Response** `204 No Content` (always returns 204, even if email not found, to prevent enumeration)

---

### Reset Password

```
POST /auth/reset-password
```

Reset password using the token received via email.

**Request Body** (`ResetPasswordRequest`):

```json
{
  "token": "reset-token-from-email",
  "new_password": "NewSecurePass123!"
}
```

**Response** `204 No Content`

---

## Company & Data

### Get Company

```
GET /company
Authorization: Bearer <token>
```

Returns the current user's company profile.

**Response** `200` (`CompanyOut`):

```json
{
  "id": 1,
  "name": "Acme Corp",
  "industry": "manufacturing",
  "region": "US",
  "revenue_usd": 50000000,
  "employee_count": 500
}
```

---

### Update Company

```
PATCH /company
Authorization: Bearer <token>  (Admin only)
```

**Request Body** (`CompanyUpdate`):

```json
{
  "name": "Acme Corporation",
  "industry": "manufacturing",
  "revenue_usd": 55000000,
  "employee_count": 520
}
```

**Response** `200` (`CompanyOut`)

---

### Upload Operational Data

```
POST /data
Authorization: Bearer <token>
```

**Request Body** (`DataUploadCreate`):

```json
{
  "year": 2024,
  "provided_data": {
    "fuel_use_liters": 50000,
    "fuel_type": "diesel",
    "electricity_kwh": 2000000,
    "natural_gas_m3": 10000,
    "vehicle_km": 200000,
    "employee_count": 500,
    "revenue_usd": 50000000,
    "supplier_spend_usd": 15000000,
    "shipping_ton_km": 500000,
    "office_sqm": 5000,
    "business_travel_usd": 200000,
    "waste_kg": 50000,
    "region": "US"
  },
  "notes": "FY2024 operational data"
}
```

**Response** `201` (`DataUploadOut`)

---

### List Data Uploads

```
GET /data?year=2024&limit=50&offset=0
Authorization: Bearer <token>
```

Paginated, filterable by year.

**Response** `200` (`PaginatedResponse[DataUploadOut]`):

```json
{
  "items": [...],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

---

### Get / Update / Delete Data Upload

```
GET    /data/{upload_id}
PATCH  /data/{upload_id}
DELETE /data/{upload_id}
```

`PATCH` accepts `DataUploadUpdate` (update notes/fields). `DELETE` performs soft-delete. Returns `204 No Content`.

---

## Carbon Estimation & Reports

### Run Emission Estimation

```
POST /estimate
Authorization: Bearer <token>
```

Requires credits (`estimate` operation — 10 credits). Rate-limited to **5 requests/minute**. Runs estimation on a data upload using the local engine or Bittensor subnet.

**Request Body** (`EstimateRequest`):

```json
{
  "upload_id": 1
}
```

**Response** `201` (`EmissionReportOut`):

```json
{
  "id": 1,
  "company_id": 1,
  "upload_id": 1,
  "year": 2024,
  "scope1": 125400.5,
  "scope2": 890200.0,
  "scope3": 3450000.0,
  "total": 4465600.5,
  "breakdown": {
    "scope1_detail": {
      "stationary_combustion": 50200.0,
      "mobile_combustion": 65000.5,
      "fugitive_emissions": 10200.0
    },
    "scope2_detail": {
      "location_based": 890200.0,
      "market_based": 780100.0
    },
    "scope3_detail": {
      "cat1_purchased_goods": 1500000.0,
      "cat4_upstream_transport": 750000.0,
      "cat5_waste": 100000.0,
      "cat6_business_travel": 600000.0,
      "cat7_commuting": 500000.0
    }
  },
  "confidence": 0.85,
  "data_sources": ["EPA", "eGRID", "IEA"],
  "assumptions": ["Industry average used for Scope 3 Cat 1"],
  "notes": null,
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### List Reports

```
GET /reports?year=2024&confidence_min=0.7&sort_by=created_at&order=desc&limit=50&offset=0
Authorization: Bearer <token>
```

Paginated, filterable by year and confidence threshold, sortable.

**Response** `200` (`PaginatedResponse[EmissionReportOut]`)

---

### Export Reports

```
GET /reports/export?format=csv
GET /reports/export?format=json
Authorization: Bearer <token>
```

Returns a streaming response with all reports in CSV or JSON format.

---

### Get / Update / Delete Report

```
GET    /reports/{report_id}
PATCH  /reports/{report_id}       — Update year/notes (ReportUpdate)
DELETE /reports/{report_id}       — Soft-delete → 204
```

---

### Export Report as PDF

```
GET /reports/{report_id}/export/pdf
Authorization: Bearer <token>
```

Requires credits (`pdf_export` operation — 5 credits). Returns a styled PDF with scope breakdown, charts, and metadata.

**Response:** `StreamingResponse` (`application/pdf`)

---

### Dashboard Summary

```
GET /dashboard
Authorization: Bearer <token>
```

**Response** `200` (`DashboardSummary`):

```json
{
  "latest_report": { ... },
  "total_reports": 12,
  "total_uploads": 15,
  "yoy_change": -5.2,
  "scope_breakdown": {
    "scope1": 125400.5,
    "scope2": 890200.0,
    "scope3": 3450000.0
  }
}
```

---

## AI Enhancement

All AI endpoints are at `/api/v1/ai`.

### Parse Unstructured Text

```
POST /ai/parse-text
Authorization: Bearer <token>
```

Extract structured emission data from unstructured text (invoices, utility bills, etc.). Rate-limited.

**Request Body** (`ParseTextRequest`):

```json
{
  "text": "Our electricity bill for Q4 2024 shows 500,000 kWh consumed...",
  "context": "utility_bill"
}
```

**Response** `200` (`ParseTextResponse`):

```json
{
  "extracted_data": {
    "electricity_kwh": 500000,
    "period": "Q4 2024"
  },
  "confidence": 0.92,
  "method": "rule_based"
}
```

---

### Predict Missing Emissions

```
POST /ai/predict
Authorization: Bearer <token>
```

Predict missing emission categories using industry-based statistical models. Rate-limited.

**Request Body** (`PredictionRequest`):

```json
{
  "industry": "manufacturing",
  "revenue_usd": 50000000,
  "employee_count": 500,
  "known_emissions": {
    "scope1": 125400.5,
    "scope2": 890200.0
  }
}
```

**Response** `200` (`PredictionResponse`):

```json
{
  "predictions": {
    "scope3": 3200000.0,
    "scope3_detail": { ... }
  },
  "confidence": 0.75,
  "method": "industry_average"
}
```

---

### Generate Audit Trail

```
POST /ai/audit-trail
Authorization: Bearer <token>
```

Generate a human-readable audit trail narrative for an emission report.

**Request Body** (`AuditTrailRequest`):

```json
{
  "report_id": 1
}
```

**Response** `200`:

```json
{
  "narrative": "Emission report #1 was generated on Jan 15, 2024...",
  "methodology": "Activity-based with EPA/eGRID factors...",
  "data_quality": "High confidence (0.85)..."
}
```

---

### Get Recommendations

```
GET /ai/recommendations/{report_id}
Authorization: Bearer <token>
```

Generate carbon reduction recommendations based on a specific emission report.

**Response** `200` (`RecommendationSummary`):

```json
{
  "report_id": 1,
  "total_reduction_potential_pct": 25.5,
  "recommendations": [
    {
      "strategy": "Switch to renewable energy",
      "scope": "scope2",
      "reduction_pct": 15.0,
      "cost_category": "medium",
      "timeframe": "1-3 years",
      "description": "..."
    }
  ]
}
```

---

## Questionnaires

All endpoints are at `/api/v1/questionnaires`.

### Upload Document

```
POST /questionnaires/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

Upload a questionnaire document (PDF, DOCX, XLSX, CSV — max 10 MB).

**Request:** `file` (multipart upload)

**Response** `201` (`QuestionnaireOut`):

```json
{
  "id": 1,
  "company_id": 1,
  "title": "cdp_questionnaire.pdf",
  "file_type": "pdf",
  "status": "uploaded",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### List Questionnaires

```
GET /questionnaires/?limit=50&offset=0
Authorization: Bearer <token>
```

**Response** `200` (`PaginatedResponse[QuestionnaireOut]`)

---

### List Templates

```
GET /questionnaires/templates/
Authorization: Bearer <token>
```

Returns the 5 pre-built questionnaire templates (CDP, EcoVadis, TCFD, GHG Protocol, CSRD/ESRS).

---

### Get Template

```
GET /questionnaires/templates/{template_id}
Authorization: Bearer <token>
```

Returns template details with all questions.

---

### Apply Template

```
POST /questionnaires/templates/{template_id}/apply
Authorization: Bearer <token>
```

Creates a new questionnaire from a template with AI-generated draft answers.

**Response** `200` (`QuestionnaireDetail`)

---

### Get Questionnaire Detail

```
GET /questionnaires/{questionnaire_id}
Authorization: Bearer <token>
```

Returns the questionnaire with all extracted questions.

**Response** `200` (`QuestionnaireDetail`):

```json
{
  "id": 1,
  "title": "cdp_questionnaire.pdf",
  "status": "extracted",
  "questions": [
    {
      "id": 1,
      "text": "What governance body oversees climate-related issues?",
      "ai_draft": "The board of directors...",
      "human_answer": null,
      "status": "draft"
    }
  ]
}
```

---

### Trigger AI Extraction

```
POST /questionnaires/{questionnaire_id}/extract
Authorization: Bearer <token>
```

Requires credits (`questionnaire_extract` — 8 credits). Triggers AI extraction of questions + draft answer generation.

**Response** `200` (`QuestionnaireDetail`)

---

### Update Question Answer

```
PATCH /questionnaires/{questionnaire_id}/questions/{question_id}
Authorization: Bearer <token>
```

**Request Body** (`QuestionUpdate`):

```json
{
  "human_answer": "Our board of directors meets quarterly...",
  "status": "reviewed"
}
```

**Response** `200` (`QuestionOut`)

---

### Update Questionnaire

```
PATCH /questionnaires/{questionnaire_id}
Authorization: Bearer <token>
```

**Request Body** (`QuestionnaireUpdate`):

```json
{
  "title": "CDP Climate Change 2024",
  "status": "completed"
}
```

---

### Delete Questionnaire

```
DELETE /questionnaires/{questionnaire_id}
Authorization: Bearer <token>
```

**Response** `204 No Content`

---

### Export Questionnaire as PDF

```
GET /questionnaires/{questionnaire_id}/export/pdf
Authorization: Bearer <token>
```

Requires credits (`pdf_export` — 5 credits).

**Response:** `StreamingResponse` (`application/pdf`)

---

## What-If Scenarios

All endpoints are at `/api/v1/scenarios`.

### Create Scenario

```
POST /scenarios/
Authorization: Bearer <token>
```

**Request Body** (`ScenarioCreate`):

```json
{
  "name": "Renewable Energy Switch",
  "description": "What if we switch 50% of electricity to renewables?",
  "base_report_id": 1,
  "parameters": {
    "electricity_renewable_pct": 50,
    "fleet_ev_pct": 25
  }
}
```

**Response** `201` (`ScenarioOut`)

---

### List Scenarios

```
GET /scenarios/?limit=50&offset=0
Authorization: Bearer <token>
```

**Response** `200` (`PaginatedResponse[ScenarioOut]`)

---

### Get / Update / Delete Scenario

```
GET    /scenarios/{scenario_id}
PATCH  /scenarios/{scenario_id}      — Update name/description (ScenarioUpdate)
DELETE /scenarios/{scenario_id}      — Soft-delete → 204
```

---

### Compute Scenario

```
POST /scenarios/{scenario_id}/compute
Authorization: Bearer <token>
```

Requires credits (`scenario_compute` — 3 credits). Runs the what-if computation with projected emissions.

**Response** `200` (`ScenarioOut`):

```json
{
  "id": 1,
  "name": "Renewable Energy Switch",
  "base_report_id": 1,
  "parameters": { ... },
  "results": {
    "projected_scope1": 125400.5,
    "projected_scope2": 445100.0,
    "projected_scope3": 3450000.0,
    "projected_total": 4020500.5,
    "reduction_pct": 9.97
  },
  "computed_at": "2024-01-15T11:00:00Z"
}
```

---

## Supply Chain

All endpoints are at `/api/v1/supply-chain`.

### Add Supplier Link

```
POST /supply-chain/links
Authorization: Bearer <token>
```

**Request Body** (`SupplyChainLinkCreate`):

```json
{
  "supplier_company_id": 5,
  "spend_usd": 2000000,
  "category": "raw_materials",
  "notes": "Primary steel supplier"
}
```

**Response** `201` (`SupplyChainLinkOut`)

---

### List Suppliers

```
GET /supply-chain/suppliers?limit=50&offset=0
Authorization: Bearer <token>
```

Returns suppliers with their emission data.

**Response** `200`:

```json
{
  "items": [...],
  "total": 8,
  "limit": 20,
  "offset": 0
}
```

---

### List Buyers

```
GET /supply-chain/buyers?limit=50&offset=0
Authorization: Bearer <token>
```

Returns companies this company supplies to.

---

### Calculate Scope 3 from Suppliers

```
GET /supply-chain/scope3-from-suppliers
Authorization: Bearer <token>
```

Aggregates Scope 3 Category 1 emissions from verified suppliers.

**Response** `200`:

```json
{
  "total_scope3_cat1": 1250000.0,
  "supplier_count": 5,
  "verified_count": 3,
  "details": [...]
}
```

---

### Get / Update / Delete Supply Chain Link

```
GET    /supply-chain/links/{link_id}
PATCH  /supply-chain/links/{link_id}     — Admin: update verification status
DELETE /supply-chain/links/{link_id}     — Soft-delete → 204
```

---

## Compliance Reporting

### Generate Compliance Report

```
POST /compliance/report
Authorization: Bearer <token>
```

Requires credits (`estimate` operation). Generates a compliance report for the specified framework.

**Request Body** (`ComplianceReportRequest`):

```json
{
  "report_id": 1,
  "framework": "ghg_protocol"
}
```

Supported frameworks: `ghg_protocol`, `cdp`, `tcfd`, `sbti`

**Response** `200`:

<details>
<summary>GHG Protocol response example</summary>

```json
{
  "framework": "ghg_protocol",
  "report": {
    "organizational_boundary": "Operational control",
    "reporting_period": "2024",
    "scope1": { ... },
    "scope2": { ... },
    "scope3": { ... },
    "total_emissions": 4465600.5,
    "base_year": null,
    "methodology": "Activity-based (GHG Protocol Corporate Standard)"
  }
}
```

</details>

<details>
<summary>SBTi response example</summary>

```json
{
  "framework": "sbti",
  "report": {
    "target_type": "1.5°C aligned",
    "annual_reduction_rate": 4.2,
    "pathway": [
      { "year": 2024, "projected": 1015600.5 },
      { "year": 2025, "projected": 973945.3 }
    ],
    "scope_coverage": "Scope 1 + Scope 2"
  }
}
```

</details>

---

## PCAF Financed Emissions

Endpoints at `/api/v1/pcaf`. Write operations (create portfolio, add/delete asset) require **Pro** or **Enterprise** plan.

### Create Portfolio

```
POST /pcaf/portfolios
Authorization: Bearer <token>
```

**Request Body** (`FinancedPortfolioCreate`):

```json
{ "name": "2024 Lending Portfolio", "year": 2024 }
```

**Response** `201` (`FinancedPortfolioOut`)

### List Portfolios

```
GET /pcaf/portfolios?skip=0&limit=50
Authorization: Bearer <token>
```

**Response** `200`: `{ "items": [...], "total": 2 }`

### Portfolio Summary

```
GET /pcaf/portfolios/{portfolio_id}/summary
Authorization: Bearer <token>
```

**Response** `200` (`PortfolioSummary`):

```json
{
  "asset_count": 5,
  "total_financed_emissions_tco2e": 12500.0,
  "total_outstanding": 50000000.0,
  "weighted_data_quality": 2.4,
  "by_asset_class": {
    "business_loans": { "count": 3, "financed_emissions_tco2e": 8000.0 }
  }
}
```

### Add Asset

```
POST /pcaf/portfolios/{portfolio_id}/assets
Authorization: Bearer <token>
```

**Request Body** (`FinancedAssetCreate`):

```json
{
  "asset_name": "Company A Loan",
  "asset_class": "business_loans",
  "outstanding_amount": 1000000,
  "total_equity_debt": 10000000,
  "investee_emissions_tco2e": 5000,
  "data_quality_score": 2
}
```

**Response** `201` — includes auto-calculated `attribution_factor` and `financed_emissions_tco2e`.

### List Assets

```
GET /pcaf/portfolios/{portfolio_id}/assets?skip=0&limit=100
Authorization: Bearer <token>
```

### Delete Asset

```
DELETE /pcaf/portfolios/{portfolio_id}/assets/{asset_id}
Authorization: Bearer <token>
```

**Response** `204`

---

## Data Reviews

Endpoints at `/api/v1/reviews`. State machine: `draft → submitted → approved/rejected`. Approve/reject require admin role.

### Create Review

```
POST /reviews
Authorization: Bearer <token>
```

**Request Body**: `{ "report_id": "<uuid>" }`

**Response** `201` (`DataReviewOut`) — status: `draft`

### List Reviews

```
GET /reviews?status_filter=submitted&skip=0&limit=50
Authorization: Bearer <token>
```

### Get Review

```
GET /reviews/{review_id}
Authorization: Bearer <token>
```

### Review Action

```
POST /reviews/{review_id}/action
Authorization: Bearer <token>
```

**Request Body** (`DataReviewAction`):

```json
{ "action": "approve", "notes": "Verified and approved" }
```

Actions: `submit` (any user), `approve` / `reject` (admin only).

---

## MFA (TOTP)

Endpoints at `/api/v1/auth/mfa`. Implements RFC 4226/6238 TOTP.

### Status

```
GET /auth/mfa/status
Authorization: Bearer <token>
```

**Response** `200`: `{ "mfa_enabled": false }`

### Setup

```
POST /auth/mfa/setup
Authorization: Bearer <token>
```

**Response** `200` (`MFASetupOut`):

```json
{
  "secret": "JBSWY3DPEHPK3PXP...",
  "provisioning_uri": "otpauth://totp/CarbonScope:user@example.com?...",
  "backup_codes": ["a1b2c3d4", "e5f6g7h8", ...]
}
```

### Verify (Activate)

```
POST /auth/mfa/verify
Authorization: Bearer <token>
```

**Request Body**: `{ "totp_code": "123456" }`

**Response** `200`: `{ "mfa_enabled": true }`

### Validate (Login 2FA)

```
POST /auth/mfa/validate
Authorization: Bearer <token>
```

**Request Body**: `{ "totp_code": "123456" }`

**Response** `200`: `{ "valid": true }`

### Disable

```
DELETE /auth/mfa/disable
Authorization: Bearer <token>
```

**Request Body**: `{ "totp_code": "123456" }`

**Response** `204`

---

## Industry Benchmarks

Endpoints at `/api/v1/benchmarks`.

### List Benchmarks

```
GET /benchmarks?industry=manufacturing&region=US&year=2024
Authorization: Bearer <token>
```

**Response** `200`: `{ "items": [...], "total": 5 }`

### Compare to Industry

```
GET /benchmarks/compare?report_id=<uuid>
Authorization: Bearer <token>
```

**Response** `200` (`BenchmarkComparison`):

```json
{
  "company_emissions": {
    "scope1": 1200,
    "scope2": 800,
    "scope3": 3000,
    "total": 5000
  },
  "industry_average": { "avg_scope1_tco2e": 1000, "avg_total_tco2e": 4100 },
  "vs_average": { "scope1": 20.0, "scope2": null, "total": 21.95 },
  "percentile_rank": "bottom_25"
}
```

Ranking labels: `top_10` (≤ -30%), `top_25` (≤ -10%), `median` (± 10%), `bottom_25` (≤ +30%), `bottom_10` (> +30%).

---

## Billing & Subscriptions

All endpoints are at `/api/v1/billing`.

### Get Subscription

```
GET /billing/subscription
Authorization: Bearer <token>
```

**Response** `200` (`SubscriptionOut`):

```json
{
  "id": 1,
  "company_id": 1,
  "plan": "pro",
  "status": "active",
  "monthly_credits": 1000,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### Change Plan

```
POST /billing/subscription
Authorization: Bearer <token>  (Admin only)
```

**Request Body** (`SubscriptionCreate`):

```json
{
  "plan": "enterprise"
}
```

Plans: `free`, `pro`, `enterprise`

---

### Get Credit Balance

```
GET /billing/credits
Authorization: Bearer <token>
```

**Response** `200` (`CreditBalanceOut`):

```json
{
  "balance": 850,
  "plan": "pro",
  "monthly_grant": 1000
}
```

---

### Get Credit Ledger

```
GET /billing/credits/ledger?limit=50&offset=0
Authorization: Bearer <token>
```

Returns credit transaction history.

**Response** `200` (`PaginatedResponse[CreditLedgerOut]`):

```json
{
  "items": [
    {
      "id": 1,
      "amount": -10,
      "operation": "estimate",
      "balance_after": 850,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 25,
  "limit": 20,
  "offset": 0
}
```

---

### Grant Credits (Admin)

```
POST /billing/credits/grant?amount=500
Authorization: Bearer <token>  (Admin only)
```

**Response** `200` (`CreditBalanceOut`)

---

### List Plans

```
GET /billing/plans
```

No authentication required. Returns available plans with feature limits.

---

## Alerts

All endpoints are at `/api/v1/alerts`.

### List Alerts

```
GET /alerts?unread_only=true&limit=50&offset=0
Authorization: Bearer <token>
```

**Response** `200` (`PaginatedResponse[AlertOut]`):

```json
{
  "items": [
    {
      "id": 1,
      "company_id": 1,
      "type": "emission_increase",
      "message": "Scope 2 emissions increased 15% compared to previous report",
      "severity": "warning",
      "acknowledged": false,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 3,
  "limit": 20,
  "offset": 0
}
```

---

### Acknowledge Alert

```
POST /alerts/{alert_id}/acknowledge
Authorization: Bearer <token>
```

**Response** `200` (`AlertOut`)

---

### Trigger Alert Check

```
POST /alerts/check
Authorization: Bearer <token>
```

Manually triggers alert evaluation for the current company. Admin role required.

**Response** `200` (list of newly created alerts)

---

## Data Marketplace

All endpoints are at `/api/v1/marketplace`. Requires Pro or Enterprise plan.

### Create Listing

```
POST /marketplace/listings
Authorization: Bearer <token>
```

**Request Body** (`DataListingCreate`):

```json
{
  "report_id": 1,
  "title": "Manufacturing Emissions 2024",
  "description": "Anonymized emission data for mid-size manufacturer",
  "price_credits": 50,
  "data_type": "emission_report"
}
```

**Response** `201` (`DataListingOut`)

---

### Browse Listings

```
GET /marketplace/listings?industry=manufacturing&region=US&limit=50&offset=0
Authorization: Bearer <token>
```

Filterable by industry, region, and data type.

**Response** `200` (`PaginatedResponse[DataListingOut]`)

---

### Get Listing Detail

```
GET /marketplace/listings/{listing_id}
Authorization: Bearer <token>
```

---

### Purchase Listing

```
POST /marketplace/listings/{listing_id}/purchase
Authorization: Bearer <token>
```

Deducts credits and grants access to the anonymized data.

**Response** `200` (`DataPurchaseOut`)

---

### My Listings

```
GET /marketplace/my-listings
Authorization: Bearer <token>
```

---

### My Sales

```
GET /marketplace/my-sales?limit=50&offset=0
Authorization: Bearer <token>
```

Returns purchases of your listings.

**Response** `200` (`PaginatedResponse[DataPurchaseOut]`)

---

### My Revenue

```
GET /marketplace/my-revenue
Authorization: Bearer <token>
```

Returns total revenue, sales count, and active listing count.

**Response** `200` (`SellerRevenue`):

```json
{
  "total_credits": 250,
  "total_sales": 5,
  "active_listings": 3
}
```

---

### Withdraw Listing

```
POST /marketplace/listings/{listing_id}/withdraw
Authorization: Bearer <token>
```

---

## Webhooks

All endpoints are at `/api/v1/webhooks`.

### Register Webhook

```
POST /webhooks/
Authorization: Bearer <token>  (Admin only)
```

**Request Body** (`WebhookCreate`):

```json
{
  "url": "https://example.com/webhook",
  "events": ["report.created", "data.uploaded"],
  "description": "Production webhook"
}
```

An HMAC-SHA256 secret is auto-generated and returned once.

**Response** `201` (`WebhookOut`):

```json
{
  "id": 1,
  "url": "https://example.com/webhook",
  "events": ["report.created", "data.uploaded"],
  "secret": "whsec_abc123...",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### List Webhooks

```
GET /webhooks/?limit=50&offset=0
Authorization: Bearer <token>
```

**Response** `200` (`PaginatedResponse[WebhookOutPublic]`) — secret is not included.

---

### Toggle Webhook

```
PATCH /webhooks/{webhook_id}
Authorization: Bearer <token>
```

**Request Body** (`WebhookToggle`):

```json
{
  "is_active": false
}
```

---

### Delete Webhook

```
DELETE /webhooks/{webhook_id}
Authorization: Bearer <token>  (Admin only)
```

**Response** `204 No Content`

---

### List Deliveries

```
GET /webhooks/{webhook_id}/deliveries?limit=50&offset=0
Authorization: Bearer <token>
```

**Response** `200` (`PaginatedResponse[WebhookDeliveryOut]`):

```json
{
  "items": [
    {
      "id": 1,
      "webhook_id": 1,
      "event": "report.created",
      "status_code": 200,
      "duration_ms": 245,
      "response_body": "OK",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

## Stripe Webhooks

Endpoint: `POST /api/v1/stripe/webhooks`

Receives payment events from Stripe. No authentication token required — requests are verified using the `Stripe-Signature` header and the `STRIPE_WEBHOOK_SECRET` environment variable.

### Supported Events

| Event Type                      | Action                                                 |
| :------------------------------ | :----------------------------------------------------- |
| `customer.subscription.updated` | Sync subscription status (active, past_due, cancelled) |
| `customer.subscription.deleted` | Mark subscription cancelled                            |
| `invoice.payment_failed`        | Create payment failure alert, notify account owner     |
| `checkout.session.completed`    | Link Stripe customer to company subscription           |

### Signature Verification

Stripe signs each webhook with HMAC-SHA256 over `{timestamp}.{payload}`. The endpoint rejects:

- Requests without a valid `Stripe-Signature` header
- Timestamps older than 5 minutes (replay protection)
- Invalid HMAC signatures

### Response Codes

| Code | Meaning                                |
| :--- | :------------------------------------- |
| 200  | Event processed successfully           |
| 400  | Signature verification failed          |
| 503  | `STRIPE_WEBHOOK_SECRET` not configured |

---

## Audit Logs

### List Audit Logs (Admin)

```
GET /audit-logs/?action=create&resource_type=emission_report&user_id=1&limit=50&offset=0
Authorization: Bearer <token>  (Admin only)
```

Filterable by action, resource type, and user ID.

**Response** `200` (`PaginatedResponse[AuditLogOut]`):

```json
{
  "items": [
    {
      "id": 1,
      "user_id": 1,
      "action": "create",
      "resource_type": "emission_report",
      "resource_id": "1",
      "detail": "Created emission report for FY2024",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

## Health & Metrics

### Health Check

```
GET /health
```

No authentication required. Returns minimal status.

**Response** `200`:

```json
{
  "status": "healthy"
}
```

### Health Detail (Admin)

```
GET /health/detail
```

Requires admin authentication.

**Response** `200`:

```json
{
  "status": "healthy",
  "version": "0.24.1",
  "database": "connected",
  "email": "configured",
  "bittensor": "local/test",
  "db_pool": "sqlite/no_pool"
}
```

---

### Metrics

```
GET /metrics
```

Requires admin authentication.

**Response** `200`:

```json
{
  "uptime_seconds": 86400,
  "total_requests": 15234,
  "total_errors": 3,
  "status_codes": {
    "200": 15190,
    "401": 28,
    "500": 3
  },
  "version": "0.24.1"
}
```

---

### Server-Sent Events (SSE)

```
GET /api/v1/events/subscribe
```

Requires authentication (Bearer token or cookie). Opens an SSE stream for real-time push events scoped to the authenticated user's company.

**Event types:**

| Event               | Data                                              |
| :------------------- | :------------------------------------------------ |
| `alert.created`      | `{"alert_id": "...", "metric": "...", ...}`       |
| `alert.acknowledged` | `{"alert_id": "...", "acknowledged_by": "..."}`   |

**Example:**

```
event: alert.created
data: {"alert_id": "abc123", "metric": "scope_1", "value": 120.5}
```

Connection auto-closes after server-defined timeout. Client should reconnect on close.

---

## Common Patterns

### Pagination

All list endpoints support offset-based pagination:

| Parameter | Default | Description                 |
| :-------- | :-----: | :-------------------------- |
| `limit`   |   50    | Items per page (max varies) |
| `offset`  |    0    | Number of items to skip     |

Response format:

```json
{
  "items": [...],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

### Authentication

Two methods are supported:

1. **Bearer Token** — `Authorization: Bearer <access_token>`
2. **Cookie** — `access_token` httpOnly cookie (set automatically on login)

When using cookie-based auth on state-changing methods (`POST`, `PUT`, `PATCH`, `DELETE`), include the `X-CSRF-Token` header matching the `csrf_token` cookie value.

### Soft Deletes

`DELETE` endpoints mark records with a `deleted_at` timestamp rather than removing them. Soft-deleted records are excluded from listing queries.

### Credit Operations

Operations that consume credits:

| Operation                |  Credits |
| :----------------------- | -------: |
| Emission Estimate        |       10 |
| Questionnaire Extraction |        8 |
| PDF Export               |        5 |
| Scenario Compute         |        3 |
| Marketplace Purchase     | Variable |

If insufficient credits, the API returns `402 Payment Required`.

---

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

### Status Codes

| Code | Description                                                      |
| :--: | :--------------------------------------------------------------- |
| 400  | Bad request (validation error, invalid input)                    |
| 401  | Unauthorized (missing or invalid token)                          |
| 402  | Payment required (insufficient credits)                          |
| 403  | Forbidden (insufficient role or plan)                            |
| 404  | Not found (resource doesn't exist or belongs to another company) |
| 409  | Conflict (duplicate resource)                                    |
| 422  | Validation error (Pydantic schema validation failure)            |
| 429  | Too many requests (rate limit exceeded)                          |
| 500  | Internal server error (includes `X-Request-ID` header)           |

### Rate Limits

| Scope                       | Limit     |
| :-------------------------- | :-------- |
| Auth                        | 10/minute |
| Default                     | 60/minute |
| `/estimate`                 | 5/minute  |
| `/scenarios/*/compute`      | 5/minute  |
| `/questionnaires/upload`    | 5/minute  |
| `/questionnaires/*/extract` | 5/minute  |
| `/marketplace/*/purchase`   | 10/minute |
| `/billing/subscription`     | 5/minute  |
| `/stripe/webhooks`          | 60/minute |

Rate limit headers are included in responses:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

---

## Versioning Strategy

The CarbonScope API follows **URL path versioning** with the prefix `/api/v1/`.

### Principles

1. **Backwards compatibility**: Existing fields and endpoints in a version are never removed or renamed. New fields may be added to response bodies (clients should ignore unknown fields).
2. **Deprecation window**: When a breaking change is planned, the old version continues to work for at least **6 months** with a `Sunset` header indicating the removal date.
3. **Version lifecycle**: `v1` (current, stable) → `v2` (future, TBD). New major versions get a new URL prefix (`/api/v2/`).
4. **Additive changes** (non-breaking): New optional query parameters, new response fields, new endpoints — these ship within the current version without incrementing.
5. **Breaking changes**: Removing/renaming fields, changing response structure, altering authentication flow, removing endpoints — these require a new major version.

### Headers

| Header          | Description                                          |
| :-------------- | :--------------------------------------------------- |
| `X-API-Version` | Current API version in the response (`1.0`)          |
| `Sunset`        | (If deprecated) ISO-8601 date of planned removal     |
| `Deprecation`   | (If deprecated) ISO-8601 date feature was deprecated |
