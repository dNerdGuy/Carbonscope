"""What-if scenario builder service.

Allows companies to model emission changes under hypothetical parameter
adjustments (e.g., switching to renewable energy, changing fleet, supplier swaps).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Company, EmissionReport, Scenario


# Parameter adjustment handlers — each takes baseline emissions + params → adjusted
def _apply_energy_switch(baseline: dict[str, float], params: dict[str, Any]) -> dict[str, float]:
    """Model switching a % of energy to renewables."""
    pct = min(max(params.get("renewable_pct", 0), 0), 100) / 100
    # Scope 2 drops proportionally to renewable %
    return {
        "scope1": baseline["scope1"],
        "scope2": round(baseline["scope2"] * (1 - pct), 2),
        "scope3": baseline["scope3"],
    }


def _apply_fleet_electrification(baseline: dict[str, float], params: dict[str, Any]) -> dict[str, float]:
    """Model electrifying a % of vehicle fleet."""
    pct = min(max(params.get("electrification_pct", 0), 0), 100) / 100
    # Scope 1 transport ~30% of total scope1 on average
    transport_share = params.get("transport_share", 0.3)
    reduction = baseline["scope1"] * transport_share * pct * 0.85  # EVs ~85% lower
    return {
        "scope1": round(baseline["scope1"] - reduction, 2),
        "scope2": round(baseline["scope2"] + reduction * 0.3, 2),  # extra electricity
        "scope3": baseline["scope3"],
    }


def _apply_supplier_change(baseline: dict[str, float], params: dict[str, Any]) -> dict[str, float]:
    """Model switching suppliers to lower-emission alternatives."""
    pct_reduction = min(max(params.get("scope3_reduction_pct", 0), 0), 100) / 100
    return {
        "scope1": baseline["scope1"],
        "scope2": baseline["scope2"],
        "scope3": round(baseline["scope3"] * (1 - pct_reduction), 2),
    }


def _apply_efficiency(baseline: dict[str, float], params: dict[str, Any]) -> dict[str, float]:
    """Model general operational efficiency improvements."""
    pct = min(max(params.get("efficiency_pct", 0), 0), 50) / 100
    return {
        "scope1": round(baseline["scope1"] * (1 - pct), 2),
        "scope2": round(baseline["scope2"] * (1 - pct), 2),
        "scope3": baseline["scope3"],
    }


_ADJUSTMENTS = {
    "energy_switch": _apply_energy_switch,
    "fleet_electrification": _apply_fleet_electrification,
    "supplier_change": _apply_supplier_change,
    "efficiency": _apply_efficiency,
}


def compute_scenario(
    baseline: dict[str, float],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Compute scenario results from baseline emissions and adjustment parameters.

    Parameters is a dict where keys are adjustment types and values are
    adjustment-specific params. Multiple adjustments are applied in sequence.
    """
    current = dict(baseline)

    adjustments_applied = []
    for adj_type, adj_params in parameters.items():
        handler = _ADJUSTMENTS.get(adj_type)
        if handler and isinstance(adj_params, dict):
            current = handler(current, adj_params)
            adjustments_applied.append(adj_type)

    total_baseline = baseline["scope1"] + baseline["scope2"] + baseline["scope3"]
    total_scenario = current["scope1"] + current["scope2"] + current["scope3"]
    reduction = total_baseline - total_scenario
    reduction_pct = (reduction / total_baseline * 100) if total_baseline > 0 else 0.0

    return {
        "baseline": baseline,
        "adjusted": current,
        "total_baseline": round(total_baseline, 2),
        "total_adjusted": round(total_scenario, 2),
        "total_reduction": round(reduction, 2),
        "reduction_pct": round(reduction_pct, 2),
        "adjustments_applied": adjustments_applied,
    }


async def run_scenario(
    db: AsyncSession,
    scenario_id: str,
    company_id: str,
) -> Scenario:
    """Compute a scenario using the linked base report emissions."""
    result = await db.execute(
        select(Scenario).where(
            Scenario.id == scenario_id,
            Scenario.company_id == company_id,
        )
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise ValueError("Scenario not found")

    # Get baseline emissions from the base report
    report_result = await db.execute(
        select(EmissionReport).where(
            EmissionReport.id == scenario.base_report_id,
            EmissionReport.company_id == company_id,
            EmissionReport.deleted_at.is_(None),
        )
    )
    report = report_result.scalar_one_or_none()
    if not report:
        raise ValueError("Base emission report not found")

    baseline = {
        "scope1": float(report.scope1),
        "scope2": float(report.scope2),
        "scope3": float(report.scope3),
    }

    scenario.results = compute_scenario(baseline, scenario.parameters or {})
    scenario.status = "computed"
    await db.commit()
    await db.refresh(scenario)
    return scenario
