"""CarbonSynapse — the Bittensor protocol for carbon emission estimation.

Defines the request/response contract between validators (who send company
questionnaires) and miners (who return Scope 1/2/3 emission estimates).
"""

from __future__ import annotations

from typing import ClassVar, Optional

import bittensor as bt


class CarbonSynapse(bt.Synapse):
    """Bittensor Synapse for corporate carbon footprint estimation.

    **Validator → Miner (request):**
        ``questionnaire`` and ``context`` are populated by the validator.

    **Miner → Validator (response):**
        The miner fills ``emissions``, ``breakdown``, ``confidence``,
        ``data_completeness``, ``sources``, ``assumptions``, and
        ``methodology_version``.
    """

    # ── Request fields (validator fills these) ──────────────────────

    questionnaire: dict = {}
    """Company data.  Expected keys:

    - ``company`` (str): Company name / ID.
    - ``industry`` (str): Sector key — ``"manufacturing"``, ``"transportation"``,
      ``"technology"``, ``"retail"``, ``"energy"``, ``"financial_services"``,
      ``"construction"``, ``"food_beverage"``, ``"healthcare"``.
    - ``services_used`` (list[str]): Business activities.
    - ``provided_data`` (dict): Partial operational data:
        - ``fuel_use_liters`` (float)
        - ``fuel_type`` (str)
        - ``natural_gas_m3`` (float)
        - ``electricity_kwh`` (float)
        - ``vehicle_km`` (float)
        - ``employee_count`` (int)
        - ``revenue_usd`` (float)
        - ``supplier_spend_usd`` (float)
        - ``shipping_ton_km`` (float)
        - ``office_sqm`` (float)
        - ``business_travel_usd`` (float)
        - ``waste_kg`` (float)
        - ``refrigerant_type`` (str)
        - ``refrigerant_kg_leaked`` (float)
        - ``rec_kwh`` (float)
    - ``region`` (str): ISO-2 country code, US state, or eGRID subregion.
    - ``year`` (int): Reporting year.
    """

    context: dict = {}
    """Additional context.  Expected keys:

    - ``grid_factor_override`` (float | None): Supplier-specific gCO2e/kWh.
    - ``methodology`` (str): ``"ghg_protocol"`` (default).
    """

    # ── Response fields (miner fills these) ─────────────────────────

    emissions: Optional[dict] = None
    """Top-level emission totals in kgCO2e::

        {"scope1": float, "scope2": float, "scope3": float, "total": float}
    """

    breakdown: Optional[dict] = None
    """Category-level breakdown::

        {
            "scope1_detail": {"stationary_combustion": float, "mobile_combustion": float, ...},
            "scope2_detail": {"location_based": float, "market_based": float},
            "scope3_detail": {"cat1_purchased_goods": float, "cat4_upstream_transport": float, ...}
        }
    """

    confidence: Optional[float] = None
    """Data-completeness-based confidence score (0.0–1.0)."""

    data_completeness: Optional[float] = None
    """Fraction of expected data fields that were provided (0.0–1.0)."""

    sources: Optional[list] = None
    """List of data sources used (e.g. ``["EPA emission factors v2025", ...]``)."""

    assumptions: Optional[list] = None
    """Audit trail: list of assumptions made during estimation."""

    methodology_version: Optional[str] = None
    """Methodology identifier (e.g. ``"ghg_protocol_v2025"``)."""

    # ── Synapse config ──────────────────────────────────────────────

    required_hash_fields: ClassVar[tuple[str, ...]] = ("questionnaire",)
