"""GHG Protocol compliance checker.

Validates that a miner's response follows GHG Protocol Corporate Standard
rules for scope classification, gas inclusion, and arithmetic consistency.
"""

from __future__ import annotations

from typing import Any


def check_ghg_compliance(response_emissions: dict, response_breakdown: dict | None, questionnaire: dict) -> float:
    """Return a 0.0–1.0 compliance score.

    Checks:
    1. Arithmetic: total ≈ scope1 + scope2 + scope3 (within 1%).
    2. Non-negative scopes.
    3. Scope classification correctness (fuel → S1, electricity → S2).
    4. Required fields present.
    """
    score = 1.0
    penalties: list[str] = []

    s1 = response_emissions.get("scope1", 0)
    s2 = response_emissions.get("scope2", 0)
    s3 = response_emissions.get("scope3", 0)
    total = response_emissions.get("total", 0)

    # 1. Arithmetic consistency
    expected_total = s1 + s2 + s3
    if expected_total > 0:
        diff = abs(total - expected_total) / expected_total
        if diff > 0.01:
            score -= 0.25
            penalties.append(f"Total mismatch: {total} vs expected {expected_total}")

    # 2. Non-negative scopes
    for scope_name, val in [("scope1", s1), ("scope2", s2), ("scope3", s3), ("total", total)]:
        if val < 0:
            score -= 0.20
            penalties.append(f"Negative {scope_name}: {val}")

    # 3. Scope classification checks
    provided_data = questionnaire.get("provided_data", {})

    # If fuel data given, Scope 1 should be > 0
    has_fuel = (provided_data.get("fuel_use_liters") or 0) > 0 or (provided_data.get("natural_gas_m3") or 0) > 0
    if has_fuel and s1 == 0:
        score -= 0.15
        penalties.append("Fuel data provided but Scope 1 is zero")

    # If electricity data given, Scope 2 should be > 0
    has_electricity = (provided_data.get("electricity_kwh") or 0) > 0
    if has_electricity and s2 == 0:
        score -= 0.15
        penalties.append("Electricity data provided but Scope 2 is zero")

    # 4. Breakdown provided when emissions > 0
    if response_breakdown is None and total > 0:
        score -= 0.10
        penalties.append("No breakdown provided despite non-zero emissions")

    return max(score, 0.0)
