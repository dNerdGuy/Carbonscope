"""Tests for the scoring engine and validation modules."""

import pytest

from carbonscope.scoring import (
    calc_accuracy_score,
    calc_completeness_score,
    score_response,
    W_ACCURACY,
    W_COMPLIANCE,
    W_COMPLETENESS,
    W_ANTI_HALLUCINATION,
    W_BENCHMARK,
)
from carbonscope.validation.ghg_protocol import check_ghg_compliance
from carbonscope.validation.sanity_checks import run_sanity_checks
from carbonscope.validation.benchmark import check_benchmark_alignment


# ── Accuracy scoring ────────────────────────────────────────────────


class TestAccuracyScore:
    def test_perfect_match(self):
        e = {"scope1": 100, "scope2": 200, "scope3": 300}
        gt = {"scope1": 100, "scope2": 200, "scope3": 300}
        assert calc_accuracy_score(e, gt) == 1.0

    def test_complete_mismatch(self):
        e = {"scope1": 0, "scope2": 0, "scope3": 0}
        gt = {"scope1": 100, "scope2": 200, "scope3": 300}
        assert calc_accuracy_score(e, gt) == 0.0

    def test_partial_accuracy(self):
        e = {"scope1": 80, "scope2": 200, "scope3": 250}
        gt = {"scope1": 100, "scope2": 200, "scope3": 300}
        score = calc_accuracy_score(e, gt)
        assert 0.5 < score < 1.0

    def test_both_zero_is_perfect(self):
        e = {"scope1": 0, "scope2": 0, "scope3": 0}
        gt = {"scope1": 0, "scope2": 0, "scope3": 0}
        assert calc_accuracy_score(e, gt) == 1.0


# ── Completeness scoring ───────────────────────────────────────────


class TestCompletenessScore:
    def test_all_fields_present(self):
        score = calc_completeness_score(
            emissions={"scope1": 1, "scope2": 2, "scope3": 3, "total": 6},
            breakdown={"scope1_detail": {}},
            confidence=0.8,
            sources=["EPA"],
            assumptions=["Used defaults for X"],
        )
        assert score == 1.0

    def test_no_fields(self):
        score = calc_completeness_score(None, None, None, None, None)
        assert score == 0.0

    def test_partial_fields(self):
        score = calc_completeness_score(
            emissions={"scope1": 1, "scope2": 2, "scope3": 3, "total": 6},
            breakdown=None,
            confidence=0.5,
            sources=None,
            assumptions=None,
        )
        assert 0.0 < score < 1.0


# ── GHG compliance ──────────────────────────────────────────────────


class TestGHGCompliance:
    def test_valid_response(self):
        emissions = {"scope1": 100, "scope2": 200, "scope3": 300, "total": 600}
        breakdown = {"scope1_detail": {"fuel": 100}}
        q = {"provided_data": {"fuel_use_liters": 100, "electricity_kwh": 5000}}
        score = check_ghg_compliance(emissions, breakdown, q)
        assert score == 1.0

    def test_total_mismatch_penalised(self):
        emissions = {"scope1": 100, "scope2": 200, "scope3": 300, "total": 999}
        score = check_ghg_compliance(emissions, {}, {"provided_data": {}})
        assert score < 1.0

    def test_negative_scope_penalised(self):
        emissions = {"scope1": -10, "scope2": 200, "scope3": 300, "total": 490}
        score = check_ghg_compliance(emissions, {}, {"provided_data": {}})
        assert score < 1.0

    def test_fuel_present_but_scope1_zero(self):
        emissions = {"scope1": 0, "scope2": 200, "scope3": 300, "total": 500}
        q = {"provided_data": {"fuel_use_liters": 1000}}
        score = check_ghg_compliance(emissions, {}, q)
        assert score < 1.0

    def test_electricity_present_but_scope2_zero(self):
        emissions = {"scope1": 100, "scope2": 0, "scope3": 300, "total": 400}
        q = {"provided_data": {"electricity_kwh": 50000}}
        score = check_ghg_compliance(emissions, {}, q)
        assert score < 1.0


# ── Sanity checks ──────────────────────────────────────────────────


class TestSanityChecks:
    def test_sane_response(self):
        emissions = {"scope1": 500, "scope2": 1000, "scope3": 3000, "total": 4500}
        q = {
            "industry": "manufacturing",
            "provided_data": {
                "fuel_use_liters": 200,
                "electricity_kwh": 5000,
                "employee_count": 50,
            },
        }
        score = run_sanity_checks(emissions, None, 0.6, q)
        assert score >= 0.8

    def test_negative_emissions_penalised(self):
        emissions = {"scope1": -100, "scope2": 200, "scope3": 300, "total": 400}
        q = {"industry": "manufacturing", "provided_data": {}}
        score = run_sanity_checks(emissions, None, 0.5, q)
        assert score < 1.0

    def test_suspicious_confidence(self):
        emissions = {"scope1": 100, "scope2": 200, "scope3": 300, "total": 600}
        q = {
            "industry": "technology",
            "provided_data": {"revenue_usd": 1_000_000},  # only 1 field
        }
        score = run_sanity_checks(emissions, None, 0.99, q)
        assert score < 1.0

    def test_zero_total_with_data(self):
        emissions = {"scope1": 0, "scope2": 0, "scope3": 0, "total": 0}
        q = {
            "industry": "manufacturing",
            "provided_data": {"fuel_use_liters": 5000, "electricity_kwh": 10000},
        }
        score = run_sanity_checks(emissions, None, 0.5, q)
        assert score < 1.0


# ── Benchmark alignment ────────────────────────────────────────────


class TestBenchmarkAlignment:
    def test_reasonable_split(self):
        # Manufacturing: typically S1 ~30%, S2 ~20%, S3 ~50%
        emissions = {"scope1": 300, "scope2": 200, "scope3": 500}
        score = check_benchmark_alignment(emissions, "manufacturing")
        assert score >= 0.5

    def test_zero_total_neutral(self):
        emissions = {"scope1": 0, "scope2": 0, "scope3": 0}
        assert check_benchmark_alignment(emissions, "manufacturing") == 0.5

    def test_wildly_wrong_split(self):
        # 100% Scope 1, 0% everything else — unusual for any industry
        emissions = {"scope1": 10000, "scope2": 0, "scope3": 0}
        score = check_benchmark_alignment(emissions, "technology")
        assert score < 0.7


# ── Composite scorer ───────────────────────────────────────────────


class TestScoreResponse:
    def test_weights_sum_to_one(self):
        total = W_ACCURACY + W_COMPLIANCE + W_COMPLETENESS + W_ANTI_HALLUCINATION + W_BENCHMARK
        assert total == pytest.approx(1.0)

    def test_good_response_scores_high(self):
        result = score_response(
            emissions={"scope1": 100, "scope2": 200, "scope3": 300, "total": 600},
            breakdown={"scope1_detail": {"fuel": 100}},
            confidence=0.7,
            sources=["EPA eGRID"],
            assumptions=["Default grid factor for US"],
            questionnaire={
                "industry": "manufacturing",
                "provided_data": {"fuel_use_liters": 50, "electricity_kwh": 5000},
            },
            ground_truth={"scope1": 100, "scope2": 200, "scope3": 300},
            industry="manufacturing",
        )
        assert result["final"] > 0.5
        assert all(0 <= v <= 1.0 for v in result.values())

    def test_empty_response_scores_low(self):
        result = score_response(
            emissions={"scope1": 0, "scope2": 0, "scope3": 0, "total": 0},
            breakdown=None,
            confidence=None,
            sources=None,
            assumptions=None,
            questionnaire={
                "industry": "manufacturing",
                "provided_data": {"fuel_use_liters": 5000, "electricity_kwh": 50000},
            },
            ground_truth={"scope1": 10000, "scope2": 5000, "scope3": 50000},
            industry="manufacturing",
        )
        assert result["final"] < 0.5

    def test_no_ground_truth_gives_neutral_accuracy(self):
        result = score_response(
            emissions={"scope1": 100, "scope2": 200, "scope3": 300, "total": 600},
            breakdown={"scope1_detail": {}},
            confidence=0.7,
            sources=["EPA"],
            assumptions=["Default"],
            questionnaire={"industry": "manufacturing", "provided_data": {}},
            ground_truth=None,
        )
        assert result["accuracy"] == 0.5
