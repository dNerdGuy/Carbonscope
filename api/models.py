"""Database models for the CarbonScope platform."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
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
    company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False)
    role: str = Column(String(50), default="member")  # admin | member
    is_active: bool = Column(Boolean, nullable=False, default=True)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)
    last_login: datetime | None = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: int = Column(Integer, nullable=False, default=0)
    locked_until: datetime | None = Column(DateTime(timezone=True), nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)


# ── Data uploads (raw operational data) ─────────────────────────────


class DataUpload(Base):
    __tablename__ = "data_uploads"
    __table_args__ = (
        Index("ix_data_uploads_company_year", "company_id", "year"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    year: int = Column(Integer, nullable=False)
    provided_data: dict = Column(JSON, nullable=False, default=dict)
    notes: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    company = relationship("Company", back_populates="data_uploads")


# ── Emission reports (subnet results) ──────────────────────────────


class EmissionReport(Base):
    __tablename__ = "emission_reports"
    __table_args__ = (
        Index("ix_emission_reports_company_year", "company_id", "year"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    data_upload_id: str | None = Column(String(32), ForeignKey("data_uploads.id"), nullable=True)
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

    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    deleted_at: datetime | None = Column(DateTime(timezone=True), nullable=True, default=None)

    company = relationship("Company", back_populates="emission_reports")


# ── Supply chain links ──────────────────────────────────────────────


class SupplyChainLink(Base):
    __tablename__ = "supply_chain_links"
    __table_args__ = (
        UniqueConstraint("buyer_company_id", "supplier_company_id", name="uq_supply_chain_buyer_supplier"),
    )

    id: str = Column(String(32), primary_key=True, default=_new_id)
    buyer_company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    supplier_company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    spend_usd: float | None = Column(Float, nullable=True)
    category: str = Column(String(100), default="purchased_goods")
    status: str = Column(String(50), default="pending")  # pending | verified | rejected
    notes: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

    buyer = relationship("Company", foreign_keys=[buyer_company_id])
    supplier = relationship("Company", foreign_keys=[supplier_company_id])


# ── Webhooks (continuous monitoring) ─────────────────────────────────


class Webhook(Base):
    __tablename__ = "webhooks"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    url: str = Column(String(2048), nullable=False)
    event_types: list = Column(JSON, nullable=False, default=list)  # ["report.created", "data.uploaded"]
    secret: str = Column(String(255), nullable=False)
    active: bool = Column(Boolean, nullable=False, default=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

    company = relationship("Company")


# ── Webhook delivery logs ────────────────────────────────────────────


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    webhook_id: str = Column(String(32), ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: str = Column(String(100), nullable=False)
    payload: dict = Column(JSON, nullable=False)
    status_code: int | None = Column(Integer, nullable=True)
    response_body: str | None = Column(Text, nullable=True)
    success: bool = Column(Boolean, nullable=False, default=False)
    error: str | None = Column(Text, nullable=True)
    duration_ms: int | None = Column(Integer, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

    webhook = relationship("Webhook")


# ── Audit Log ───────────────────────────────────────────────────────


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    user_id: str = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    action: str = Column(String(100), nullable=False)
    resource_type: str = Column(String(100), nullable=False)
    resource_id: str | None = Column(String(32), nullable=True)
    detail: str | None = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)


# ── Questionnaire ───────────────────────────────────────────────────


class Questionnaire(Base):
    """Uploaded sustainability questionnaire document."""
    __tablename__ = "questionnaires"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    title: str = Column(String(500), nullable=False)
    original_filename: str = Column(String(500), nullable=False)
    file_type: str = Column(String(20), nullable=False)  # pdf, xlsx, docx, csv
    file_size: int = Column(Integer, nullable=False)
    status: str = Column(String(50), default="uploaded")  # uploaded | extracting | extracted | reviewed | exported
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
    status: str = Column(String(50), default="draft")  # draft | reviewed | approved
    confidence: float = Column(Float, default=0.0)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    questionnaire = relationship("Questionnaire", back_populates="questions")


# ── Scenario (What-If) ──────────────────────────────────────────────


class Scenario(Base):
    """What-if scenario for predictive emissions analysis."""
    __tablename__ = "scenarios"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    name: str = Column(String(255), nullable=False)
    description: str | None = Column(Text, nullable=True)
    base_report_id: str | None = Column(String(32), ForeignKey("emission_reports.id"), nullable=True)
    parameters: dict = Column(JSON, nullable=False, default=dict)  # what-if changes
    results: dict | None = Column(JSON, nullable=True)  # computed results
    status: str = Column(String(50), default="draft")  # draft | computed | archived
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    company = relationship("Company")


# ── Subscription & Billing ──────────────────────────────────────────


class Subscription(Base):
    """Company subscription for tiered access."""
    __tablename__ = "subscriptions"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    plan: str = Column(String(50), nullable=False, default="free")  # free | pro | enterprise
    status: str = Column(String(50), nullable=False, default="active")  # active | cancelled | past_due
    stripe_customer_id: str | None = Column(String(255), nullable=True)
    stripe_subscription_id: str | None = Column(String(255), nullable=True)
    current_period_start: datetime | None = Column(DateTime(timezone=True), nullable=True)
    current_period_end: datetime | None = Column(DateTime(timezone=True), nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    company = relationship("Company")


class CreditLedger(Base):
    """Credit transactions for API usage metering."""
    __tablename__ = "credit_ledger"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    amount: int = Column(Integer, nullable=False)  # positive = add, negative = deduct
    reason: str = Column(String(255), nullable=False)  # subscription_grant | estimate_usage | export_usage | manual
    balance_after: int = Column(Integer, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

    company = relationship("Company")


# ── Alerts ──────────────────────────────────────────────────────────


class Alert(Base):
    """Automated alert when emissions change significantly."""
    __tablename__ = "alerts"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    alert_type: str = Column(String(100), nullable=False)  # emission_increase | confidence_drop | target_exceeded
    severity: str = Column(String(50), nullable=False, default="info")  # info | warning | critical
    title: str = Column(String(500), nullable=False)
    message: str = Column(Text, nullable=False)
    is_read: bool = Column(Boolean, nullable=False, default=False)
    acknowledged_at: datetime | None = Column(DateTime(timezone=True), nullable=True)
    metadata_json: dict | None = Column(JSON, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

    company = relationship("Company")


# ── Data Marketplace ────────────────────────────────────────────────


class DataListing(Base):
    """Anonymized emissions data listed on the marketplace."""
    __tablename__ = "data_listings"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    seller_company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    title: str = Column(String(500), nullable=False)
    description: str | None = Column(Text, nullable=True)
    data_type: str = Column(String(100), nullable=False)  # emission_report | benchmark | supply_chain
    industry: str = Column(String(100), nullable=False)
    region: str = Column(String(10), nullable=False)
    year: int = Column(Integer, nullable=False)
    price_credits: int = Column(Integer, nullable=False, default=0)  # 0 = free
    anonymized_data: dict = Column(JSON, nullable=False, default=dict)
    status: str = Column(String(50), default="active")  # active | sold | withdrawn
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

    seller = relationship("Company")


class DataPurchase(Base):
    """Record of a marketplace data purchase."""
    __tablename__ = "data_purchases"

    id: str = Column(String(32), primary_key=True, default=_new_id)
    listing_id: str = Column(String(32), ForeignKey("data_listings.id"), nullable=False, index=True)
    buyer_company_id: str = Column(String(32), ForeignKey("companies.id"), nullable=False, index=True)
    price_credits: int = Column(Integer, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

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
