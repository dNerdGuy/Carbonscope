# Database Schema Reference

> Auto-maintained reference for the CarbonScope PostgreSQL schema.
> **25 models**, all using `String(32)` hex UUID primary keys and `DateTime(timezone=True)` timestamps.

## Conventions

- **Soft-delete**: Most tables have a nullable `deleted_at` column; queries should filter `deleted_at IS NULL`.
- **Audit trail**: `created_at` / `updated_at` columns on every table; `AuditLog` for user actions.
- **Foreign keys**: All company FKs use `ON DELETE CASCADE`.

---

## Core Domain

### Company (`companies`)

| Column                               | Type         | Notes          |
| ------------------------------------ | ------------ | -------------- |
| id                                   | String(32)   | PK             |
| name                                 | String(255)  | NOT NULL       |
| industry                             | String(100)  | NOT NULL       |
| region                               | String(10)   | default `"US"` |
| employee_count                       | Integer      | nullable       |
| revenue_usd                          | Float        | nullable       |
| created_at / updated_at / deleted_at | DateTime(tz) |                |

### User (`users`)

| Column                | Type                    | Notes                   |
| --------------------- | ----------------------- | ----------------------- |
| id                    | String(32)              | PK                      |
| email                 | String(255)             | UNIQUE, indexed         |
| hashed_password       | String(255)             |                         |
| full_name             | String(255)             |                         |
| company_id            | String(32)              | FK → companies, indexed |
| role                  | Enum(`admin`, `member`) | default `member`        |
| is_active             | Boolean                 | default True            |
| failed_login_attempts | Integer                 | default 0               |
| locked_until          | DateTime(tz)            | nullable                |
| deleted_at            | DateTime(tz)            | soft-delete             |

### DataUpload (`data_uploads`)

| Column        | Type       | Notes                   |
| ------------- | ---------- | ----------------------- |
| id            | String(32) | PK                      |
| company_id    | String(32) | FK → companies, indexed |
| year          | Integer    |                         |
| provided_data | JSON       | default `{}`            |
| notes         | Text       | nullable                |

Index: `(company_id, year)`

### EmissionReport (`emission_reports`)

| Column                           | Type       | Notes                          |
| -------------------------------- | ---------- | ------------------------------ |
| id                               | String(32) | PK                             |
| company_id                       | String(32) | FK → companies, indexed        |
| data_upload_id                   | String(32) | FK → data_uploads (SET NULL)   |
| year                             | Integer    |                                |
| scope1 / scope2 / scope3 / total | Float      | default 0.0, CHECK ≥ 0         |
| breakdown                        | JSON       | nullable                       |
| confidence                       | Float      | CHECK 0–1                      |
| sources / assumptions            | JSON       | nullable                       |
| methodology_version              | String(50) | default `"ghg_protocol_v2025"` |
| miner_scores                     | JSON       | nullable                       |

Index: `(company_id, year)`

---

## Supply Chain & Scenarios

### SupplyChainLink (`supply_chain_links`)

| Column              | Type                                    | Notes                       |
| ------------------- | --------------------------------------- | --------------------------- |
| id                  | String(32)                              | PK                          |
| buyer_company_id    | String(32)                              | FK → companies              |
| supplier_company_id | String(32)                              | FK → companies              |
| spend_usd           | Float                                   | nullable                    |
| category            | String(100)                             | default `"purchased_goods"` |
| status              | Enum(`pending`, `verified`, `rejected`) |                             |

Unique: `(buyer_company_id, supplier_company_id)`

### Scenario (`scenarios`)

| Column         | Type                                  | Notes                           |
| -------------- | ------------------------------------- | ------------------------------- |
| id             | String(32)                            | PK                              |
| company_id     | String(32)                            | FK → companies                  |
| name           | String(255)                           |                                 |
| base_report_id | String(32)                            | FK → emission_reports, nullable |
| parameters     | JSON                                  | default `{}`                    |
| results        | JSON                                  | nullable                        |
| status         | Enum(`draft`, `computed`, `archived`) |                                 |

---

## Questionnaires

### Questionnaire (`questionnaires`)

| Column            | Type                                                                | Notes          |
| ----------------- | ------------------------------------------------------------------- | -------------- |
| id                | String(32)                                                          | PK             |
| company_id        | String(32)                                                          | FK → companies |
| title             | String(500)                                                         |                |
| original_filename | String(500)                                                         |                |
| file_type         | String(20)                                                          |                |
| file_size         | Integer                                                             |                |
| status            | Enum(`uploaded`, `extracting`, `extracted`, `reviewed`, `exported`) |                |
| extracted_text    | Text                                                                | nullable       |

### QuestionnaireQuestion (`questionnaire_questions`)

| Column           | Type                                  | Notes                         |
| ---------------- | ------------------------------------- | ----------------------------- |
| id               | String(32)                            | PK                            |
| questionnaire_id | String(32)                            | FK → questionnaires (CASCADE) |
| question_number  | Integer                               |                               |
| question_text    | Text                                  |                               |
| ai_draft_answer  | Text                                  | nullable                      |
| human_answer     | Text                                  | nullable                      |
| status           | Enum(`draft`, `reviewed`, `approved`) |                               |
| confidence       | Float                                 | default 0.0                   |

---

## PCAF / Financed Emissions

### FinancedPortfolio (`financed_portfolios`)

| Column     | Type        | Notes          |
| ---------- | ----------- | -------------- |
| id         | String(32)  | PK             |
| company_id | String(32)  | FK → companies |
| name       | String(255) |                |
| year       | Integer     |                |

Index: `(company_id, year)`

### FinancedAsset (`financed_assets`)

| Column                   | Type                 | Notes                              |
| ------------------------ | -------------------- | ---------------------------------- |
| id                       | String(32)           | PK                                 |
| portfolio_id             | String(32)           | FK → financed_portfolios (CASCADE) |
| asset_name               | String(255)          |                                    |
| asset_class              | Enum(PCAFAssetClass) | 7 classes                          |
| outstanding_amount       | Float                | CHECK ≥ 0                          |
| total_equity_debt        | Float                | CHECK > 0                          |
| investee_emissions_tco2e | Float                | CHECK ≥ 0                          |
| attribution_factor       | Float                | auto-calculated                    |
| financed_emissions_tco2e | Float                | auto-calculated                    |
| data_quality_score       | Integer              | PCAF 1–5, CHECK 1–5                |

---

## Billing & Marketplace

### Subscription (`subscriptions`)

| Column                                      | Type                                    | Notes                  |
| ------------------------------------------- | --------------------------------------- | ---------------------- |
| id                                          | String(32)                              | PK                     |
| company_id                                  | String(32)                              | FK → companies, UNIQUE |
| plan                                        | Enum(`free`, `pro`, `enterprise`)       |                        |
| status                                      | Enum(`active`, `cancelled`, `past_due`) |                        |
| stripe_customer_id / stripe_subscription_id | String(255)                             | nullable               |

### CreditLedger (`credit_ledger`)

| Column        | Type               | Notes          |
| ------------- | ------------------ | -------------- |
| id            | String(32)         | PK             |
| company_id    | String(32)         | FK → companies |
| amount        | Integer            | +add / −deduct |
| reason        | Enum(CreditReason) | 13 values      |
| balance_after | Integer            | CHECK ≥ 0      |

### DataListing (`data_listings`)

Marketplace listings for anonymized emission data. FK → companies via `seller_company_id`.

### DataPurchase (`data_purchases`)

Unique: `(listing_id, buyer_company_id)`.

---

## Auth & Security

### RefreshToken (`refresh_tokens`)

`user_id` FK → users, `token_hash` UNIQUE, `expires_at`.

### RevokedToken (`revoked_tokens`)

`jti` UNIQUE, `user_id` FK → users, `expires_at`.

### PasswordResetToken (`password_reset_tokens`)

`user_id` FK → users, `email`, `token_hash` UNIQUE, `expires_at`.

### MFASecret (`mfa_secrets`)

`user_id` FK → users (UNIQUE), `totp_secret`, `is_enabled`, `backup_codes` (JSON).

### Invitation (`invitations`)

`company_id` FK, `email`, `role`, `invited_by` FK → users, `token_hash` UNIQUE, `expires_at`.

---

## Monitoring

### Alert (`alerts`)

| Column          | Type                                                            | Notes          |
| --------------- | --------------------------------------------------------------- | -------------- |
| id              | String(32)                                                      | PK             |
| company_id      | String(32)                                                      | FK → companies |
| alert_type      | Enum(`emission_increase`, `confidence_drop`, `target_exceeded`) |                |
| severity        | Enum(`info`, `warning`, `critical`)                             |                |
| title / message | String / Text                                                   |                |
| is_read         | Boolean                                                         | default False  |

### AuditLog (`audit_logs`)

`user_id`, `company_id`, `action`, `resource_type`, `resource_id`, `detail`. Index: `(company_id, created_at)`.

### Webhook (`webhooks`) / WebhookDelivery (`webhook_deliveries`)

Company webhook registrations with delivery tracking, retry count, and success status.

### IndustryBenchmark (`industry_benchmarks`)

Unique: `(industry, region, year)`. Stores aggregated emission averages and intensity metrics.

### DataReview (`data_reviews`)

`report_id` FK, `status` Enum(`draft`, `submitted`, `in_review`, `approved`, `rejected`), `submitted_by`, `reviewed_by` FKs → users.

---

## Entity-Relationship Summary

```
Company ──┬── User
           ├── DataUpload ── EmissionReport ── DataReview
           ├── SupplyChainLink (buyer/supplier)
           ├── Scenario
           ├── Questionnaire ── QuestionnaireQuestion
           ├── FinancedPortfolio ── FinancedAsset
           ├── Subscription
           ├── CreditLedger
           ├── Alert
           ├── Webhook ── WebhookDelivery
           ├── DataListing ── DataPurchase
           ├── AuditLog
           └── Invitation

User ──┬── RefreshToken
       ├── RevokedToken
       ├── PasswordResetToken
       └── MFASecret
```
