"""Pydantic schemas for request/response validation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, EmailStr, Field, field_validator

T = TypeVar("T")


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
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v


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
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v


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
    employee_count: int | None = None
    revenue_usd: float | None = None


# ── Data upload ─────────────────────────────────────────────────────


class DataUploadCreate(BaseModel):
    year: int = Field(ge=2000, le=2030)
    provided_data: dict[str, Any]
    notes: str | None = None


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
    spend_usd: float | None = None
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
    framework: str = Field(pattern="^(ghg_protocol|cdp|tcfd|sbti)$")


# ── Webhooks ────────────────────────────────────────────────────────


class WebhookCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    event_types: list[str] = Field(min_length=1)


class WebhookOut(BaseModel):
    id: str
    company_id: str
    url: str
    event_types: list[str]
    secret: str
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
