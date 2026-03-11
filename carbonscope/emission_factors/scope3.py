"""Scope 3 — Value chain emissions (15 categories).

Provides activity-based, spend-based, and employee-based estimation
methods, plus industry-default gap-filling logic.
"""

from __future__ import annotations

from typing import Any

from .loader import get_transport_factor, get_industry_profile, load_factors


# ── Category-specific calculators ───────────────────────────────────


def calc_cat1_purchased_goods(spend_usd: float, industry: str = "manufacturing") -> float:
    """Category 1 — Purchased goods & services (spend-based).

    Returns kgCO2e.
    """
    if spend_usd <= 0:
        return 0.0
    profile = get_industry_profile(industry)
    factor = profile.get("spend_factor_kgco2e_per_1000usd", 3.0)
    return round(spend_usd / 1000.0 * factor, 2)


def calc_cat4_transport(ton_km: float, mode: str = "road") -> float:
    """Category 4 — Upstream transportation & distribution.

    Parameters
    ----------
    ton_km:
        Freight volume in tonne-kilometres.
    mode:
        ``"road"``, ``"air"``, ``"sea"``, ``"rail"``, ``"inland_waterway"``.
    """
    if ton_km <= 0:
        return 0.0
    factor = get_transport_factor(mode)
    return round(ton_km * factor, 2)


def calc_cat5_waste(waste_kg: float, method: str = "landfill") -> float:
    """Category 5 — Waste generated in operations."""
    if waste_kg <= 0:
        return 0.0
    factors = {"landfill": 0.586, "recycling": 0.021, "incineration": 0.021}
    factor = factors.get(method, 0.586)
    return round(waste_kg * factor, 2)


def calc_cat6_business_travel(
    employee_count: int = 0,
    industry: str = "manufacturing",
    travel_spend_usd: float = 0.0,
) -> float:
    """Category 6 — Business travel.

    Uses industry-average per-employee factors or spend-based estimate.
    """
    if travel_spend_usd > 0:
        # Spend-based: ~0.3 kgCO2e per USD of travel spend (airline + hotel avg)
        return round(travel_spend_usd * 0.30, 2)

    if employee_count > 0:
        averages = load_factors("industry").get("business_travel_averages", {})
        tco2e_per_emp = averages.get(industry, averages.get("global_average", 1.5))
        return round(employee_count * tco2e_per_emp * 1000, 2)  # convert tCO2e → kgCO2e

    return 0.0


def calc_cat7_commuting(
    employee_count: int,
    region: str = "US",
) -> float:
    """Category 7 — Employee commuting.

    Uses regional average annual commuting emissions per employee.
    Returns kgCO2e.
    """
    if employee_count <= 0:
        return 0.0

    averages = load_factors("industry").get("commuting_averages", {})
    region_upper = region.upper().strip()
    tco2e_per_emp = averages.get(region_upper, averages.get("global", 1.5))
    return round(employee_count * tco2e_per_emp * 1000, 2)


def calc_spend_based(spend_usd: float, industry: str = "manufacturing") -> float:
    """Generic spend-based Scope 3 estimation.

    Falls back when no activity data is available.
    Returns kgCO2e for the full Scope 3 implied by the spend.
    """
    if spend_usd <= 0:
        return 0.0
    profile = get_industry_profile(industry)
    factor = profile.get("spend_factor_kgco2e_per_1000usd", 3.0)
    return round(spend_usd / 1000.0 * factor, 2)


# ── Industry-default gap-filling ────────────────────────────────────


def fill_industry_defaults(
    scope3_detail: dict[str, float],
    industry: str,
    provided_data: dict[str, Any],
) -> dict[str, float]:
    """Fill missing Scope 3 categories using industry averages.

    For categories already calculated (non-zero in *scope3_detail*), keeps the
    existing value.  For missing/zero categories, estimates from:
      - revenue_usd × industry profile
      - employee_count × per-employee averages
      - industry scope split ratios

    Returns the updated *scope3_detail* dict.
    """
    profile = get_industry_profile(industry)
    materiality = profile.get("scope3_materiality", {})

    # Estimate total Scope 3 from revenue or employee count
    revenue = provided_data.get("revenue_usd", 0) or 0
    employees = provided_data.get("employee_count", 0) or 0

    estimated_total_scope3_kg = 0.0
    if revenue > 0:
        tco2e_per_m_usd = profile.get("avg_tco2e_per_million_usd_revenue", 50.0)
        estimated_total_scope3_kg = (revenue / 1_000_000) * tco2e_per_m_usd * 1000  # to kgCO2e
        scope3_pct = profile["typical_scope_split"]["scope3_pct"]
        estimated_total_scope3_kg *= scope3_pct
    elif employees > 0:
        tco2e_per_emp = profile.get("avg_tco2e_per_employee", 10.0)
        estimated_total_scope3_kg = employees * tco2e_per_emp * 1000
        scope3_pct = profile["typical_scope_split"]["scope3_pct"]
        estimated_total_scope3_kg *= scope3_pct

    if estimated_total_scope3_kg <= 0:
        return scope3_detail

    # Fill each material category that is missing
    filled = dict(scope3_detail)
    already_accounted = sum(filled.values())

    for cat, weight in materiality.items():
        if filled.get(cat, 0) > 0:
            continue
        estimated_cat = estimated_total_scope3_kg * weight
        # Don't exceed remaining budget
        remaining = max(estimated_total_scope3_kg - already_accounted, 0)
        fill_val = min(estimated_cat, remaining)
        if fill_val > 0:
            filled[cat] = round(fill_val, 2)
            already_accounted += fill_val

    return filled
