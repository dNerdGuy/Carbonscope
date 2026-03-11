"""Utility functions for unit conversions, GWP calculations, and data completeness scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── Unit conversion tables ──────────────────────────────────────────

VOLUME_CONVERSIONS: dict[str, float] = {
    # to liters
    "gallons_to_liters": 3.78541,
    "m3_to_liters": 1000.0,
    "barrels_to_liters": 158.987,
}

MASS_CONVERSIONS: dict[str, float] = {
    # to kg
    "tonnes_to_kg": 1000.0,
    "short_tons_to_kg": 907.185,
    "pounds_to_kg": 0.453592,
}

ENERGY_CONVERSIONS: dict[str, float] = {
    # to kWh
    "mwh_to_kwh": 1000.0,
    "therms_to_kwh": 29.3001,
    "mmbtu_to_kwh": 293.071,
    "gj_to_kwh": 277.778,
    "mj_to_kwh": 0.277778,
}

DISTANCE_CONVERSIONS: dict[str, float] = {
    # to km
    "miles_to_km": 1.60934,
    "nautical_miles_to_km": 1.852,
}


def convert_units(value: float, conversion: str) -> float:
    """Convert a value using a named conversion factor.

    >>> convert_units(100, "gallons_to_liters")
    378.541
    """
    all_conversions = {
        **VOLUME_CONVERSIONS,
        **MASS_CONVERSIONS,
        **ENERGY_CONVERSIONS,
        **DISTANCE_CONVERSIONS,
    }
    factor = all_conversions.get(conversion)
    if factor is None:
        raise ValueError(f"Unknown conversion: {conversion!r}. Available: {sorted(all_conversions)}")
    return value * factor


# ── GWP helpers ─────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "emission_factors"


def _load_gwp() -> dict[str, int]:
    path = _DATA_DIR / "gwp_ar6.json"
    with open(path) as f:
        data = json.load(f)
    return data["gwp_100yr"]


_GWP_CACHE: dict[str, int] | None = None


def get_gwp(gas: str) -> int:
    """Return the 100-year GWP value for a greenhouse gas (IPCC AR6)."""
    global _GWP_CACHE
    if _GWP_CACHE is None:
        _GWP_CACHE = _load_gwp()
    val = _GWP_CACHE.get(gas)
    if val is None:
        raise ValueError(f"Unknown gas: {gas!r}")
    return val


def to_co2e(co2_kg: float = 0.0, ch4_kg: float = 0.0, n2o_kg: float = 0.0) -> float:
    """Convert individual gas masses (kg) to kgCO2e using AR6 GWP values."""
    return co2_kg * 1 + ch4_kg * 27 + n2o_kg * 273


# ── Data completeness scoring ──────────────────────────────────────

# Maps data field names to their relative importance (weight) for computing
# confidence, by industry.  A field present in provided_data counts towards
# the weighted completeness score.

FIELD_WEIGHTS: dict[str, dict[str, float]] = {
    "manufacturing": {
        "fuel_use_liters": 0.15,
        "fuel_type": 0.05,
        "natural_gas_m3": 0.15,
        "electricity_kwh": 0.15,
        "employee_count": 0.05,
        "revenue_usd": 0.05,
        "supplier_spend_usd": 0.20,
        "shipping_ton_km": 0.10,
        "office_sqm": 0.02,
        "vehicle_km": 0.08,
    },
    "transportation": {
        "fuel_use_liters": 0.30,
        "fuel_type": 0.05,
        "electricity_kwh": 0.05,
        "employee_count": 0.05,
        "revenue_usd": 0.05,
        "vehicle_km": 0.20,
        "shipping_ton_km": 0.15,
        "supplier_spend_usd": 0.10,
        "natural_gas_m3": 0.03,
        "office_sqm": 0.02,
    },
    "technology": {
        "electricity_kwh": 0.20,
        "employee_count": 0.15,
        "revenue_usd": 0.10,
        "supplier_spend_usd": 0.15,
        "office_sqm": 0.10,
        "fuel_use_liters": 0.02,
        "natural_gas_m3": 0.03,
        "vehicle_km": 0.02,
        "shipping_ton_km": 0.03,
        "fuel_type": 0.02,
        "business_travel_usd": 0.18,
    },
    "retail": {
        "electricity_kwh": 0.20,
        "supplier_spend_usd": 0.25,
        "shipping_ton_km": 0.15,
        "employee_count": 0.05,
        "revenue_usd": 0.05,
        "fuel_use_liters": 0.05,
        "fuel_type": 0.03,
        "natural_gas_m3": 0.05,
        "office_sqm": 0.07,
        "vehicle_km": 0.10,
    },
}

# Fallback weights used when industry isn't in the table above.
_DEFAULT_WEIGHTS: dict[str, float] = {
    "fuel_use_liters": 0.15,
    "fuel_type": 0.05,
    "natural_gas_m3": 0.10,
    "electricity_kwh": 0.15,
    "employee_count": 0.08,
    "revenue_usd": 0.07,
    "supplier_spend_usd": 0.15,
    "shipping_ton_km": 0.10,
    "office_sqm": 0.05,
    "vehicle_km": 0.10,
}


def calc_data_completeness(provided_data: dict[str, Any], industry: str) -> float:
    """Return a 0.0–1.0 confidence score based on how much data was provided.

    Each recognized field in *provided_data* that has a non-None, non-zero
    value contributes its weight to the total.  The result is normalised so
    that 1.0 means every relevant field is present.
    """
    weights = FIELD_WEIGHTS.get(industry, _DEFAULT_WEIGHTS)
    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0

    earned = 0.0
    for field, weight in weights.items():
        val = provided_data.get(field)
        if val is not None and val != 0 and val != "":
            earned += weight

    return round(min(earned / total_weight, 1.0), 4)
