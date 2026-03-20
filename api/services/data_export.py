"""GDPR data portability export — aggregates all company/user data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import (
    Alert,
    AuditLog,
    Company,
    CreditLedger,
    DataListing,
    DataPurchase,
    DataReview,
    DataUpload,
    EmissionReport,
    FinancedAsset,
    FinancedPortfolio,
    Questionnaire,
    QuestionnaireQuestion,
    Scenario,
    Subscription,
    SupplyChainLink,
    User,
    Webhook,
    WebhookDelivery,
)

# Maximum rows per table to prevent OOM on large accounts
_MAX_ROWS_PER_TABLE = 10_000


def _row_to_dict(obj: Any) -> dict[str, Any]:
    """Convert an ORM model instance to a JSON-serialisable dict."""
    d: dict[str, Any] = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.key, None)
        if isinstance(val, datetime):
            val = val.isoformat()
        d[col.key] = val
    return d


async def gather_user_export(db: AsyncSession, user: User) -> dict[str, Any]:
    """Collect all data belonging to a user and their company."""
    company_id = user.company_id
    export: dict[str, Any] = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": _row_to_dict(user),
    }

    # Remove sensitive internal fields
    export["user"].pop("hashed_password", None)

    # Company
    if company_id:
        co = (await db.execute(select(Company).where(Company.id == company_id))).scalar_one_or_none()
        export["company"] = _row_to_dict(co) if co else None
    else:
        export["company"] = None

    async def _collect(model: Any, filter_col: str = "company_id") -> list[dict[str, Any]]:
        col = getattr(model, filter_col, None)
        if col is None or not company_id:
            return []
        rows = (await db.execute(select(model).where(col == company_id).limit(_MAX_ROWS_PER_TABLE))).scalars().all()
        return [_row_to_dict(r) for r in rows]

    export["data_uploads"] = await _collect(DataUpload)
    export["emission_reports"] = await _collect(EmissionReport)
    export["scenarios"] = await _collect(Scenario)
    export["questionnaires"] = await _collect(Questionnaire)
    export["supply_chain_links"] = await _collect(SupplyChainLink, "buyer_company_id")
    export["webhooks"] = await _collect(Webhook)
    export["alerts"] = await _collect(Alert)
    export["credit_ledger"] = await _collect(CreditLedger)
    export["data_listings"] = await _collect(DataListing, "seller_company_id")
    export["subscriptions"] = await _collect(Subscription)

    # Financed portfolios + assets (batch load to avoid N+1)
    portfolios = (
        await db.execute(select(FinancedPortfolio).where(FinancedPortfolio.company_id == company_id).limit(_MAX_ROWS_PER_TABLE))
    ).scalars().all()
    portfolio_ids = [p.id for p in portfolios]
    assets_by_pf: dict[str, list] = {}
    if portfolio_ids:
        all_assets = (
            await db.execute(select(FinancedAsset).where(FinancedAsset.portfolio_id.in_(portfolio_ids)))
        ).scalars().all()
        for a in all_assets:
            assets_by_pf.setdefault(a.portfolio_id, []).append(a)
    export["financed_portfolios"] = []
    for p in portfolios:
        pd = _row_to_dict(p)
        pd["assets"] = [_row_to_dict(a) for a in assets_by_pf.get(p.id, [])]
        export["financed_portfolios"].append(pd)

    # Questionnaire questions (batch load to avoid N+1)
    q_ids = [q["id"] for q in export["questionnaires"]]
    questions_by_q: dict[str, list] = {}
    if q_ids:
        all_questions = (
            await db.execute(select(QuestionnaireQuestion).where(QuestionnaireQuestion.questionnaire_id.in_(q_ids)))
        ).scalars().all()
        for qq in all_questions:
            questions_by_q.setdefault(qq.questionnaire_id, []).append(qq)
    for q in export["questionnaires"]:
        q["questions"] = [_row_to_dict(qq) for qq in questions_by_q.get(q["id"], [])]

    # Data purchases (buyer side)
    if company_id:
        purchases = (
            await db.execute(select(DataPurchase).where(DataPurchase.buyer_company_id == company_id))
        ).scalars().all()
        export["data_purchases"] = [_row_to_dict(p) for p in purchases]
    else:
        export["data_purchases"] = []

    # Data reviews
    if company_id:
        reviews = (
            await db.execute(select(DataReview).where(DataReview.company_id == company_id))
        ).scalars().all()
        export["data_reviews"] = [_row_to_dict(r) for r in reviews]
    else:
        export["data_reviews"] = []

    # Audit logs for this user
    logs = (
        await db.execute(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).limit(1000))
    ).scalars().all()
    export["audit_logs"] = [_row_to_dict(l) for l in logs]

    # Strip webhook secrets from export
    for wh in export["webhooks"]:
        wh.pop("secret", None)

    return export
