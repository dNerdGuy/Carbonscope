"""Industry benchmark alignment checker.

Compares a miner's scope-split proportions against known industry averages.
Large deviations suggest the miner's methodology is flawed.
"""

from __future__ import annotations

from carbonscope.emission_factors.loader import get_industry_profile


def check_benchmark_alignment(emissions: dict, industry: str) -> float:
    """Return a 0.0–1.0 benchmark alignment score.

    Compares the scope 1/2/3 proportions of the response against the
    industry's typical split.  Deviations beyond a tolerance threshold
    reduce the score.
    """
    s1 = emissions.get("scope1", 0)
    s2 = emissions.get("scope2", 0)
    s3 = emissions.get("scope3", 0)
    total = s1 + s2 + s3

    if total <= 0:
        return 0.5  # Can't evaluate — neutral

    actual_pcts = {
        "scope1_pct": s1 / total,
        "scope2_pct": s2 / total,
        "scope3_pct": s3 / total,
    }

    profile = get_industry_profile(industry)
    expected = profile.get("typical_scope_split", {})

    if not expected:
        return 0.5

    # Tolerance: 25 percentage points deviation per scope before penalty
    tolerance = 0.25
    score = 1.0

    for key in ["scope1_pct", "scope2_pct", "scope3_pct"]:
        actual = actual_pcts.get(key, 0)
        exp = expected.get(key, 0)
        deviation = abs(actual - exp)
        if deviation > tolerance:
            # Proportional penalty for excess deviation
            excess = deviation - tolerance
            penalty = min(excess / 0.5, 1.0) * 0.33  # max ~0.33 penalty per scope
            score -= penalty

    return max(score, 0.0)
