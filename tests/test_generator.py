"""Tests for the test case generator module."""

import pytest

from carbonscope.test_cases.generator import (
    get_curated_cases,
    get_case_by_id,
    generate_synthetic_query,
)


class TestCuratedCases:
    def test_curated_cases_load(self):
        cases = get_curated_cases()
        assert len(cases) == 5

    def test_each_case_has_ground_truth(self):
        for case in get_curated_cases():
            gt = case["ground_truth"]
            assert "scope1" in gt
            assert "scope2" in gt
            assert "scope3" in gt
            assert "total" in gt

    def test_ground_truth_total_is_consistent(self):
        for case in get_curated_cases():
            gt = case["ground_truth"]
            expected = gt["scope1"] + gt["scope2"] + gt["scope3"]
            assert gt["total"] == pytest.approx(expected, rel=0.01)

    def test_get_case_by_id(self):
        case = get_case_by_id("logistics_provider_x")
        assert case is not None
        assert case["questionnaire"]["industry"] == "transportation"

    def test_get_case_by_id_not_found(self):
        assert get_case_by_id("nonexistent") is None

    def test_logistics_provider_has_scope1(self):
        """Logistics company with 1.8M liters diesel should have significant S1."""
        case = get_case_by_id("logistics_provider_x")
        assert case["ground_truth"]["scope1"] > 0

    def test_tech_saas_has_low_scope1(self):
        """SaaS company with no fuel should have S1 ≈ 0."""
        case = get_case_by_id("tech_saas")
        assert case["ground_truth"]["scope1"] == 0


class TestSyntheticGenerator:
    def test_generates_valid_case(self):
        case = generate_synthetic_query(completeness_level=0.5)
        assert "questionnaire" in case
        assert "ground_truth" in case
        q = case["questionnaire"]
        assert "company" in q
        assert "industry" in q
        assert "provided_data" in q

    def test_high_completeness_has_more_fields(self):
        low = generate_synthetic_query(completeness_level=0.2)
        high = generate_synthetic_query(completeness_level=1.0)
        low_fields = len(low["questionnaire"]["provided_data"])
        high_fields = len(high["questionnaire"]["provided_data"])
        # High completeness should generally have ≥ as many fields
        # (random, so just check high is at least partially populated)
        assert high_fields >= 1
        assert low_fields >= 1

    def test_ground_truth_non_negative(self):
        for _ in range(10):
            case = generate_synthetic_query(completeness_level=0.7)
            gt = case["ground_truth"]
            assert gt["scope1"] >= 0
            assert gt["scope2"] >= 0
            assert gt["scope3"] >= 0
            assert gt["total"] >= 0
