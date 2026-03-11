"""Missing data prediction service.

Uses industry benchmarks and statistical relationships to predict
emissions for categories where no primary data is available.
Provides uncertainty bounds (low/mid/high) to quantify prediction quality.
"""

from __future__ import annotations

import math
from typing import Any

from carbonscope.emission_factors.loader import get_industry_profile, load_factors


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

    # Choose prediction strategy based on available proxy data
    if revenue > 0 and employees > 0:
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
