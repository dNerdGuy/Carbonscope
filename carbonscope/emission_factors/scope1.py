"""Scope 1 — Direct emissions from owned/controlled sources.

Covers stationary combustion, mobile combustion, process emissions,
and fugitive emissions (refrigerant leaks).
"""

from __future__ import annotations

from .loader import load_factors, get_fuel_factor


# ── Stationary combustion ───────────────────────────────────────────


def calc_stationary_combustion(
    fuel_type: str,
    quantity: float,
    unit: str = "liters",
) -> float:
    """Calculate kgCO2e from stationary fuel combustion.

    Parameters
    ----------
    fuel_type:
        Key in epa_stationary_combustion.json ``fuels`` dict
        (e.g. ``"diesel"``, ``"natural_gas"``, ``"coal_anthracite"``).
    quantity:
        Amount of fuel consumed.
    unit:
        Unit of *quantity*.  Must match the dataset's native unit for the fuel
        (liters for liquid fuels, m3 for gas, kg for solids).  Conversion from
        other units should be done beforehand via :func:`carbonscope.utils.convert_units`.

    Returns
    -------
    float
        Emissions in kgCO2e.
    """
    if quantity <= 0:
        return 0.0

    fuels = load_factors("epa_stationary")["fuels"]
    fuel = fuels.get(fuel_type)
    if fuel is None:
        fuel = fuels["diesel"]

    factor = fuel["total_kgco2e_per_unit"]

    # Handle unit mismatch for natural gas (dataset native unit = m3)
    if fuel_type == "natural_gas" and unit == "therms":
        # 1 therm ≈ 2.83168 m³
        quantity = quantity * 2.83168
    elif fuel_type == "natural_gas" and unit == "kWh":
        # 1 kWh of natural gas ≈ 0.0949 m³
        quantity = quantity * 0.0949

    return round(quantity * factor, 2)


# ── Mobile combustion ───────────────────────────────────────────────


def calc_mobile_combustion(
    vehicle_type: str = "heavy_truck_diesel",
    distance_km: float = 0.0,
    fuel_liters: float = 0.0,
) -> float:
    """Calculate kgCO2e from mobile sources (company vehicles).

    Provide *either* ``distance_km`` or ``fuel_liters`` (not both unless you
    want fuel to take priority).

    Parameters
    ----------
    vehicle_type:
        Key in epa_mobile_combustion.json ``vehicle_types`` dict.
    distance_km:
        Distance driven in km.
    fuel_liters:
        Fuel consumed in litres (overrides distance-based calc).
    """
    mobile = load_factors("epa_mobile")

    if fuel_liters > 0:
        # Convert fuel directly using stationary factors for the fuel type
        vt = mobile["vehicle_types"].get(vehicle_type, {})
        fuel_type = vt.get("fuel_type", "diesel")
        return calc_stationary_combustion(fuel_type, fuel_liters, "liters")

    if distance_km > 0:
        vt = mobile["vehicle_types"].get(vehicle_type)
        if vt is None:
            vt = mobile["vehicle_types"]["heavy_truck_diesel"]
        return round(distance_km * vt["kgco2e_per_km"], 2)

    return 0.0


# ── Fugitive emissions ──────────────────────────────────────────────


def calc_fugitive_emissions(
    refrigerant_type: str,
    kg_leaked: float,
) -> float:
    """Calculate kgCO2e from refrigerant leaks.

    Parameters
    ----------
    refrigerant_type:
        Key in gwp_ar6.json ``common_refrigerants`` dict
        (e.g. ``"R_134a"``, ``"R_410A"``), or a gas name like ``"HFC_134a"``.
    kg_leaked:
        Mass of refrigerant leaked in kg.
    """
    if kg_leaked <= 0:
        return 0.0

    gwp_data = load_factors("gwp")

    # Try common refrigerants first
    ref = gwp_data["common_refrigerants"].get(refrigerant_type)
    if ref is not None:
        return round(kg_leaked * ref["gwp"], 2)

    # Fall back to raw GWP table
    gwp_val = gwp_data["gwp_100yr"].get(refrigerant_type)
    if gwp_val is not None:
        return round(kg_leaked * gwp_val, 2)

    # Unknown refrigerant — use HFC-134a as conservative default
    return round(kg_leaked * 1530, 2)
