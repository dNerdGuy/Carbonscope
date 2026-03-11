"""Bittensor subnet bridge — connects the platform API to the CarbonScope subnet.

Sends questionnaires to miners via Dendrite, collects responses, picks the
best-scoring result, and returns it.
"""

from __future__ import annotations

import logging
from typing import Any

from carbonscope.protocol import CarbonSynapse
from carbonscope.scoring import score_response

logger = logging.getLogger(__name__)

# ── Lazy-initialised Bittensor objects ──────────────────────────────
# Imported at first call to avoid import-time bittensor overhead in tests.

_bt_inited = False
_dendrite = None
_subtensor = None
_metagraph = None
_wallet = None


def _init_bt() -> None:
    global _bt_inited, _dendrite, _subtensor, _metagraph, _wallet
    if _bt_inited:
        return

    import bittensor as bt
    from api.config import BT_NETUID, BT_NETWORK, BT_WALLET_HOTKEY, BT_WALLET_NAME

    _wallet = bt.Wallet(name=BT_WALLET_NAME, hotkey=BT_WALLET_HOTKEY)
    _subtensor = bt.Subtensor(network=BT_NETWORK)
    _metagraph = bt.Metagraph(netuid=BT_NETUID, network=BT_NETWORK)
    _dendrite = bt.Dendrite(wallet=_wallet)
    _bt_inited = True
    logger.info("Bittensor bridge initialised (network=%s, netuid=%s)", BT_NETWORK, BT_NETUID)


def _get_miner_axons() -> list:
    """Return axon endpoints for all active miners."""
    _init_bt()
    _metagraph.sync(subtensor=_subtensor)
    return [
        _metagraph.axons[uid]
        for uid in range(_metagraph.n)
        if not _metagraph.validator_permit[uid] and _metagraph.active[uid]
    ]


# ── Public API ──────────────────────────────────────────────────────


async def estimate_emissions(
    questionnaire: dict[str, Any],
    context: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Send a questionnaire to subnet miners and return the best response.

    Returns a dict with keys: emissions, breakdown, confidence, sources,
    assumptions, methodology_version, miner_scores.
    """
    _init_bt()

    synapse = CarbonSynapse(
        questionnaire=questionnaire,
        context=context or {},
    )

    axons = _get_miner_axons()
    if not axons:
        raise RuntimeError("No active miners found on the subnet")

    from api.config import BT_QUERY_TIMEOUT
    responses: list[CarbonSynapse] = _dendrite.query(
        axons=axons,
        synapse=synapse,
        timeout=timeout or BT_QUERY_TIMEOUT,
    )

    # Score each response and pick the best
    industry = questionnaire.get("industry", "manufacturing")
    best_score = -1.0
    best_response: CarbonSynapse | None = None
    all_scores: dict[int, dict] = {}

    for idx, resp in enumerate(responses):
        if not resp.is_success or resp.emissions is None:
            continue

        result = score_response(
            emissions=resp.emissions,
            breakdown=resp.breakdown,
            confidence=resp.confidence,
            sources=resp.sources,
            assumptions=resp.assumptions,
            questionnaire=questionnaire,
            industry=industry,
        )
        all_scores[idx] = result

        if result["final"] > best_score:
            best_score = result["final"]
            best_response = resp

    if best_response is None:
        raise RuntimeError("No valid responses received from miners")

    return {
        "emissions": best_response.emissions,
        "breakdown": best_response.breakdown,
        "confidence": best_response.confidence,
        "sources": best_response.sources,
        "assumptions": best_response.assumptions,
        "methodology_version": best_response.methodology_version,
        "miner_scores": all_scores,
    }


def estimate_emissions_local(
    questionnaire: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the emission estimation locally (without Bittensor network).

    Uses the miner's forward logic directly — useful for development/testing.
    """
    from carbonscope.emission_factors.scope1 import (
        calc_stationary_combustion,
        calc_mobile_combustion,
        calc_fugitive_emissions,
    )
    from carbonscope.emission_factors.scope2 import calc_location_based, calc_market_based
    from carbonscope.emission_factors.scope3 import (
        calc_cat1_purchased_goods,
        calc_cat4_transport,
        calc_cat5_waste,
        calc_cat6_business_travel,
        calc_cat7_commuting,
        fill_industry_defaults,
    )
    from carbonscope.utils import calc_data_completeness

    data = questionnaire.get("provided_data", {})
    industry = questionnaire.get("industry", "manufacturing")
    region = questionnaire.get("region", "US")
    ctx = context or {}

    # Scope 1
    s1 = 0.0
    s1_detail: dict[str, float] = {}

    fuel = data.get("fuel_use_liters") or 0
    fuel_type = data.get("fuel_type", "diesel")
    if fuel > 0:
        val = calc_stationary_combustion(fuel_type, fuel, "liters")
        s1 += val
        s1_detail["stationary_combustion"] = val

    ng = data.get("natural_gas_m3") or 0
    if ng > 0:
        val = calc_stationary_combustion("natural_gas", ng, "m3")
        s1 += val
        s1_detail["natural_gas"] = val

    vkm = data.get("vehicle_km") or 0
    if vkm > 0:
        val = calc_mobile_combustion("heavy_truck_diesel", distance_km=vkm)
        s1 += val
        s1_detail["mobile_combustion"] = val

    ref_type = data.get("refrigerant_type")
    ref_kg = data.get("refrigerant_kg_leaked") or 0
    if ref_type and ref_kg > 0:
        val = calc_fugitive_emissions(ref_type, ref_kg)
        s1 += val
        s1_detail["fugitive_emissions"] = val

    # Scope 2
    elec = data.get("electricity_kwh") or 0
    factor_override = ctx.get("grid_factor_override")
    rec_kwh = data.get("rec_kwh") or 0

    s2_loc = calc_location_based(elec, region) if elec > 0 else 0.0
    s2_mkt = calc_market_based(elec, region, factor_override, rec_kwh) if elec > 0 else 0.0
    s2 = s2_loc
    s2_detail = {"location_based": s2_loc, "market_based": s2_mkt}

    # Scope 3
    s3_detail: dict[str, float] = {}

    spend = data.get("supplier_spend_usd") or 0
    if spend > 0:
        s3_detail["cat1_purchased_goods"] = calc_cat1_purchased_goods(spend, industry)

    tkm = data.get("shipping_ton_km") or 0
    if tkm > 0:
        s3_detail["cat4_upstream_transport"] = calc_cat4_transport(tkm, "road")

    waste = data.get("waste_kg") or 0
    if waste > 0:
        s3_detail["cat5_waste"] = calc_cat5_waste(waste)

    travel = data.get("business_travel_usd") or 0
    emps = data.get("employee_count") or 0
    if travel > 0 or emps > 0:
        s3_detail["cat6_business_travel"] = calc_cat6_business_travel(emps, industry, travel)
    if emps > 0:
        s3_detail["cat7_commuting"] = calc_cat7_commuting(emps, region)

    s3_detail = fill_industry_defaults(s3_detail, industry, data)
    s3 = sum(s3_detail.values())

    confidence = calc_data_completeness(data, industry)
    total = round(s1 + s2 + s3, 2)

    assumptions = []
    if ng == 0 and fuel == 0 and vkm == 0:
        assumptions.append("No direct fuel/vehicle data — Scope 1 is zero or estimated from defaults")
    if elec == 0:
        assumptions.append("No electricity data — Scope 2 is zero")
    if spend == 0:
        assumptions.append("No supplier spend data — Scope 3 Cat 1 estimated from industry defaults")

    return {
        "emissions": {
            "scope1": round(s1, 2),
            "scope2": round(s2, 2),
            "scope3": round(s3, 2),
            "total": total,
        },
        "breakdown": {
            "scope1_detail": s1_detail,
            "scope2_detail": s2_detail,
            "scope3_detail": s3_detail,
        },
        "confidence": round(confidence, 4),
        "sources": [
            "EPA Emission Factors",
            "eGRID / IEA Grid Factors",
            "Industry Averages Database",
        ],
        "assumptions": assumptions,
        "methodology_version": "ghg_protocol_v2025",
        "miner_scores": None,
    }
