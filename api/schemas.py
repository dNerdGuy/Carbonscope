"""Pydantic schemas for request/response validation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, EmailStr, Field, field_validator

T = TypeVar("T")

_MAX_JSON_DEPTH = 5


def _check_json_depth(obj: Any, depth: int = 0) -> None:
    """Reject deeply nested JSON to prevent resource exhaustion."""
    if depth > _MAX_JSON_DEPTH:
        raise ValueError(f"JSON nesting exceeds maximum depth of {_MAX_JSON_DEPTH}")
    if isinstance(obj, dict):
        for v in obj.values():
            _check_json_depth(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _check_json_depth(v, depth + 1)


def _check_password_strength(v: str) -> str:
    """Shared password strength validator."""
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"[0-9]", v):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>\[\]\\~`_+\-=/;\']', v):
        raise ValueError("Password must contain at least one special character")
    return v


# ── Auth ────────────────────────────────────────────────────────────


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    company_name: str = Field(min_length=1, max_length=255)
    industry: str = Field(min_length=1, max_length=100)
    region: str = Field(default="US", max_length=10)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    company_id: str
    role: str

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


# ── Company ─────────────────────────────────────────────────────────


class CompanyOut(BaseModel):
    id: str
    name: str
    industry: str
    region: str
    employee_count: int | None = None
    revenue_usd: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    region: str | None = None
    employee_count: int | None = Field(default=None, ge=0)
    revenue_usd: float | None = Field(default=None, ge=0)


# ── Data upload ─────────────────────────────────────────────────────


class DataUploadCreate(BaseModel):
    year: int = Field(ge=2000, le=2030)
    provided_data: dict[str, Any]
    notes: str | None = None

    @field_validator("provided_data")
    @classmethod
    def validate_depth(cls, v: dict) -> dict:
        _check_json_depth(v)
        return v


class DataUploadUpdate(BaseModel):
    year: int | None = Field(default=None, ge=2000, le=2030)
    provided_data: dict[str, Any] | None = None
    notes: str | None = None


class DataUploadOut(BaseModel):
    id: str
    company_id: str
    year: int
    provided_data: dict[str, Any]
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Emission report ─────────────────────────────────────────────────


class EmissionReportOut(BaseModel):
    id: str
    company_id: str
    year: int
    scope1: float
    scope2: float
    scope3: float
    total: float
    breakdown: dict | None = None
    confidence: float
    sources: list | None = None
    assumptions: list | None = None
    methodology_version: str
    miner_scores: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportUpdate(BaseModel):
    year: int | None = Field(default=None, ge=2000, le=2030)
    notes: str | None = None


class EstimateRequest(BaseModel):
    """Trigger an emission estimation for a specific data upload."""
    data_upload_id: str


# ── Paginated response ──────────────────────────────────────────────


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# ── Dashboard ───────────────────────────────────────────────────────


class DashboardSummary(BaseModel):
    company: CompanyOut
    latest_report: EmissionReportOut | None = None
    reports_count: int = 0
    data_uploads_count: int = 0
    year_over_year: list[dict[str, Any]] = []


# ── AI / Parsing ────────────────────────────────────────────────────


class ParseTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class ParseTextResponse(BaseModel):
    extracted_data: dict[str, Any]


class AuditTrailRequest(BaseModel):
    report_id: str


# ── Predictions ─────────────────────────────────────────────────────


class PredictionRequest(BaseModel):
    known_data: dict[str, Any]
    industry: str | None = None
    region: str | None = None


class PredictionResponse(BaseModel):
    predictions: dict[str, float]
    method: str
    uncertainty: dict[str, float]
    filled_categories: list[str]
    confidence_adjustment: float


# ── Recommendations ─────────────────────────────────────────────────


class RecommendationOut(BaseModel):
    id: str
    scope: int
    category: str
    title: str
    description: str
    co2_reduction_tco2e: float
    reduction_percentage: float
    annual_cost_usd: dict[str, float]
    cost_tier: str
    payback_years: int
    difficulty: str
    co_benefits: list[str]
    priority_score: float


class RecommendationSummary(BaseModel):
    recommendations: list[RecommendationOut]
    summary: dict[str, Any]


# ── Supply chain ────────────────────────────────────────────────────


class SupplyChainLinkCreate(BaseModel):
    supplier_company_id: str
    spend_usd: float | None = Field(default=None, ge=0)
    category: str = "purchased_goods"
    notes: str | None = None


class SupplyChainLinkOut(BaseModel):
    id: str
    buyer_company_id: str
    supplier_company_id: str
    spend_usd: float | None
    category: str
    status: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SupplyChainLinkUpdate(BaseModel):
    status: str = Field(pattern="^(pending|verified|rejected)$")


# ── Compliance ──────────────────────────────────────────────────────


class ComplianceReportRequest(BaseModel):
    report_id: str
    framework: str = Field(pattern="^(ghg_protocol|cdp|tcfd|sbti|csrd|issb|secr)$")


# ── Webhooks ────────────────────────────────────────────────────────


class WebhookCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    event_types: list[str] = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError("Webhook URL must start with https:// or http://")
        return v


class WebhookToggle(BaseModel):
    active: bool


class WebhookOut(BaseModel):
    """Full webhook details — includes secret (returned only on creation)."""
    id: str
    company_id: str
    url: str
    event_types: list[str]
    secret: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookOutPublic(BaseModel):
    """Webhook details without secret — used for list and update responses."""
    id: str
    company_id: str
    url: str
    event_types: list[str]
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryOut(BaseModel):
    id: str
    webhook_id: str
    event_type: str
    payload: dict[str, Any]
    status_code: int | None = None
    success: bool
    error: str | None = None
    duration_ms: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Audit Log ───────────────────────────────────────────────────────


class AuditLogOut(BaseModel):
    id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str | None = None
    detail: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Questionnaire ───────────────────────────────────────────────────


class QuestionnaireOut(BaseModel):
    id: str
    company_id: str
    title: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuestionOut(BaseModel):
    id: str
    questionnaire_id: str
    question_number: int
    question_text: str
    category: str | None = None
    ai_draft_answer: str | None = None
    human_answer: str | None = None
    status: str
    confidence: float
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionUpdate(BaseModel):
    human_answer: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|reviewed|approved)$")


class QuestionnaireUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    status: str | None = Field(default=None, pattern="^(uploaded|extracting|extracted|reviewed|exported)$")


class QuestionnaireDetail(BaseModel):
    questionnaire: QuestionnaireOut
    questions: list[QuestionOut]


# ── What-If Scenarios ───────────────────────────────────────────────


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    base_report_id: str | None = None
    parameters: dict[str, Any]

    @field_validator("parameters")
    @classmethod
    def validate_depth(cls, v: dict) -> dict:
        _check_json_depth(v)
        return v


class ScenarioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class ScenarioOut(BaseModel):
    id: str
    company_id: str
    name: str
    description: str | None = None
    base_report_id: str | None = None
    parameters: dict[str, Any]
    results: dict[str, Any] | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Subscriptions & Billing ─────────────────────────────────────────


class SubscriptionOut(BaseModel):
    id: str
    company_id: str
    plan: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionCreate(BaseModel):
    plan: str = Field(pattern="^(free|pro|enterprise)$")


class CreditBalanceOut(BaseModel):
    company_id: str
    balance: int
    plan: str


class CreditLedgerOut(BaseModel):
    id: str
    amount: int
    reason: str
    balance_after: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Alerts ──────────────────────────────────────────────────────────


class AlertOut(BaseModel):
    id: str
    company_id: str
    alert_type: str
    severity: str
    title: str
    message: str
    is_read: bool
    acknowledged_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Data Marketplace ────────────────────────────────────────────────


class DataListingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    data_type: str = Field(pattern="^(emission_report|benchmark|supply_chain)$")
    report_id: str  # source report to anonymize
    price_credits: int = Field(ge=0, default=0)


class DataListingOut(BaseModel):
    id: str
    seller_company_id: str
    title: str
    description: str | None = None
    data_type: str
    industry: str
    region: str
    year: int
    price_credits: int
    anonymized_data: dict[str, Any]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DataPurchaseOut(BaseModel):
    id: str
    listing_id: str
    buyer_company_id: str
    price_credits: int
    listing: DataListingOut
    created_at: datetime

    model_config = {"from_attributes": True}


# ── PCAF Financed Emissions ─────────────────────────────────────────


class FinancedAssetCreate(BaseModel):
    asset_name: str = Field(min_length=1, max_length=255)
    asset_class: str = Field(pattern="^(listed_equity|corporate_bonds|business_loans|project_finance|commercial_real_estate|mortgages|sovereign_debt)$")
    outstanding_amount: float = Field(ge=0)
    total_equity_debt: float = Field(gt=0)
    investee_emissions_tco2e: float = Field(ge=0)
    data_quality_score: int = Field(ge=1, le=5, default=3)
    industry: str | None = None
    region: str | None = None
    notes: str | None = None


class FinancedAssetOut(BaseModel):
    id: str
    portfolio_id: str
    asset_name: str
    asset_class: str
    outstanding_amount: float
    total_equity_debt: float
    investee_emissions_tco2e: float
    attribution_factor: float | None = None
    financed_emissions_tco2e: float | None = None
    data_quality_score: int
    industry: str | None = None
    region: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FinancedPortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    year: int = Field(ge=2000, le=2030)


class FinancedPortfolioOut(BaseModel):
    id: str
    company_id: str
    name: str
    year: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    portfolio: FinancedPortfolioOut
    total_financed_emissions_tco2e: float
    total_outstanding: float
    weighted_data_quality: float
    asset_count: int
    by_asset_class: dict[str, Any]


# ── Data Review & Approval ──────────────────────────────────────────


class DataReviewCreate(BaseModel):
    report_id: str


class DataReviewAction(BaseModel):
    action: str = Field(pattern="^(submit|approve|reject)$")
    notes: str | None = None


class DataReviewOut(BaseModel):
    id: str
    report_id: str
    company_id: str
    status: str
    submitted_by: str | None = None
    reviewed_by: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── MFA (TOTP) ──────────────────────────────────────────────────────


class MFASetupOut(BaseModel):
    secret: str
    provisioning_uri: str
    backup_codes: list[str]


class MFAVerifyRequest(BaseModel):
    totp_code: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")


class MFAStatusOut(BaseModel):
    mfa_enabled: bool


# ── Industry Benchmarks ─────────────────────────────────────────────


class BenchmarkOut(BaseModel):
    industry: str
    region: str
    year: int
    avg_scope1_tco2e: float
    avg_scope2_tco2e: float
    avg_scope3_tco2e: float
    avg_total_tco2e: float
    avg_intensity_per_employee: float | None = None
    avg_intensity_per_revenue: float | None = None
    sample_size: int
    source: str

    model_config = {"from_attributes": True}


class BenchmarkComparison(BaseModel):
    company_emissions: dict[str, float]
    industry_average: BenchmarkOut | None = None
    percentile_rank: dict[str, str | None]
    vs_average: dict[str, float | None]
