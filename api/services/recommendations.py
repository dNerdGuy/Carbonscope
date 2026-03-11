"""Carbon reduction recommendation engine.

Analyzes an emission profile and returns ranked, actionable
reduction pathways with estimated CO2 savings and cost impact.
"""

from __future__ import annotations

from typing import Any


# ── Reduction strategies database ────────────────────────────────────

_STRATEGIES: list[dict[str, Any]] = [
    # Scope 1 reductions
    {
        "id": "electrify_fleet",
        "scope": 1,
        "category": "Mobile Combustion",
        "title": "Electrify Vehicle Fleet",
        "description": "Replace diesel/gasoline fleet vehicles with electric vehicles (EVs). Shifts emissions from Scope 1 to Scope 2 (lower with clean grid).",
        "reduction_pct": 0.60,
        "cost_tier": "high",
        "payback_years": 5,
        "difficulty": "medium",
        "co_benefits": ["Reduced fuel costs", "Lower maintenance", "Regulatory compliance"],
        "applicable_when": lambda data, breakdown: breakdown.get("scope1_detail", {}).get("mobile_combustion", 0) > 100,
    },
    {
        "id": "switch_renewable_gas",
        "scope": 1,
        "category": "Stationary Combustion",
        "title": "Switch to Renewable Natural Gas",
        "description": "Replace conventional natural gas with certified renewable natural gas (RNG) or biogas for heating and processes.",
        "reduction_pct": 0.80,
        "cost_tier": "medium",
        "payback_years": 3,
        "difficulty": "low",
        "co_benefits": ["Carbon-neutral fuel", "Often drop-in replacement"],
        "applicable_when": lambda data, breakdown: (
            breakdown.get("scope1_detail", {}).get("stationary_combustion", 0) > 50
            or breakdown.get("scope1_detail", {}).get("natural_gas", 0) > 50
        ),
    },
    {
        "id": "refrigerant_management",
        "scope": 1,
        "category": "Fugitive Emissions",
        "title": "Upgrade Refrigerant Management",
        "description": "Transition to low-GWP refrigerants (HFO, CO2, ammonia) and improve leak detection systems.",
        "reduction_pct": 0.70,
        "cost_tier": "medium",
        "payback_years": 4,
        "difficulty": "medium",
        "co_benefits": ["Regulatory compliance (Kigali Amendment)", "Reduced refrigerant purchase costs"],
        "applicable_when": lambda data, breakdown: breakdown.get("scope1_detail", {}).get("fugitive_emissions", 0) > 50,
    },
    # Scope 2 reductions
    {
        "id": "onsite_solar",
        "scope": 2,
        "category": "Electricity",
        "title": "Install On-site Solar PV",
        "description": "Install rooftop or ground-mount solar panels to generate on-site renewable electricity.",
        "reduction_pct": 0.40,
        "cost_tier": "high",
        "payback_years": 7,
        "difficulty": "medium",
        "co_benefits": ["Energy cost savings", "Energy independence", "Grid resilience"],
        "applicable_when": lambda data, breakdown: breakdown.get("scope2_detail", {}).get("location_based", 0) > 100,
    },
    {
        "id": "purchase_recs",
        "scope": 2,
        "category": "Electricity",
        "title": "Purchase Renewable Energy Certificates (RECs)",
        "description": "Purchase RECs or sign a virtual PPA to cover 100% of electricity consumption with renewable sources.",
        "reduction_pct": 0.95,
        "cost_tier": "low",
        "payback_years": 0,
        "difficulty": "low",
        "co_benefits": ["Immediate Scope 2 market-based reduction", "Sustainability branding"],
        "applicable_when": lambda data, breakdown: breakdown.get("scope2_detail", {}).get("location_based", 0) > 50,
    },
    {
        "id": "energy_efficiency",
        "scope": 2,
        "category": "Electricity",
        "title": "Energy Efficiency Upgrades",
        "description": "LED lighting, HVAC optimization, building envelope improvements, smart controls.",
        "reduction_pct": 0.25,
        "cost_tier": "medium",
        "payback_years": 3,
        "difficulty": "low",
        "co_benefits": ["Reduced energy bills", "Improved comfort", "Extended equipment life"],
        "applicable_when": lambda data, breakdown: breakdown.get("scope2_detail", {}).get("location_based", 0) > 0,
    },
    # Scope 3 reductions
    {
        "id": "supplier_engagement",
        "scope": 3,
        "category": "Purchased Goods & Services",
        "title": "Supplier Carbon Engagement Program",
        "description": "Require top suppliers to set science-based targets. Shift procurement to lower-carbon suppliers.",
        "reduction_pct": 0.20,
        "cost_tier": "low",
        "payback_years": 2,
        "difficulty": "medium",
        "co_benefits": ["Supply chain resilience", "Innovation", "Stakeholder trust"],
        "applicable_when": lambda data, breakdown: breakdown.get("scope3_detail", {}).get("cat1_purchased_goods", 0) > 200,
    },
    {
        "id": "optimize_logistics",
        "scope": 3,
        "category": "Transportation",
        "title": "Optimize Logistics & Modal Shift",
        "description": "Shift freight from air/road to rail/sea. Consolidate shipments. Optimize routes.",
        "reduction_pct": 0.30,
        "cost_tier": "low",
        "payback_years": 1,
        "difficulty": "medium",
        "co_benefits": ["Lower shipping costs", "Fewer delays"],
        "applicable_when": lambda data, breakdown: breakdown.get("scope3_detail", {}).get("cat4_upstream_transport", 0) > 100,
    },
    {
        "id": "remote_work",
        "scope": 3,
        "category": "Employee Commuting",
        "title": "Expand Remote & Hybrid Work",
        "description": "Allow flexible remote work to reduce employee commuting emissions by 40-60%.",
        "reduction_pct": 0.50,
        "cost_tier": "low",
        "payback_years": 0,
        "difficulty": "low",
        "co_benefits": ["Employee satisfaction", "Reduced office costs", "Talent attraction"],
        "applicable_when": lambda data, breakdown: breakdown.get("scope3_detail", {}).get("cat7_commuting", 0) > 50,
    },
    {
        "id": "waste_reduction",
        "scope": 3,
        "category": "Waste",
        "title": "Zero Waste to Landfill Program",
        "description": "Implement waste reduction, recycling, and composting to divert waste from landfills.",
        "reduction_pct": 0.60,
        "cost_tier": "low",
        "payback_years": 2,
        "difficulty": "low",
        "co_benefits": ["Reduced disposal costs", "Resource recovery", "Regulatory compliance"],
        "applicable_when": lambda data, breakdown: breakdown.get("scope3_detail", {}).get("cat5_waste", 0) > 30,
    },
    {
        "id": "business_travel_policy",
        "scope": 3,
        "category": "Business Travel",
        "title": "Sustainable Travel Policy",
        "description": "Replace non-essential flights with video calls. Mandate rail for short-haul trips. Offset remaining flights.",
        "reduction_pct": 0.40,
        "cost_tier": "low",
        "payback_years": 0,
        "difficulty": "low",
        "co_benefits": ["Travel cost reduction", "Employee time savings"],
        "applicable_when": lambda data, breakdown: breakdown.get("scope3_detail", {}).get("cat6_business_travel", 0) > 50,
    },
]

# Cost tier to approximate annual cost per tCO2e reduced
_COST_PER_TCO2E: dict[str, dict[str, float]] = {
    "low":    {"min": 5,   "max": 30},
    "medium": {"min": 30,  "max": 100},
    "high":   {"min": 100, "max": 300},
}


def generate_recommendations(
    emissions: dict[str, float],
    breakdown: dict | None,
    industry: str,
    provided_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generate ranked reduction recommendations based on emission profile.

    Returns a sorted list of applicable strategies with estimated savings.
    """
    breakdown = breakdown or {}
    provided_data = provided_data or {}
    results: list[dict[str, Any]] = []

    scope_map = {1: emissions.get("scope1", 0), 2: emissions.get("scope2", 0), 3: emissions.get("scope3", 0)}

    for strategy in _STRATEGIES:
        # Check if strategy is applicable to this profile
        try:
            if not strategy["applicable_when"](provided_data, breakdown):
                continue
        except Exception:
            continue

        scope_val = scope_map.get(strategy["scope"], 0)
        if scope_val <= 0:
            continue

        # Estimate CO2 savings
        # Find the relevant category value from breakdown
        category_emission = _get_category_emission(strategy, breakdown)
        if category_emission <= 0:
            category_emission = scope_val * 0.3  # fallback: assume 30% of scope

        co2_reduction = round(category_emission * strategy["reduction_pct"], 1)
        cost_range = _COST_PER_TCO2E[strategy["cost_tier"]]
        annual_cost = {
            "min": round(co2_reduction * cost_range["min"]),
            "max": round(co2_reduction * cost_range["max"]),
        }

        # Calculate a priority score (higher = do first)
        # Factors: CO2 impact (50%), cost efficiency (30%), ease (20%)
        impact_score = min(co2_reduction / max(emissions.get("total", 1), 1), 1.0)
        cost_score = {"low": 1.0, "medium": 0.6, "high": 0.3}[strategy["cost_tier"]]
        ease_score = {"low": 1.0, "medium": 0.6, "high": 0.3}[strategy["difficulty"]]
        priority = round(impact_score * 0.5 + cost_score * 0.3 + ease_score * 0.2, 4)

        results.append({
            "id": strategy["id"],
            "scope": strategy["scope"],
            "category": strategy["category"],
            "title": strategy["title"],
            "description": strategy["description"],
            "co2_reduction_tco2e": co2_reduction,
            "reduction_percentage": round(strategy["reduction_pct"] * 100, 0),
            "annual_cost_usd": annual_cost,
            "cost_tier": strategy["cost_tier"],
            "payback_years": strategy["payback_years"],
            "difficulty": strategy["difficulty"],
            "co_benefits": strategy["co_benefits"],
            "priority_score": priority,
        })

    # Sort by priority (highest first)
    results.sort(key=lambda x: x["priority_score"], reverse=True)
    return results


def _get_category_emission(strategy: dict, breakdown: dict) -> float:
    """Extract the relevant emission value from breakdown for a strategy."""
    scope = strategy["scope"]
    detail_key = f"scope{scope}_detail"
    detail = breakdown.get(detail_key, {})

    if scope == 1:
        cat = strategy["category"]
        if "Mobile" in cat:
            return detail.get("mobile_combustion", 0)
        if "Stationary" in cat:
            return detail.get("stationary_combustion", 0) + detail.get("natural_gas", 0)
        if "Fugitive" in cat:
            return detail.get("fugitive_emissions", 0)
    elif scope == 2:
        return detail.get("location_based", 0)
    elif scope == 3:
        cat = strategy["category"]
        if "Purchased" in cat:
            return detail.get("cat1_purchased_goods", 0)
        if "Transport" in cat:
            return detail.get("cat4_upstream_transport", 0)
        if "Commut" in cat:
            return detail.get("cat7_commuting", 0)
        if "Waste" in cat:
            return detail.get("cat5_waste", 0)
        if "Travel" in cat:
            return detail.get("cat6_business_travel", 0)

    return 0.0


def summarize_reduction_potential(
    recommendations: list[dict[str, Any]],
    total_emissions: float,
) -> dict[str, Any]:
    """Summarize total reduction potential across all recommendations."""
    total_reduction = sum(r["co2_reduction_tco2e"] for r in recommendations)
    total_cost_min = sum(r["annual_cost_usd"]["min"] for r in recommendations)
    total_cost_max = sum(r["annual_cost_usd"]["max"] for r in recommendations)

    return {
        "total_reduction_tco2e": round(total_reduction, 1),
        "total_reduction_pct": round(total_reduction / max(total_emissions, 1) * 100, 1),
        "annual_cost_range_usd": {"min": total_cost_min, "max": total_cost_max},
        "recommendation_count": len(recommendations),
        "quick_wins": len([r for r in recommendations if r["difficulty"] == "low" and r["cost_tier"] == "low"]),
    }
