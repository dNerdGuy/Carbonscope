"""Test case generator — curated + synthetic questionnaires with ground truth.

Provides a set of realistic company questionnaires and their expected
(hand-calculated) emission values for validator scoring.
"""

from __future__ import annotations

import random
from typing import Any

from carbonscope.emission_factors.scope1 import calc_stationary_combustion, calc_mobile_combustion
from carbonscope.emission_factors.scope2 import calc_location_based
from carbonscope.emission_factors.scope3 import (
    calc_cat1_purchased_goods,
    calc_cat4_transport,
    calc_cat6_business_travel,
    calc_cat7_commuting,
    fill_industry_defaults,
)


# ── Curated test cases ──────────────────────────────────────────────

CURATED_CASES: list[dict[str, Any]] = [
    {
        "id": "logistics_provider_x",
        "description": "Large logistics company — high Scope 1 (fuel), moderate Scope 2",
        "questionnaire": {
            "company": "Logistics Provider X",
            "industry": "transportation",
            "services_used": ["freight shipping", "warehousing"],
            "provided_data": {
                "fuel_use_liters": 1_887_000,  # ~5000 tonnes diesel (5000*1000/0.832 density ≈ 6.01M, using 5000t * 1000kg/t / 0.832 kg/L)
                "fuel_type": "diesel",
                "electricity_kwh": 1_200_000,
                "employee_count": 500,
                "revenue_usd": 50_000_000,
                "vehicle_km": 2_000_000,
            },
            "region": "US",
            "year": 2025,
        },
        "context": {"methodology": "ghg_protocol"},
    },
    {
        "id": "us_manufacturer",
        "description": "Mid-size US manufacturer in Ohio — Scope 1 gas, Scope 2 coal-heavy grid",
        "questionnaire": {
            "company": "MidWest Manufacturing Co",
            "industry": "manufacturing",
            "services_used": ["industrial manufacturing", "assembly"],
            "provided_data": {
                "natural_gas_m3": 500_000,
                "electricity_kwh": 5_000_000,
                "employee_count": 200,
                "revenue_usd": 30_000_000,
                "supplier_spend_usd": 10_000_000,
                "shipping_ton_km": 500_000,
            },
            "region": "RFCW",  # Ohio — 560 gCO2e/kWh
            "year": 2025,
        },
        "context": {"methodology": "ghg_protocol"},
    },
    {
        "id": "tech_saas",
        "description": "SaaS company in California — minimal S1, low S2, S3 dominated by travel",
        "questionnaire": {
            "company": "CloudTech Inc",
            "industry": "technology",
            "services_used": ["cloud services", "software development"],
            "provided_data": {
                "electricity_kwh": 200_000,
                "employee_count": 50,
                "revenue_usd": 10_000_000,
                "supplier_spend_usd": 500_000,
                "business_travel_usd": 200_000,
                "office_sqm": 1_000,
            },
            "region": "CAMX",  # California — 240 gCO2e/kWh
            "year": 2025,
        },
        "context": {"methodology": "ghg_protocol"},
    },
    {
        "id": "minimal_data_retail",
        "description": "Edge case — retailer provides only industry + revenue",
        "questionnaire": {
            "company": "RetailCo",
            "industry": "retail",
            "services_used": ["retail sales"],
            "provided_data": {
                "revenue_usd": 50_000_000,
            },
            "region": "US",
            "year": 2025,
        },
        "context": {"methodology": "ghg_protocol"},
    },
    {
        "id": "inconsistent_data",
        "description": "Edge case — claims zero fuel but has vehicle fleet",
        "questionnaire": {
            "company": "InconsistentCo",
            "industry": "transportation",
            "services_used": ["freight shipping"],
            "provided_data": {
                "fuel_use_liters": 0,
                "vehicle_km": 500_000,
                "electricity_kwh": 100_000,
                "employee_count": 30,
            },
            "region": "DE",  # Germany
            "year": 2025,
        },
        "context": {"methodology": "ghg_protocol"},
    },
]


def _compute_ground_truth(case: dict[str, Any]) -> dict[str, float]:
    """Compute ground-truth emissions for a test case using our reference implementation."""
    q = case["questionnaire"]
    data = q.get("provided_data", {})
    industry = q.get("industry", "manufacturing")
    region = q.get("region", "US")

    # Scope 1
    s1 = 0.0
    fuel = data.get("fuel_use_liters") or 0
    fuel_type = data.get("fuel_type", "diesel")
    if fuel > 0:
        s1 += calc_stationary_combustion(fuel_type, fuel, "liters")
    ng = data.get("natural_gas_m3") or 0
    if ng > 0:
        s1 += calc_stationary_combustion("natural_gas", ng, "m3")
    vkm = data.get("vehicle_km") or 0
    if vkm > 0:
        s1 += calc_mobile_combustion("heavy_truck_diesel", distance_km=vkm)

    # Scope 2
    s2 = 0.0
    elec = data.get("electricity_kwh") or 0
    if elec > 0:
        s2 = calc_location_based(elec, region)

    # Scope 3
    s3_detail: dict[str, float] = {}
    spend = data.get("supplier_spend_usd") or 0
    if spend > 0:
        s3_detail["cat1_purchased_goods"] = calc_cat1_purchased_goods(spend, industry)
    tkm = data.get("shipping_ton_km") or 0
    if tkm > 0:
        s3_detail["cat4_upstream_transport"] = calc_cat4_transport(tkm, "road")
    travel = data.get("business_travel_usd") or 0
    emps = data.get("employee_count") or 0
    if travel > 0 or emps > 0:
        s3_detail["cat6_business_travel"] = calc_cat6_business_travel(emps, industry, travel)
    if emps > 0:
        s3_detail["cat7_commuting"] = calc_cat7_commuting(emps, region)
    s3_detail = fill_industry_defaults(s3_detail, industry, data)
    s3 = sum(s3_detail.values())

    return {
        "scope1": round(s1, 2),
        "scope2": round(s2, 2),
        "scope3": round(s3, 2),
        "total": round(s1 + s2 + s3, 2),
    }


def get_curated_cases() -> list[dict[str, Any]]:
    """Return curated test cases with pre-computed ground truth."""
    cases = []
    for case in CURATED_CASES:
        enriched = dict(case)
        enriched["ground_truth"] = _compute_ground_truth(case)
        cases.append(enriched)
    return cases


def get_case_by_id(case_id: str) -> dict[str, Any] | None:
    """Look up a single curated case by ID."""
    for case in get_curated_cases():
        if case["id"] == case_id:
            return case
    return None


# ── Synthetic query generator ───────────────────────────────────────

_INDUSTRIES = ["manufacturing", "transportation", "technology", "retail",
               "energy", "financial_services", "construction", "food_beverage"]
_REGIONS = ["US", "GB", "DE", "FR", "IN", "CN", "JP", "AU", "BR", "CA"]


def generate_synthetic_query(
    completeness_level: float = 0.5,
) -> dict[str, Any]:
    """Generate a random synthetic company questionnaire.

    Parameters
    ----------
    completeness_level:
        0.0–1.0 — fraction of data fields to populate.
    """
    industry = random.choice(_INDUSTRIES)
    region = random.choice(_REGIONS)

    all_fields: dict[str, Any] = {
        "fuel_use_liters": random.uniform(1_000, 500_000),
        "fuel_type": random.choice(["diesel", "gasoline", "natural_gas"]),
        "natural_gas_m3": random.uniform(1_000, 200_000),
        "electricity_kwh": random.uniform(50_000, 5_000_000),
        "vehicle_km": random.uniform(10_000, 2_000_000),
        "employee_count": random.randint(10, 5000),
        "revenue_usd": random.uniform(1_000_000, 100_000_000),
        "supplier_spend_usd": random.uniform(100_000, 20_000_000),
        "shipping_ton_km": random.uniform(10_000, 1_000_000),
        "office_sqm": random.uniform(100, 50_000),
    }

    # Keep only a fraction of fields based on completeness
    field_names = list(all_fields.keys())
    n_keep = max(1, int(len(field_names) * completeness_level))
    kept = random.sample(field_names, n_keep)
    provided_data = {k: all_fields[k] for k in kept}
    # Ensure fuel_type is present when fuel_use_liters is
    if "fuel_use_liters" in provided_data and "fuel_type" not in provided_data:
        provided_data["fuel_type"] = "diesel"

    questionnaire = {
        "company": f"Synthetic-{random.randint(1000,9999)}",
        "industry": industry,
        "services_used": [f"{industry} operations"],
        "provided_data": provided_data,
        "region": region,
        "year": 2025,
    }
    context = {"methodology": "ghg_protocol"}

    case = {
        "id": f"synthetic_{random.randint(10000,99999)}",
        "questionnaire": questionnaire,
        "context": context,
    }
    case["ground_truth"] = _compute_ground_truth(case)
    return case
