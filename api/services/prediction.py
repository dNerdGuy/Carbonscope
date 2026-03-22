"""Missing data prediction service.

Uses industry benchmarks and statistical relationships to predict
emissions for categories where no primary data is available.
Provides uncertainty bounds (low/mid/high) to quantify prediction quality.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any

from carbonscope.emission_factors.loader import get_industry_profile, load_factors

logger = logging.getLogger(__name__)

# ── ML model (optional) ─────────────────────────────────────────────
# When the trained artifact is present the service augments rule-based
# predictions with ML estimates; otherwise it falls back gracefully.

_MODEL_PATH: str = os.getenv(
    "SCOPE3_MODEL_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "data" / "model" / "scope3_predictor.pkl"),
)

_ml_artifact: dict | None = None
_ml_load_attempted: bool = False


def _load_model() -> dict | None:
    """Lazily load the scikit-learn artifact.  Returns None if unavailable."""
    global _ml_artifact, _ml_load_attempted
    if _ml_load_attempted:
        return _ml_artifact
    _ml_load_attempted = True
    if not Path(_MODEL_PATH).exists():
        return None
    try:
        import joblib  # noqa: PLC0415
        _ml_artifact = joblib.load(_MODEL_PATH)
        logger.info("Loaded ML prediction model v%s from %s",
                    _ml_artifact.get("version", "?"), _MODEL_PATH)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to load ML prediction model: %s — using rule-based fallback", exc)
    return _ml_artifact


def _ml_predict(industry: str, region: str, revenue_usd: float, employee_count: int) -> dict[str, float] | None:
    """Return ML-based scope predictions or None if model is unavailable."""
    artifact = _load_model()
    if artifact is None:
        return None
    try:
        import numpy as np  # noqa: PLC0415
        log_emp = float(np.log1p(employee_count))
        log_rev = float(np.log1p(revenue_usd))
        X = np.array([[industry, region, float(employee_count), revenue_usd, log_emp, log_rev]], dtype=object)
        models: dict = artifact["models"]
        return {
            scope: float(max(0.0, models[scope].predict(X)[0]))
            for scope in ("scope1", "scope2", "scope3")
            if scope in models
        }
    except Exception as exc:  # pragma: no cover
        logger.warning("ML prediction failed: %s — falling back to rule-based", exc)
        return None


# ── Intensity-based prediction ──────────────────────────────────────

# Revenue-based and employee-based emission intensities by industry
# Sources: CDP 2023 disclosure data, EPA GHG Reporting Program
_REVENUE_INTENSITIES: dict[str, dict[str, float]] = {
    # tCO2e per $M USD revenue
    "energy":          {"scope1": 450.0, "scope2": 85.0,  "scope3": 280.0},
    "manufacturing":   {"scope1": 120.0, "scope2": 65.0,  "scope3": 300.0},
    "technology":      {"scope1": 5.0,   "scope2": 25.0,  "scope3": 95.0},
    "transportation":  {"scope1": 300.0, "scope2": 30.0,  "scope3": 180.0},
    "retail":          {"scope1": 15.0,  "scope2": 45.0,  "scope3": 350.0},
    "healthcare":      {"scope1": 25.0,  "scope2": 55.0,  "scope3": 150.0},
    "finance":         {"scope1": 3.0,   "scope2": 20.0,  "scope3": 80.0},
    "construction":    {"scope1": 180.0, "scope2": 40.0,  "scope3": 250.0},
    "agriculture":     {"scope1": 250.0, "scope2": 30.0,  "scope3": 200.0},
}

_EMPLOYEE_INTENSITIES: dict[str, dict[str, float]] = {
    # tCO2e per employee
    "energy":          {"scope1": 45.0, "scope2": 8.5, "scope3": 28.0},
    "manufacturing":   {"scope1": 18.0, "scope2": 9.5, "scope3": 40.0},
    "technology":      {"scope1": 1.2,  "scope2": 3.5, "scope3": 12.0},
    "transportation":  {"scope1": 35.0, "scope2": 4.0, "scope3": 20.0},
    "retail":          {"scope1": 2.5,  "scope2": 6.0, "scope3": 22.0},
    "healthcare":      {"scope1": 3.5,  "scope2": 7.5, "scope3": 18.0},
    "finance":         {"scope1": 0.8,  "scope2": 4.0, "scope3": 10.0},
    "construction":    {"scope1": 22.0, "scope2": 5.0, "scope3": 30.0},
    "agriculture":     {"scope1": 30.0, "scope2": 3.5, "scope3": 25.0},
}

# Uncertainty multipliers for confidence intervals
_UNCERTAINTY = {
    "revenue_based":   {"low": 0.5, "high": 1.8},  # Revenue-only has wide bands
    "employee_based":  {"low": 0.55, "high": 1.7},
    "hybrid":          {"low": 0.65, "high": 1.5},
    "partial_data":    {"low": 0.75, "high": 1.35},
}


def _default() -> dict[str, float]:
    return {"scope1": 0.0, "scope2": 0.0, "scope3": 0.0}


def predict_from_revenue(
    revenue_usd: float,
    industry: str,
) -> dict[str, float]:
    """Predict emissions from annual revenue and industry."""
    intensities = _REVENUE_INTENSITIES.get(industry.lower(), _REVENUE_INTENSITIES["manufacturing"])
    revenue_m = revenue_usd / 1_000_000
    return {
        "scope1": round(intensities["scope1"] * revenue_m, 2),
        "scope2": round(intensities["scope2"] * revenue_m, 2),
        "scope3": round(intensities["scope3"] * revenue_m, 2),
    }


def predict_from_employees(
    employee_count: int,
    industry: str,
) -> dict[str, float]:
    """Predict emissions from employee count and industry."""
    intensities = _EMPLOYEE_INTENSITIES.get(industry.lower(), _EMPLOYEE_INTENSITIES["manufacturing"])
    return {
        "scope1": round(intensities["scope1"] * employee_count, 2),
        "scope2": round(intensities["scope2"] * employee_count, 2),
        "scope3": round(intensities["scope3"] * employee_count, 2),
    }


def predict_missing_emissions(
    known_data: dict[str, Any],
    industry: str,
    region: str = "US",
) -> dict[str, Any]:
    """Predict emissions for categories where no primary data exists.

    Returns dict with:
        predictions: {scope: tCO2e} for each missing scope
        method: which prediction method was used
        uncertainty: {low, mid, high} bounds
        filled_categories: which Scope 3 subcategories were predicted
        confidence_adjustment: factor to adjust report confidence
    """
    revenue = known_data.get("revenue_usd") or 0
    employees = known_data.get("employee_count") or 0

    # Determine what's already calculated vs missing
    has_scope1_data = any(
        known_data.get(k) for k in ["fuel_use_liters", "natural_gas_therms", "diesel_gallons",
                                     "gasoline_gallons", "vehicle_km", "fleet_miles"]
    )
    has_scope2_data = bool(known_data.get("electricity_kwh"))
    has_scope3_data = any(
        known_data.get(k) for k in ["supplier_spend_usd", "purchased_goods_usd",
                                     "shipping_ton_km", "freight_ton_miles",
                                     "waste_kg", "waste_metric_tons",
                                     "business_travel_usd", "business_travel_miles"]
    )

    predictions: dict[str, float] = {}
    method = "none"
    filled_categories: list[str] = []

    # Try ML model first; fall back to intensity-factor rules if unavailable
    ml_preds = _ml_predict(industry, region, revenue, employees)
    if ml_preds is not None:
        predictions = {k: round(v, 2) for k, v in ml_preds.items()}
        method = "ml_gradient_boosting"
    elif revenue > 0 and employees > 0:
        # Hybrid: average of both approaches
        rev_pred = predict_from_revenue(revenue, industry)
        emp_pred = predict_from_employees(employees, industry)
        method = "hybrid"
        for scope in ("scope1", "scope2", "scope3"):
            predictions[scope] = round((rev_pred[scope] + emp_pred[scope]) / 2, 2)
    elif revenue > 0:
        predictions = predict_from_revenue(revenue, industry)
        method = "revenue_based"
    elif employees > 0:
        predictions = predict_from_employees(employees, industry)
        method = "employee_based"
    else:
        # Use industry average per-company (median company size)
        profile = get_industry_profile(industry)
        if profile:
            avg_total = profile.get("avg_total_tco2e", 5000)
            splits = profile.get("scope_split", {"scope1": 0.2, "scope2": 0.15, "scope3": 0.65})
            predictions = {
                "scope1": round(avg_total * splits.get("scope1", 0.2), 2),
                "scope2": round(avg_total * splits.get("scope2", 0.15), 2),
                "scope3": round(avg_total * splits.get("scope3", 0.65), 2),
            }
        else:
            predictions = {"scope1": 1000.0, "scope2": 750.0, "scope3": 3250.0}
        method = "industry_average"

    # Only fill in scopes with no primary data
    final_predictions: dict[str, float] = {}
    if not has_scope1_data:
        final_predictions["scope1"] = predictions.get("scope1", 0)
        filled_categories.append("Scope 1 (all categories)")
    if not has_scope2_data:
        final_predictions["scope2"] = predictions.get("scope2", 0)
        filled_categories.append("Scope 2 (electricity)")
    if not has_scope3_data:
        final_predictions["scope3"] = predictions.get("scope3", 0)
        filled_categories.extend([
            "Scope 3 Cat 1 (Purchased goods)",
            "Scope 3 Cat 4 (Transport)",
            "Scope 3 Cat 5 (Waste)",
            "Scope 3 Cat 6 (Business travel)",
            "Scope 3 Cat 7 (Commuting)",
        ])

    # Calculate uncertainty bounds
    unc_key = "partial_data" if (has_scope1_data or has_scope2_data or has_scope3_data) else method
    unc = _UNCERTAINTY.get(unc_key, _UNCERTAINTY["revenue_based"])
    mid_total = sum(final_predictions.values())
    uncertainty = {
        "low": round(mid_total * unc["low"], 2),
        "mid": round(mid_total, 2),
        "high": round(mid_total * unc["high"], 2),
    }

    # Confidence adjustment — primary data scopes get full credit
    data_coverage = sum([has_scope1_data, has_scope2_data, has_scope3_data]) / 3.0
    confidence_adjustment = 0.4 + 0.6 * data_coverage  # 40% base, up to 100%

    return {
        "predictions": final_predictions,
        "method": method,
        "uncertainty": uncertainty,
        "filled_categories": filled_categories,
        "confidence_adjustment": round(confidence_adjustment, 4),
    }
