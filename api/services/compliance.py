"""Automated compliance reporting service.

Generates structured reports aligned with major frameworks:
- GHG Protocol Corporate Standard inventory
- CDP Climate Change Questionnaire (key modules)
- TCFD recommended disclosures
- SBTi baseline and target pathway
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def generate_ghg_inventory(
    company_name: str,
    industry: str,
    region: str,
    year: int,
    scope1: float,
    scope2: float,
    scope3: float,
    total: float,
    breakdown: dict | None,
    sources: list | None,
    assumptions: list | None,
    confidence: float,
) -> dict[str, Any]:
    """Generate a GHG Protocol Corporate Standard inventory report."""
    breakdown = breakdown or {}

    s1_detail = breakdown.get("scope1_detail", {})
    s2_detail = breakdown.get("scope2_detail", {})
    s3_detail = breakdown.get("scope3_detail", {})

    return {
        "framework": "GHG Protocol Corporate Standard",
        "version": "Revised Edition (2004, updated 2015)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reporting_period": f"{year}-01-01 to {year}-12-31",
        "organization": {
            "name": company_name,
            "industry_sector": industry,
            "region": region,
        },
        "organizational_boundary": {
            "approach": "Operational Control",
            "description": f"{company_name} reports GHG emissions from all operations under its operational control.",
        },
        "emissions_summary": {
            "total_tco2e": total,
            "scope1_tco2e": scope1,
            "scope2_location_tco2e": s2_detail.get("location_based", scope2),
            "scope2_market_tco2e": s2_detail.get("market_based", scope2),
            "scope3_tco2e": scope3,
            "unit": "metric tonnes of CO2 equivalent (tCO2e)",
            "gwp_source": "IPCC AR6",
            "gases_included": ["CO2", "CH4", "N2O", "HFCs"],
        },
        "scope1_detail": {
            "stationary_combustion": s1_detail.get("stationary_combustion", 0) + s1_detail.get("natural_gas", 0),
            "mobile_combustion": s1_detail.get("mobile_combustion", 0),
            "fugitive_emissions": s1_detail.get("fugitive_emissions", 0),
            "process_emissions": 0,
        },
        "scope2_detail": {
            "location_based_method": s2_detail.get("location_based", scope2),
            "market_based_method": s2_detail.get("market_based", scope2),
            "grid_region": region,
        },
        "scope3_categories": _build_scope3_categories(s3_detail),
        "data_quality": {
            "confidence_score": confidence,
            "data_sources": sources or [],
            "assumptions": assumptions or [],
            "verification_status": "Self-assessed" if confidence < 0.8 else "Ready for third-party verification",
        },
        "methodology_notes": [
            "Emission factors sourced from EPA, eGRID, IEA, and DEFRA databases.",
            "Scope 3 categories without primary data estimated using industry benchmarks.",
            "GWP values from IPCC Sixth Assessment Report (AR6).",
        ],
    }


def _build_scope3_categories(s3_detail: dict) -> list[dict[str, Any]]:
    """Map internal Scope 3 details to GHG Protocol's 15 categories."""
    cat_map = [
        (1, "Purchased goods and services", "cat1_purchased_goods"),
        (2, "Capital goods", "cat2_capital_goods"),
        (3, "Fuel- and energy-related activities", "cat3_fuel_energy"),
        (4, "Upstream transportation and distribution", "cat4_upstream_transport"),
        (5, "Waste generated in operations", "cat5_waste"),
        (6, "Business travel", "cat6_business_travel"),
        (7, "Employee commuting", "cat7_commuting"),
        (8, "Upstream leased assets", "cat8_leased_assets"),
        (9, "Downstream transportation and distribution", "cat9_downstream_transport"),
        (10, "Processing of sold products", "cat10_processing"),
        (11, "Use of sold products", "cat11_use_products"),
        (12, "End-of-life treatment of sold products", "cat12_end_of_life"),
        (13, "Downstream leased assets", "cat13_downstream_leased"),
        (14, "Franchises", "cat14_franchises"),
        (15, "Investments", "cat15_investments"),
    ]

    categories = []
    for num, name, key in cat_map:
        value = s3_detail.get(key, 0)
        method = "Activity-based" if value > 0 and key in s3_detail else "Not estimated"
        if key not in s3_detail and value > 0:
            method = "Industry-default"

        # Check default-filled keys
        default_keys = {k for k in s3_detail if k.startswith("cat") and k not in
                       ["cat1_purchased_goods", "cat4_upstream_transport", "cat5_waste",
                        "cat6_business_travel", "cat7_commuting"]}
        if key in default_keys:
            method = "Industry-default"

        categories.append({
            "category_number": num,
            "category_name": name,
            "tco2e": round(value, 2),
            "method": method,
            "relevant": value > 0,
        })

    return categories


def generate_cdp_responses(
    company_name: str,
    industry: str,
    year: int,
    scope1: float,
    scope2: float,
    scope3: float,
    total: float,
    breakdown: dict | None,
    confidence: float,
) -> dict[str, Any]:
    """Generate key CDP Climate Change questionnaire responses."""
    s2_detail = (breakdown or {}).get("scope2_detail", {})

    return {
        "framework": "CDP Climate Change Questionnaire",
        "reporting_year": year,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "modules": {
            "C0_introduction": {
                "C0.1": company_name,
                "C0.2": f"Reporting period: {year}-01-01 to {year}-12-31",
                "C0.3": "Operational control",
            },
            "C1_governance": {
                "C1.1": "Yes — Board-level oversight of climate-related issues",
                "C1.2": "Climate risk is integrated into overall risk management",
            },
            "C4_targets": {
                "C4.1": "Absolute emissions reduction target",
                "C4.1a": {
                    "base_year": year,
                    "base_year_emissions": total,
                    "target_year": year + 5,
                    "target_reduction_pct": 30,
                    "target_emissions": round(total * 0.7, 2),
                },
            },
            "C6_emissions": {
                "C6.1_scope1": scope1,
                "C6.3_scope2_location": s2_detail.get("location_based", scope2),
                "C6.3_scope2_market": s2_detail.get("market_based", scope2),
                "C6.5_scope3": scope3,
                "C6.10_methodology": "GHG Protocol Corporate Standard",
                "C6.10_gwp_source": "IPCC AR6",
            },
            "C7_emissions_breakdown": {
                "by_scope": {
                    "scope1_pct": round(scope1 / max(total, 1) * 100, 1),
                    "scope2_pct": round(scope2 / max(total, 1) * 100, 1),
                    "scope3_pct": round(scope3 / max(total, 1) * 100, 1),
                },
            },
        },
    }


def generate_tcfd_disclosure(
    company_name: str,
    industry: str,
    year: int,
    scope1: float,
    scope2: float,
    scope3: float,
    total: float,
    recommendations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate TCFD-aligned disclosure framework."""
    return {
        "framework": "Task Force on Climate-related Financial Disclosures (TCFD)",
        "reporting_year": year,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pillars": {
            "governance": {
                "description": "Board oversight and management role in climate-related risks and opportunities.",
                "board_oversight": "The Board receives quarterly updates on climate-related performance and risks.",
                "management_role": "A dedicated sustainability team monitors emissions and implements reduction strategies.",
            },
            "strategy": {
                "description": "Climate-related risks and opportunities impact on strategy and financial planning.",
                "risks": [
                    {
                        "type": "Transition",
                        "risk": "Carbon pricing / emissions trading",
                        "impact": "Potential cost increase of $10-50 per tCO2e on Scope 1 emissions",
                        "time_horizon": "Medium-term (2-5 years)",
                    },
                    {
                        "type": "Physical",
                        "risk": "Extreme weather events disrupting operations",
                        "impact": "Supply chain disruptions, facility damage",
                        "time_horizon": "Long-term (5+ years)",
                    },
                ],
                "opportunities": [
                    {
                        "type": "Resource efficiency",
                        "description": "Energy efficiency improvements reducing costs",
                        "financial_impact": "Potential 10-25% reduction in energy costs",
                    },
                    {
                        "type": "Market",
                        "description": "Growing demand for low-carbon products and services",
                        "financial_impact": "Revenue growth from sustainable offerings",
                    },
                ],
            },
            "risk_management": {
                "description": "Processes for identifying, assessing, and managing climate risks.",
                "process": "Climate risk assessment integrated into enterprise risk management framework.",
                "integration": "Climate metrics included in operational KPIs and investment decisions.",
            },
            "metrics_and_targets": {
                "emissions": {
                    "scope1_tco2e": scope1,
                    "scope2_tco2e": scope2,
                    "scope3_tco2e": scope3,
                    "total_tco2e": total,
                },
                "intensity_metrics": {
                    "note": "Revenue-normalized and employee-normalized intensities available via dashboard.",
                },
                "targets": {
                    "short_term": f"Reduce absolute emissions 15% by {year + 3}",
                    "medium_term": f"Reduce absolute emissions 30% by {year + 5}",
                    "long_term": f"Achieve net-zero by {year + 25}",
                    "science_based": "Aligned with 1.5°C pathway (SBTi)",
                },
                "key_reduction_strategies": [
                    r["title"] for r in (recommendations or [])[:5]
                ],
            },
        },
    }


def generate_sbti_pathway(
    company_name: str,
    year: int,
    scope1: float,
    scope2: float,
    scope3: float,
    total: float,
) -> dict[str, Any]:
    """Generate SBTi-aligned baseline and target pathway."""
    # SBTi requires 4.2% annual reduction for 1.5°C pathway (Scope 1+2)
    # and 2.5% for well-below 2°C (Scope 3)
    s12 = scope1 + scope2
    target_years = list(range(year, year + 11))
    s12_annual_reduction = 0.042
    s3_annual_reduction = 0.025

    pathway = []
    for i, y in enumerate(target_years):
        s12_projected = s12 * ((1 - s12_annual_reduction) ** i)
        s3_projected = scope3 * ((1 - s3_annual_reduction) ** i)
        pathway.append({
            "year": y,
            "scope1_2_tco2e": round(s12_projected, 1),
            "scope3_tco2e": round(s3_projected, 1),
            "total_tco2e": round(s12_projected + s3_projected, 1),
        })

    return {
        "framework": "Science Based Targets initiative (SBTi)",
        "base_year": year,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline": {
            "scope1_tco2e": scope1,
            "scope2_tco2e": scope2,
            "scope3_tco2e": scope3,
            "total_tco2e": total,
        },
        "target": {
            "ambition": "1.5°C aligned",
            "scope1_2_annual_reduction_pct": s12_annual_reduction * 100,
            "scope3_annual_reduction_pct": s3_annual_reduction * 100,
            "target_year": year + 10,
            "scope1_2_target_tco2e": round(s12 * ((1 - s12_annual_reduction) ** 10), 1),
            "scope3_target_tco2e": round(scope3 * ((1 - s3_annual_reduction) ** 10), 1),
        },
        "pathway": pathway,
        "notes": [
            "Scope 1+2: 4.2% annual absolute reduction (1.5°C pathway, SBTi corporate manual v2.1).",
            "Scope 3: 2.5% annual absolute reduction (SBTi Scope 3 minimum ambition).",
            "Pathway assumes linear year-over-year reductions from the base year.",
        ],
    }
