"""Scope 2 — Indirect emissions from purchased energy.

Covers electricity (location-based and market-based methods),
purchased steam, heating, and cooling.
"""

from __future__ import annotations

from .loader import get_grid_factor, load_factors


def calc_location_based(kwh: float, region: str = "US") -> float:
    """Calculate Scope 2 emissions using the location-based method.

    Parameters
    ----------
    kwh:
        Electricity consumed in kWh.
    region:
        eGRID subregion code, US state abbreviation, ISO-2 country code,
        or regional key (e.g. ``"EU27"``).  Falls back to global average.

    Returns
    -------
    float
        Emissions in kgCO2e.
    """
    if kwh <= 0:
        return 0.0

    gco2e_per_kwh = get_grid_factor(region)
    return round(kwh * gco2e_per_kwh / 1000.0, 2)


def calc_market_based(
    kwh: float,
    region: str = "US",
    factor_override: float | None = None,
    rec_kwh: float = 0.0,
) -> float:
    """Calculate Scope 2 emissions using the market-based method.

    Parameters
    ----------
    kwh:
        Total electricity consumed in kWh.
    region:
        Used for the residual mix factor when no override is provided.
    factor_override:
        Supplier-specific emission factor in gCO2e/kWh.  If provided,
        this takes precedence over the regional grid average.
    rec_kwh:
        kWh covered by Renewable Energy Certificates (RECs) — these are
        treated as zero-emission.

    Returns
    -------
    float
        Emissions in kgCO2e.
    """
    if kwh <= 0:
        return 0.0

    chargeable_kwh = max(kwh - rec_kwh, 0.0)
    if chargeable_kwh == 0:
        return 0.0

    if factor_override is not None and factor_override >= 0:
        gco2e = factor_override
    else:
        gco2e = get_grid_factor(region)

    return round(chargeable_kwh * gco2e / 1000.0, 2)


def calc_steam_heating(energy_kwh: float, source_type: str = "natural_gas") -> float:
    """Estimate Scope 2 emissions from purchased steam / district heating.

    Uses a simple conversion from the heat source fuel type.

    Parameters
    ----------
    energy_kwh:
        Energy content of purchased steam/heat in kWh.
    source_type:
        Assumed fuel for the steam plant (``"natural_gas"`` or ``"coal"``).
    """
    if energy_kwh <= 0:
        return 0.0

    # Approximate emission factors for steam generation (kgCO2e per kWh-thermal)
    factors = {
        "natural_gas": 0.21,
        "coal": 0.36,
        "oil": 0.28,
    }
    factor = factors.get(source_type, 0.21)
    return round(energy_kwh * factor, 2)
