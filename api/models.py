"""Database models for the CarbonScope platform."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.dialects.sqlite import JSON
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
    active: bool = Column(Integer, nullable=False, default=1)  # SQLite has no bool
    created_at: datetime = Column(DateTime(timezone=True), default=_utcnow)

    company = relationship("Company")
