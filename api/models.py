"""Database models for the CarbonScope platform."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    event,
    Enum,
)
from sqlalchemy.orm import relationship

from api.database import Base


# ── Python Enums ────────────────────────────────────────────────────


class UserRole(str, enum.Enum):
    admin = "admin"
    member = "member"


class SupplyChainStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class QuestionnaireStatus(str, enum.Enum):
    uploaded = "uploaded"
    extracting = "extracting"
    extracted = "extracted"
    reviewed = "reviewed"
    exported = "exported"


class QuestionStatus(str, enum.Enum):
    draft = "draft"
    reviewed = "reviewed"
    approved = "approved"


class ScenarioStatus(str, enum.Enum):
    draft = "draft"
    computed = "computed"
    archived = "archived"


class SubscriptionPlan(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"
    past_due = "past_due"


class AlertType(str, enum.Enum):
    emission_increase = "emission_increase"
    confidence_drop = "confidence_drop"
    target_exceeded = "target_exceeded"


class AlertSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class DataListingType(str, enum.Enum):
    emission_report = "emission_report"
    benchmark = "benchmark"
    supply_chain = "supply_chain"


class DataListingStatus(str, enum.Enum):
    active = "active"
    sold = "sold"
    withdrawn = "withdrawn"


class CreditReason(str, enum.Enum):
    subscription_grant = "subscription_grant"
    plan_upgrade = "plan_upgrade"
    estimate_usage = "estimate_usage"
    export_usage = "export_usage"
    pdf_export_usage = "pdf_export_usage"
    questionnaire_extract_usage = "questionnaire_extract_usage"
    scenario_compute_usage = "scenario_compute_usage"
    marketplace_purchase_usage = "marketplace_purchase_usage"
    manual = "manual"
    manual_grant = "manual_grant"
    monthly_reset = "monthly_reset"
    marketplace_sale = "marketplace_sale"
    plan_downgrade_adjustment = "plan_downgrade_adjustment"


class PCAFAssetClass(str, enum.Enum):
    """PCAF asset class categories for financed emissions."""
    listed_equity = "listed_equity"
    corporate_bonds = "corporate_bonds"
    business_loans = "business_loans"
    project_finance = "project_finance"
    commercial_real_estate = "commercial_real_estate"
    mortgages = "mortgages"
    sovereign_debt = "sovereign_debt"


class ReviewStatus(str, enum.Enum):
    """Data review workflow status."""
    draft = "draft"
    submitted = "submitted"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


# ── Company ─────────────────────────────────────────────────────────


class Company(Base):
    __tablename__ = "companies"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    name: str = Column(String(255), nullable=False)
    industry: str = Column(String(100), nullable=False)
    region: str = Column(String(10), nullable=False, default="US")
    employee_count: int | None = Column(Integer, nullable=True)
    revenue_usd: float | None = Column(Float, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    # relationships
    data_uploads = relationship("DataUpload", back_populates="company", cascade="all, delete-orphan")
    emission_reports = relationship("EmissionReport", back_populates="company", cascade="all, delete-orphan")


# ── User (company member) ──────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    email: str = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password: str = Column(String(255), nullable=False)
    full_name: str = Column(String(255), nullable=False)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    role: str = Column(Enum(UserRole, native_enum=False, length=50), default=UserRole.member)
    is_active: bool = Column(Boolean, nullable=False, default=True)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)
    last_login: datetime | None = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: int = Column(Integer, nullable=False, default=0)
    locked_until: datetime | None = Column(DateTime(timezone=True), nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


# ── Data uploads (raw operational data) ─────────────────────────────


class DataUpload(Base):
    __tablename__ = "data_uploads"
    __table_args__ = (
        Index("ix_data_uploads_company_year", "company_id", "year"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    year: int = Column(Integer, nullable=False)
    provided_data: dict = Column(JSON, nullable=False, default=dict)
    notes: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    company = relationship("Company", back_populates="data_uploads")


# ── Emission reports (subnet results) ──────────────────────────────


class EmissionReport(Base):
    __tablename__ = "emission_reports"
    __table_args__ = (
        Index("ix_emission_reports_company_year", "company_id", "year"),
        CheckConstraint("scope1 >= 0", name="ck_emission_reports_scope1_non_negative"),
        CheckConstraint("scope2 >= 0", name="ck_emission_reports_scope2_non_negative"),
        CheckConstraint("scope3 >= 0", name="ck_emission_reports_scope3_non_negative"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_emission_reports_confidence_range"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    data_upload_id: str | None = Column(String(32), ForeignKey("data_uploads.id", ondelete="SET NULL"), nullable=True)
    year: int = Column(Integer, nullable=False)

    # Results from Bittensor subnet
    scope1: float = Column(Float, nullable=False, default=0.0)
    scope2: float = Column(Float, nullable=False, default=0.0)
    scope3: float = Column(Float, nullable=False, default=0.0)
    total: float = Column(Float, nullable=False, default=0.0)
    breakdown: dict | None = Column(JSON, nullable=True)
    confidence: float = Column(Float, nullable=False, default=0.0)
    sources: list | None = Column(JSON, nullable=True)
    assumptions: list | None = Column(JSON, nullable=True)
    methodology_version: str = Column(String(50), default="ghg_protocol_v2025")

    # Scoring metadata (from validator)
    miner_scores: dict | None = Column(JSON, nullable=True)

    notes: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    company = relationship("Company", back_populates="emission_reports")


# ── Supply chain links ──────────────────────────────────────────────


class SupplyChainLink(Base):
    __tablename__ = "supply_chain_links"
    __table_args__ = (
        UniqueConstraint("buyer_company_id", "supplier_company_id", name="uq_supply_chain_buyer_supplier"),
        Index("ix_supply_chain_links_status", "status"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    buyer_company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    spend_usd: float | None = Column(Float, nullable=True)
    category: str = Column(String(100), default="purchased_goods")
    status: str = Column(Enum(SupplyChainStatus, native_enum=False, length=50), default=SupplyChainStatus.pending)
    notes: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    buyer = relationship("Company", foreign_keys=[buyer_company_id])
    supplier = relationship("Company", foreign_keys=[supplier_company_id])


# ── Webhooks (continuous monitoring) ─────────────────────────────────


class Webhook(Base):
    __tablename__ = "webhooks"
    __table_args__ = (
        UniqueConstraint("company_id", "url", name="uq_webhooks_company_url"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    url: str = Column(String(2048), nullable=False)
    event_types: list = Column(JSON, nullable=False, default=list)  # ["report.created", "data.uploaded"]
    secret: str = Column(String(255), nullable=False)
    active: bool = Column(Boolean, nullable=False, default=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    company = relationship("Company")
    deliveries = relationship("WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan", passive_deletes=True)


# ── Webhook delivery logs ────────────────────────────────────────────


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_created_at", "created_at"),
        Index("ix_webhook_deliveries_next_retry", "next_retry_at"),
        Index("ix_webhook_deliveries_company", "webhook_id"),
        Index("ix_webhook_deliveries_status_code", "status_code"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    webhook_id: str = Column(String(32), ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: str = Column(String(100), nullable=False)
    payload: dict = Column(JSON, nullable=False)
    status_code: int | None = Column(Integer, nullable=True)
    response_body: str | None = Column(Text, nullable=True)
    success: bool = Column(Boolean, nullable=False, default=False)
    error: str | None = Column(Text, nullable=True)
    duration_ms: int | None = Column(Integer, nullable=True)
    retry_count: int = Column(Integer, nullable=False, default=0)
    max_retries: int = Column(Integer, nullable=False, default=3)
    next_retry_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

    webhook = relationship("Webhook", back_populates="deliveries")


# ── Audit Log ───────────────────────────────────────────────────────


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_company_created", "company_id", "created_at"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    user_id: str = Column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    action: str = Column(String(100), nullable=False)
    resource_type: str = Column(String(100), nullable=False)
    resource_id: str | None = Column(String(32), nullable=True)
    detail: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow, index=True)


# ── Questionnaire ───────────────────────────────────────────────────


class Questionnaire(Base):
    """Uploaded sustainability questionnaire document."""
    __tablename__ = "questionnaires"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    title: str = Column(String(500), nullable=False)
    original_filename: str = Column(String(500), nullable=False)
    file_type: str = Column(String(20), nullable=False)  # pdf, xlsx, docx, csv
    file_size: int = Column(Integer, nullable=False)
    status: str = Column(Enum(QuestionnaireStatus, native_enum=False, length=50), default=QuestionnaireStatus.uploaded)
    extracted_text: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    company = relationship("Company")
    questions = relationship("QuestionnaireQuestion", back_populates="questionnaire", cascade="all, delete-orphan")


class QuestionnaireQuestion(Base):
    """Individual question extracted from a questionnaire."""
    __tablename__ = "questionnaire_questions"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    questionnaire_id: str = Column(String(32), ForeignKey("questionnaires.id", ondelete="CASCADE"), nullable=False, index=True)
    question_number: int = Column(Integer, nullable=False)
    question_text: str = Column(Text, nullable=False)
    category: str = Column(String(100), nullable=True)  # emissions, energy, waste, transport, governance, etc.
    ai_draft_answer: str | None = Column(Text, nullable=True)
    human_answer: str | None = Column(Text, nullable=True)
    status: str = Column(Enum(QuestionStatus, native_enum=False, length=50), default=QuestionStatus.draft)
    confidence: float = Column(Float, default=0.0)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    questionnaire = relationship("Questionnaire", back_populates="questions")


# ── Scenario (What-If) ──────────────────────────────────────────────


class Scenario(Base):
    """What-if scenario for predictive emissions analysis."""
    __tablename__ = "scenarios"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name: str = Column(String(255), nullable=False)
    description: str | None = Column(Text, nullable=True)
    base_report_id: str | None = Column(String(32), ForeignKey("emission_reports.id"), nullable=True)
    parameters: dict = Column(JSON, nullable=False, default=dict)  # what-if changes
    results: dict | None = Column(JSON, nullable=True)  # computed results
    status: str = Column(Enum(ScenarioStatus, native_enum=False, length=50), default=ScenarioStatus.draft)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    company = relationship("Company")


# ── Subscription & Billing ──────────────────────────────────────────


class Subscription(Base):
    """Company subscription for tiered access."""
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_subscription_company"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    plan: str = Column(Enum(SubscriptionPlan, native_enum=False, length=50), nullable=False, default=SubscriptionPlan.free)
    status: str = Column(Enum(SubscriptionStatus, native_enum=False, length=50), nullable=False, default=SubscriptionStatus.active)
    stripe_customer_id: str | None = Column(String(255), nullable=True)
    stripe_subscription_id: str | None = Column(String(255), nullable=True)
    current_period_start: datetime | None = Column(DateTime(timezone=True), nullable=True)
    current_period_end: datetime | None = Column(DateTime(timezone=True), nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    company = relationship("Company")


class CreditLedger(Base):
    """Credit transactions for API usage metering."""
    __tablename__ = "credit_ledger"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: int = Column(Integer, nullable=False)  # positive = add, negative = deduct
    reason: str = Column(Enum(CreditReason, native_enum=False, length=255), nullable=False)
    balance_after: int = Column(Integer, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow, index=True)

    __table_args__ = (
        CheckConstraint("balance_after >= 0", name="ck_credit_ledger_balance_non_negative"),
    )

    company = relationship("Company")


# ── Alerts ──────────────────────────────────────────────────────────


class Alert(Base):
    """Automated alert when emissions change significantly."""
    __tablename__ = "alerts"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type: str = Column(Enum(AlertType, native_enum=False, length=100), nullable=False)
    severity: str = Column(Enum(AlertSeverity, native_enum=False, length=50), nullable=False, default=AlertSeverity.info)
    title: str = Column(String(500), nullable=False)
    message: str = Column(Text, nullable=False)
    is_read: bool = Column(Boolean, nullable=False, default=False)
    acknowledged_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    metadata_json: dict | None = Column(JSON, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    company = relationship("Company")


# ── Data Marketplace ────────────────────────────────────────────────


class DataListing(Base):
    """Anonymized emissions data listed on the marketplace."""
    __tablename__ = "data_listings"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    seller_company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    title: str = Column(String(500), nullable=False)
    description: str | None = Column(Text, nullable=True)
    data_type: str = Column(Enum(DataListingType, native_enum=False, length=100), nullable=False)
    industry: str = Column(String(100), nullable=False)
    region: str = Column(String(10), nullable=False)
    year: int = Column(Integer, nullable=False)
    price_credits: int = Column(Integer, nullable=False, default=0)  # 0 = free
    anonymized_data: dict = Column(JSON, nullable=False, default=dict)
    status: str = Column(Enum(DataListingStatus, native_enum=False, length=50), default=DataListingStatus.active)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    seller = relationship("Company")


class DataPurchase(Base):
    """Record of a marketplace data purchase."""
    __tablename__ = "data_purchases"
    __table_args__ = (
        UniqueConstraint("listing_id", "buyer_company_id", name="uq_purchase_listing_buyer"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    listing_id: str = Column(String(32), ForeignKey("data_listings.id"), nullable=False, index=True)
    buyer_company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    price_credits: int = Column(Integer, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow, index=True)

    listing = relationship("DataListing")


# ── Token Storage (persistent) ──────────────────────────────────────


class RefreshToken(Base):
    """Persistent refresh token — replaces in-memory dict."""
    __tablename__ = "refresh_tokens"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    user_id: str = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: str = Column(String(128), unique=True, nullable=False, index=True)
    expires_at: datetime = Column(DateTime(timezone=True), nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)


class RevokedToken(Base):
    """Revoked JWT access token — checked in auth middleware."""
    __tablename__ = "revoked_tokens"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    jti: str = Column(String(64), unique=True, nullable=False, index=True)
    user_id: str = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    revoked_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    expires_at: datetime = Column(DateTime(timezone=True), nullable=False)


class PasswordResetToken(Base):
    """Persistent password-reset token — replaces in-memory _reset_tokens dict."""
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("ix_password_reset_tokens_email", "email"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    user_id: str = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email: str = Column(String(255), nullable=False)
    token_hash: str = Column(String(128), unique=True, nullable=False, index=True)
    expires_at: datetime = Column(DateTime(timezone=True), nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)


# ── PCAF Financed Emissions ─────────────────────────────────────────


class FinancedPortfolio(Base):
    """A financial institution's investment/lending portfolio for PCAF reporting."""
    __tablename__ = "financed_portfolios"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name: str = Column(String(255), nullable=False)
    year: int = Column(Integer, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    __table_args__ = (
        Index("ix_financed_portfolios_company_year", "company_id", "year"),
    )

    company = relationship("Company")
    assets = relationship("FinancedAsset", back_populates="portfolio", cascade="all, delete-orphan")


class FinancedAsset(Base):
    """Individual asset/investment in a PCAF portfolio."""
    __tablename__ = "financed_assets"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    portfolio_id: str = Column(String(32), ForeignKey("financed_portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_name: str = Column(String(255), nullable=False)
    asset_class: str = Column(Enum(PCAFAssetClass, native_enum=False, length=50), nullable=False)
    outstanding_amount: float = Column(Float, nullable=False)  # investment/loan amount
    total_equity_debt: float = Column(Float, nullable=False)   # investee total equity+debt
    investee_emissions_tco2e: float = Column(Float, nullable=False)  # investee reported or estimated GHG
    attribution_factor: float | None = Column(Float, nullable=True)  # auto-calculated if null
    financed_emissions_tco2e: float | None = Column(Float, nullable=True)  # auto-calculated
    data_quality_score: int = Column(Integer, nullable=False, default=3)  # PCAF 1-5 scale (1=best)
    industry: str | None = Column(String(100), nullable=True)
    region: str | None = Column(String(10), nullable=True)
    notes: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        CheckConstraint("outstanding_amount >= 0", name="ck_financed_assets_outstanding_non_negative"),
        CheckConstraint("total_equity_debt > 0", name="ck_financed_assets_equity_debt_positive"),
        CheckConstraint("investee_emissions_tco2e >= 0", name="ck_financed_assets_emissions_non_negative"),
        CheckConstraint("data_quality_score >= 1 AND data_quality_score <= 5", name="ck_financed_assets_dq_range"),
    )

    portfolio = relationship("FinancedPortfolio", back_populates="assets")


# ── Data Review & Approval Workflow ─────────────────────────────────


class DataReview(Base):
    """Track review/approval status of emission reports."""
    __tablename__ = "data_reviews"
    __table_args__ = (
        Index("ix_data_reviews_status", "status"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    report_id: str = Column(String(32), ForeignKey("emission_reports.id"), nullable=False, index=True)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    status: str = Column(Enum(ReviewStatus, native_enum=False, length=50), nullable=False, default=ReviewStatus.draft)
    submitted_by: str | None = Column(String(32), ForeignKey("users.id"), nullable=True)
    reviewed_by: str | None = Column(String(32), ForeignKey("users.id"), nullable=True)
    submitted_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    reviewed_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    review_notes: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    company = relationship("Company")
    report = relationship("EmissionReport")
    submitter = relationship("User", foreign_keys=[submitted_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])


# ── MFA (TOTP) ──────────────────────────────────────────────────────


class MFASecret(Base):
    """TOTP secret for multi-factor authentication."""
    __tablename__ = "mfa_secrets"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    user_id: str = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    totp_secret: str = Column(Text, nullable=False)  # Encrypted TOTP secret (Fernet-encrypted, ~250+ chars)
    is_enabled: bool = Column(Boolean, nullable=False, default=False)
    backup_codes: str | None = Column(Text, nullable=True)  # JSON array of hashed codes
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user = relationship("User")


# ── Industry Benchmarks ─────────────────────────────────────────────


class IndustryBenchmark(Base):
    """Pre-loaded industry benchmark data for comparison."""
    __tablename__ = "industry_benchmarks"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    industry: str = Column(String(100), nullable=False, index=True)
    region: str = Column(String(10), nullable=False, default="GLOBAL")
    year: int = Column(Integer, nullable=False)
    avg_scope1_tco2e: float = Column(Float, nullable=False, default=0.0)
    avg_scope2_tco2e: float = Column(Float, nullable=False, default=0.0)
    avg_scope3_tco2e: float = Column(Float, nullable=False, default=0.0)
    avg_total_tco2e: float = Column(Float, nullable=False, default=0.0)
    avg_intensity_per_employee: float | None = Column(Float, nullable=True)
    avg_intensity_per_revenue: float | None = Column(Float, nullable=True)
    sample_size: int = Column(Integer, nullable=False, default=0)
    source: str = Column(String(255), nullable=False, default="CarbonScope aggregated data")
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("industry", "region", "year", name="uq_benchmark_industry_region_year"),
    )


# ── Team Invitations ────────────────────────────────────────────────


class Invitation(Base):
    """Pending team member invitation."""
    __tablename__ = "invitations"
    __table_args__ = (
        Index("ix_invitations_token_hash", "token_hash"),
        Index("ix_invitations_email_company", "email", "company_id"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    email: str = Column(String(255), nullable=False)
    role: str = Column(Enum(UserRole, native_enum=False, length=50), nullable=False, default=UserRole.member)
    invited_by: str = Column(String(32), ForeignKey("users.id"), nullable=False)
    token_hash: str = Column(String(128), nullable=False, unique=True)
    expires_at: datetime = Column(DateTime(timezone=True), nullable=False)
    accepted_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

    company = relationship("Company")
    inviter = relationship("User")
