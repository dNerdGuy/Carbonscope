"""Composite scoring engine for the CarbonScope validator.

Combines accuracy, GHG compliance, completeness, anti-hallucination,
and benchmark alignment into a single 0.0–1.0 score.
"""

from __future__ import annotations

from carbonscope.validation.ghg_protocol import check_ghg_compliance
from carbonscope.validation.sanity_checks import run_sanity_checks
from carbonscope.validation.benchmark import check_benchmark_alignment

# ── Scoring weights (must sum to 1.0) ──────────────────────────────

W_ACCURACY = 0.40
W_COMPLIANCE = 0.25
W_COMPLETENESS = 0.15
W_ANTI_HALLUCINATION = 0.15
W_BENCHMARK = 0.05

assert round(W_ACCURACY + W_COMPLIANCE + W_COMPLETENESS + W_ANTI_HALLUCINATION + W_BENCHMARK, 10) == 1.0, \
    "Scoring weights must sum to 1.0"


# ── Individual scoring functions ────────────────────────────────────


def calc_accuracy_score(
    estimated: dict[str, float],
    ground_truth: dict[str, float],
) -> float:
    """Compare estimated emissions against ground truth using weighted MAPE.

    Weight by scope: S1=30%, S2=20%, S3=50% (reflecting estimation difficulty).
    Returns 0.0–1.0 (1.0 = perfect).
    """
    scope_weights = {"scope1": 0.30, "scope2": 0.20, "scope3": 0.50}
    weighted_error = 0.0
    total_weight = 0.0

    for scope, weight in scope_weights.items():
        est = estimated.get(scope, 0)
        gt = ground_truth.get(scope, 0)

        if gt > 0:
            ape = abs(est - gt) / gt
        elif est == 0:
            ape = 0.0  # both zero — perfect
        else:
            ape = 1.0  # estimated non-zero but truth is zero

        weighted_error += weight * min(ape, 1.0)
        total_weight += weight

    if total_weight == 0:
        return 0.5

    mape = weighted_error / total_weight
    return round(max(1.0 - mape, 0.0), 4)


def calc_completeness_score(
    emissions: dict | None,
    breakdown: dict | None,
    confidence: float | None,
    sources: list | None,
    assumptions: list | None,
) -> float:
    """Check that all expected output fields are present and reasonable.

    Returns 0.0–1.0.
    """
    score = 0.0
    total_checks = 5

    # 1. Emissions dict present with all keys
    if emissions and all(k in emissions for k in ("scope1", "scope2", "scope3", "total")):
        score += 1.0

    # 2. Breakdown present
    if breakdown and len(breakdown) > 0:
        score += 1.0

    # 3. Confidence provided and in range
    if confidence is not None and 0.0 <= confidence <= 1.0:
        score += 1.0

    # 4. Sources listed
    if sources and len(sources) > 0:
        score += 1.0

    # 5. Assumptions documented
    if assumptions and len(assumptions) > 0:
        score += 1.0

    return round(score / total_checks, 4)


# Overconfidence penalty thresholds
_CONFIDENCE_TRIGGER = 0.8        # minimum confidence to consider penalizing
_VERY_SPARSE_MAX_FIELDS = 3      # fields ≤ this with confidence > 0.9 → max penalty
_SPARSE_MAX_FIELDS = 5           # fields ≤ this with confidence ≥ 0.8 → moderate penalty
_PENALTY_SEVERE = 0.15           # penalty for very sparse + very confident
_PENALTY_MODERATE = 0.10         # penalty for sparse + confident


def calc_overconfidence_penalty(
    confidence: float | None,
    questionnaire: dict,
) -> float:
    """Penalize miners that report high confidence on sparse input data.

    The penalty discourages miners from returning inflated confidence scores
    when they have very little actual data to work with (~15 possible fields).

    Returns 0.0–0.15 (subtracted from the weighted final score).
    """
    if confidence is None or confidence < _CONFIDENCE_TRIGGER:
        return 0.0

    provided_data = questionnaire.get("provided_data", {})
    fields_provided = len(provided_data)

    if fields_provided <= _VERY_SPARSE_MAX_FIELDS and confidence > 0.9:
        return _PENALTY_SEVERE
    if fields_provided <= _SPARSE_MAX_FIELDS and confidence >= _CONFIDENCE_TRIGGER:
        return _PENALTY_MODERATE

    return 0.0


# ── Composite scorer ────────────────────────────────────────────────


def score_response(
    emissions: dict,
    breakdown: dict | None,
    confidence: float | None,
    sources: list | None,
    assumptions: list | None,
    questionnaire: dict,
    ground_truth: dict[str, float] | None = None,
    industry: str = "manufacturing",
) -> dict[str, float]:
    """Compute the full multi-dimensional score for a miner response.

    Parameters
    ----------
    emissions : dict
        ``{"scope1": float, "scope2": float, "scope3": float, "total": float}``
    breakdown : dict | None
        Category-level detail.
    confidence : float | None
        Miner-reported confidence.
    sources : list | None
        Data sources cited.
    assumptions : list | None
        Assumptions/audit trail.
    questionnaire : dict
        The original query questionnaire.
    ground_truth : dict | None
        If available, known-correct emissions for accuracy scoring.
    industry : str
        Sector key for benchmark comparison.

    Returns
    -------
    dict
        ``{"accuracy": float, "compliance": float, "completeness": float,
           "anti_hallucination": float, "benchmark": float, "final": float}``
    """
    # Accuracy
    if ground_truth is not None:
        accuracy = calc_accuracy_score(emissions, ground_truth)
    else:
        accuracy = 0.5  # Neutral when no ground truth

    # GHG compliance
    compliance = check_ghg_compliance(emissions, breakdown, questionnaire)

    # Completeness
    completeness = calc_completeness_score(emissions, breakdown, confidence, sources, assumptions)

    # Anti-hallucination
    anti_hallucination = run_sanity_checks(emissions, breakdown, confidence, questionnaire)

    # Benchmark alignment
    benchmark = check_benchmark_alignment(emissions, industry)

    # Weighted final
    final = (
        W_ACCURACY * accuracy
        + W_COMPLIANCE * compliance
        + W_COMPLETENESS * completeness
        + W_ANTI_HALLUCINATION * anti_hallucination
        + W_BENCHMARK * benchmark
    )
    
    # Penalties
    penalty = calc_overconfidence_penalty(confidence, questionnaire)
    final = max(0.0, final - penalty)

    return {
        "accuracy": round(accuracy, 4),
        "compliance": round(compliance, 4),
        "completeness": round(completeness, 4),
        "anti_hallucination": round(anti_hallucination, 4),
        "benchmark": round(benchmark, 4),
        "penalty": round(penalty, 4),
        "final": round(final, 4),
    }
