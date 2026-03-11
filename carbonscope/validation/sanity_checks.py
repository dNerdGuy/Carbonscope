"""Sanity checks — anti-hallucination detection.

Catches physically impossible or highly suspicious emission values that
indicate a miner is guessing/hallucinating rather than computing properly.
"""

from __future__ import annotations

from typing import Any


def run_sanity_checks(
    emissions: dict,
    breakdown: dict | None,
    confidence: float | None,
    questionnaire: dict,
) -> float:
    """Return a 0.0–1.0 score (1.0 = fully sane).

    Checks:
    1. No negative emissions.
    2. Scope 2 consistent with electricity input (±50% tolerance).
    3. No extreme values (> 100× industry average per employee/revenue).
    4. Confidence is not 1.0 when data is clearly incomplete.
    5. Total emissions > 0 when any activity data is provided.
    """
    score = 1.0
    provided_data = questionnaire.get("provided_data", {})
    industry = questionnaire.get("industry", "manufacturing")

    s1 = emissions.get("scope1", 0)
    s2 = emissions.get("scope2", 0)
    s3 = emissions.get("scope3", 0)
    total = emissions.get("total", 0)

    # 1. Negative emissions
    for val in [s1, s2, s3, total]:
        if val < 0:
            score -= 0.30
            break

    # 2. Scope 2 consistency with electricity input
    electricity_kwh = provided_data.get("electricity_kwh") or 0
    if electricity_kwh > 0 and s2 > 0:
        # Scope 2 should be roughly electricity × grid factor (0.01–0.9 kgCO2e/kWh)
        min_expected = electricity_kwh * 0.01
        max_expected = electricity_kwh * 0.9
        if s2 < min_expected * 0.5 or s2 > max_expected * 1.5:
            score -= 0.20

    # 3. Extreme value detection
    employees = provided_data.get("employee_count") or 0
    revenue = provided_data.get("revenue_usd") or 0

    # Industry upper bounds (kgCO2e per employee — generous 10× multiplier)
    _UPPER_PER_EMPLOYEE = {
        "technology": 50_000,
        "financial_services": 30_000,
        "manufacturing": 250_000,
        "transportation": 400_000,
        "energy": 2_000_000,
        "retail": 80_000,
        "construction": 200_000,
        "food_beverage": 180_000,
        "healthcare": 100_000,
    }

    if employees > 0:
        upper = _UPPER_PER_EMPLOYEE.get(industry, 250_000)
        if total > employees * upper:
            score -= 0.20

    # 4. Suspicious confidence
    if confidence is not None:
        # Count how many data fields are actually provided
        data_fields = [
            "fuel_use_liters", "natural_gas_m3", "electricity_kwh",
            "vehicle_km", "employee_count", "revenue_usd",
            "supplier_spend_usd", "shipping_ton_km",
        ]
        filled = sum(1 for f in data_fields if (provided_data.get(f) or 0) > 0)
        if filled <= 2 and confidence is not None and confidence > 0.9:
            score -= 0.15  # can't be 90%+ confident with ≤2 data fields

    # 5. Zero total with activity data
    has_any_data = any(
        (provided_data.get(f) or 0) > 0
        for f in ["fuel_use_liters", "natural_gas_m3", "electricity_kwh", "vehicle_km"]
    )
    if has_any_data and total == 0:
        score -= 0.25

    return max(score, 0.0)
