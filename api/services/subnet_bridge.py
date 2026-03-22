"""Bittensor subnet bridge — connects the platform API to the CarbonScope subnet.

Sends questionnaires to miners via Dendrite, collects responses, scores them,
applies consensus-based selection (median aggregation), and returns the result.
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
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
_bt_lock = threading.Lock()

# ── Per-miner circuit breakers ──────────────────────────────────────
_PER_MINER_FAILURE_THRESHOLD = 3   # consecutive failures per miner
_PER_MINER_RECOVERY_TIMEOUT = 120  # seconds before retrying a failed miner

# Global circuit breaker (fallback when all miners fail)
_GLOBAL_CB_FAILURE_THRESHOLD = 5
_GLOBAL_CB_RECOVERY_TIMEOUT = 60

_miner_cb: dict[int, dict] = {}  # uid -> {"failures": int, "opened_at": float}
_miner_cb_lock = threading.Lock()

_global_cb_failures: int = 0
_global_cb_opened_at: float = 0.0
_global_cb_lock = threading.Lock()


def _miner_cb_record_success(uid: int) -> None:
    with _miner_cb_lock:
        _miner_cb.pop(uid, None)


def _miner_cb_record_failure(uid: int) -> None:
    with _miner_cb_lock:
        state = _miner_cb.setdefault(uid, {"failures": 0, "opened_at": 0.0})
        state["failures"] += 1
        if state["failures"] >= _PER_MINER_FAILURE_THRESHOLD:
            state["opened_at"] = time.monotonic()
            logger.warning("Per-miner circuit breaker OPEN for miner %d", uid)


def _miner_cb_is_open(uid: int) -> bool:
    with _miner_cb_lock:
        state = _miner_cb.get(uid)
        if state is None:
            return False
        if state["failures"] < _PER_MINER_FAILURE_THRESHOLD:
            return False
        elapsed = time.monotonic() - state["opened_at"]
        if elapsed >= _PER_MINER_RECOVERY_TIMEOUT:
            return False  # half-open attempt
        return True


def _global_cb_record_success() -> None:
    global _global_cb_failures, _global_cb_opened_at
    with _global_cb_lock:
        _global_cb_failures = 0
        _global_cb_opened_at = 0.0


def _global_cb_record_failure() -> None:
    global _global_cb_failures, _global_cb_opened_at
    with _global_cb_lock:
        _global_cb_failures += 1
        if _global_cb_failures >= _GLOBAL_CB_FAILURE_THRESHOLD:
            _global_cb_opened_at = time.monotonic()
            logger.warning(
                "Global circuit breaker OPEN after %d consecutive failures; "
                "will retry in %ds",
                _global_cb_failures, _GLOBAL_CB_RECOVERY_TIMEOUT,
            )


def _global_cb_is_open() -> bool:
    with _global_cb_lock:
        if _global_cb_failures < _GLOBAL_CB_FAILURE_THRESHOLD:
            return False
        elapsed = time.monotonic() - _global_cb_opened_at
        if elapsed >= _GLOBAL_CB_RECOVERY_TIMEOUT:
            return False
        return True


def _init_bt() -> None:
    global _bt_inited, _dendrite, _subtensor, _metagraph, _wallet
    if _bt_inited:
        return

    with _bt_lock:
        # Double-checked locking
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
    """Send a questionnaire to subnet miners and return the consensus response.

    Returns a dict with keys: emissions, breakdown, confidence, sources,
    assumptions, methodology_version, miner_scores.

    Raises RuntimeError if the global circuit breaker is open or no valid
    responses are received.
    """
    if _global_cb_is_open():
        raise RuntimeError("Circuit breaker open — subnet temporarily unavailable")

    try:
        result = await _do_subnet_query(questionnaire, context, timeout)
        _global_cb_record_success()
        return result
    except RuntimeError:
        _global_cb_record_failure()
        raise


async def _do_subnet_query(
    questionnaire: dict[str, Any],
    context: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Internal: perform the actual subnet query with consensus scoring."""
    _init_bt()

    synapse = CarbonSynapse(
        questionnaire=questionnaire,
        context=context or {},
    )

    axons = _get_miner_axons()
    if not axons:
        raise RuntimeError("No active miners found on the subnet")

    # Filter out miners with open circuit breakers
    active_axons = []
    active_uids = []
    for uid_idx, axon in enumerate(axons):
        uid = uid_idx  # axon index maps to miner UID ordering
        if not _miner_cb_is_open(uid):
            active_axons.append(axon)
            active_uids.append(uid)

    if not active_axons:
        raise RuntimeError("All miners have open circuit breakers — subnet temporarily unavailable")

    from api.config import BT_QUERY_TIMEOUT
    responses: list[CarbonSynapse] = _dendrite.query(
        axons=active_axons,
        synapse=synapse,
        timeout=timeout or BT_QUERY_TIMEOUT,
    )

    # Score each response
    industry = questionnaire.get("industry", "manufacturing")
    valid_responses: list[tuple[int, CarbonSynapse, dict]] = []
    all_scores: dict[int, dict] = {}

    for uid, resp in zip(active_uids, responses):
        if not resp.is_success or resp.emissions is None:
            _miner_cb_record_failure(uid)
            continue

        # Skip error responses signalled by negative confidence
        if resp.confidence is not None and resp.confidence < 0:
            logger.info("Skipping miner %d: error response (confidence=%s)", uid, resp.confidence)
            _miner_cb_record_failure(uid)
            continue

        _miner_cb_record_success(uid)

        result = score_response(
            emissions=resp.emissions,
            breakdown=resp.breakdown,
            confidence=resp.confidence,
            sources=resp.sources,
            assumptions=resp.assumptions,
            questionnaire=questionnaire,
            industry=industry,
        )
        all_scores[uid] = result
        valid_responses.append((uid, resp, result))

    if not valid_responses:
        raise RuntimeError("No valid responses received from miners")

    # Consensus: if ≥3 valid responses, use median-based selection
    # Otherwise fall back to best-score selection
    if len(valid_responses) >= 3:
        selected = _select_by_consensus(valid_responses)
    else:
        selected = max(valid_responses, key=lambda x: x[2]["final"])

    _, best_response, best_score = selected
    selected_total = best_response.emissions.get("total", 0) if best_response.emissions else 0

    # Compute agreement_pct: fraction of valid miners within ±20% of the selected total
    if selected_total and len(valid_responses) > 1:
        tolerance = selected_total * 0.20
        agreeing = sum(
            1 for _, r, _ in valid_responses
            if abs((r.emissions or {}).get("total", 0) - selected_total) <= tolerance
        )
        agreement_pct = round(agreeing / len(valid_responses) * 100, 1)
    else:
        agreement_pct = 100.0

    return {
        "emissions": best_response.emissions,
        "breakdown": best_response.breakdown,
        "confidence": best_response.confidence,
        "sources": best_response.sources,
        "assumptions": best_response.assumptions,
        "methodology_version": best_response.methodology_version,
        "miner_scores": all_scores,
        "agreement_pct": agreement_pct,
    }


def _select_by_consensus(
    responses: list[tuple[int, CarbonSynapse, dict]],
) -> tuple[int, CarbonSynapse, dict]:
    """Select the response closest to the median emissions across all valid responses.

    **Algorithm overview:**

    1. **Median computation** — compute the median of the ``total`` emissions
       field across every valid response.  Using the median (rather than the
       mean) makes the selection robust against a small number of outlier miners
       that report fabricated or wildly incorrect values.

    2. **Quality filtering** — only responses with a composite quality score
       (``result["final"]``) of at least *0.3* are considered as candidates for
       selection.  This threshold rejects miners that produced technically valid
       JSON but scored poorly on accuracy, compliance, or completeness axes.
       If *all* miners fall below the threshold (e.g. a first-run cold-start),
       the filter is dropped and all responses become candidates, ensuring the
       function always returns something.

    3. **Proximity selection** — among the quality candidates, choose the
       response whose ``total`` emissions value is closest (by absolute
       distance) to the computed median.  This rewards miners whose answers
       align with the consensus view while still preferring higher-quality
       submissions over low-quality ones that happen to match the median.

    **Fallback chain:**
    * ``>= 3`` valid responses  →  ``_select_by_consensus`` (this function)
    * ``< 3`` valid responses   →  best-score selection (``max`` by
      ``result["final"]``) in the caller.
    * ``0`` valid responses     →  ``RuntimeError`` raised before this is
      called.

    **Return value:**
    A ``(uid, synapse, score_dict)`` triple for the winning miner.  The
    ``score_dict`` is the full dict returned by :func:`~carbonscope.scoring.score_response`
    and includes per-axis scores (``accuracy``, ``compliance``, ``completeness``,
    ``anti_hallucination``, ``benchmark``) plus the composite ``final`` score.

    The caller exposes ``miner_scores`` (all UID → score dicts) in the API
    response alongside ``agreement_pct`` (percentage of miners within ±20 % of
    the selected total) so downstream consumers can gauge consensus quality.
    """
    # Compute median total emissions
    totals = [r[1].emissions.get("total", 0) for r in responses]
    median_total = statistics.median(totals)

    # Filter to responses with quality score above threshold
    min_quality = 0.3
    quality_responses = [r for r in responses if r[2]["final"] >= min_quality]
    if not quality_responses:
        quality_responses = responses  # fallback if all below threshold

    # Select the response closest to median among quality candidates
    best = min(
        quality_responses,
        key=lambda r: abs(r[1].emissions.get("total", 0) - median_total),
    )
    return best


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
        vtype = data.get("vehicle_type", "heavy_truck_diesel")
        val = calc_mobile_combustion(vtype, distance_km=vkm)
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
