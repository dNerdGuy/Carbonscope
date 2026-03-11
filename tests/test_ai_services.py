"""Tests for AI enhancement services: LLM parser, prediction, recommendations."""

import pytest

from api.services.llm_parser import generate_audit_trail_local, parse_text_rule_based
from api.services.prediction import (
    predict_from_employees,
    predict_from_revenue,
    predict_missing_emissions,
)
from api.services.recommendations import (
    generate_recommendations,
    summarize_reduction_potential,
)


# ── Rule-based text parsing ──────────────────────────────────────────


class TestRuleBasedParsing:
    def test_parse_electricity_kwh(self):
        result = parse_text_rule_based("We consumed 450000 kWh of electricity last year.")
        assert result["electricity_kwh"] == 450000

    def test_parse_electricity_mwh(self):
        result = parse_text_rule_based("Total consumption was 1,200 MWh.")
        assert result["electricity_kwh"] == 1_200_000

    def test_parse_natural_gas(self):
        result = parse_text_rule_based("Natural gas usage: 12,500 therms.")
        assert result["natural_gas_therms"] == 12500

    def test_parse_diesel(self):
        result = parse_text_rule_based("Used 5,000 gallons of diesel for generators.")
        assert result["diesel_gallons"] == 5000

    def test_parse_employees(self):
        result = parse_text_rule_based("The company employs 350 employees across 4 offices.")
        assert result["employee_count"] == 350

    def test_parse_revenue_millions(self):
        result = parse_text_rule_based("Annual revenue of $42.5 million.")
        assert result["revenue_usd"] == 42_500_000

    def test_parse_waste(self):
        result = parse_text_rule_based("Generated 120 metric tons of waste.")
        assert result["waste_metric_tons"] == 120

    def test_parse_multiple_fields(self):
        text = """
        Acme Corp had 200 employees, revenue of $15M, consumed
        300,000 kWh of electricity, and 8,000 therms of natural gas.
        """
        result = parse_text_rule_based(text)
        assert result["employee_count"] == 200
        assert result["revenue_usd"] == 15_000_000
        assert result["electricity_kwh"] == 300_000
        assert result["natural_gas_therms"] == 8000

    def test_parse_empty_text(self):
        result = parse_text_rule_based("No data here.")
        assert result == {}


# ── Missing data prediction ──────────────────────────────────────────


class TestPrediction:
    def test_predict_from_revenue_tech(self):
        result = predict_from_revenue(10_000_000, "technology")
        assert result["scope1"] > 0
        assert result["scope2"] > 0
        assert result["scope3"] > 0
        # Tech should have low scope 1
        assert result["scope1"] < result["scope3"]

    def test_predict_from_employees_manufacturing(self):
        result = predict_from_employees(500, "manufacturing")
        assert result["scope1"] == 18.0 * 500
        assert result["scope3"] == 40.0 * 500

    def test_predict_missing_with_revenue_and_employees(self):
        result = predict_missing_emissions(
            known_data={"revenue_usd": 5_000_000, "employee_count": 100},
            industry="technology",
        )
        assert result["method"] == "hybrid"
        assert result["uncertainty"]["low"] < result["uncertainty"]["mid"]
        assert result["uncertainty"]["mid"] < result["uncertainty"]["high"]

    def test_predict_missing_with_partial_data(self):
        result = predict_missing_emissions(
            known_data={
                "electricity_kwh": 200_000,
                "revenue_usd": 10_000_000,
            },
            industry="technology",
        )
        # Scope 2 is already covered, shouldn't be in predictions
        assert "scope2" not in result["predictions"]
        assert result["confidence_adjustment"] > 0.4

    def test_predict_fallback_to_industry_average(self):
        result = predict_missing_emissions(
            known_data={},
            industry="retail",
        )
        # Should use industry average when no proxy data at all
        assert result["method"] == "industry_average"
        assert result["predictions"]["scope1"] > 0

    def test_filled_categories_listed(self):
        result = predict_missing_emissions(
            known_data={"employee_count": 100},
            industry="manufacturing",
        )
        assert len(result["filled_categories"]) > 0


# ── Reduction recommendations ────────────────────────────────────────


class TestRecommendations:
    def _sample_emissions(self):
        return {
            "scope1": 2000,
            "scope2": 1500,
            "scope3": 5000,
            "total": 8500,
        }

    def _sample_breakdown(self):
        return {
            "scope1_detail": {
                "stationary_combustion": 800,
                "natural_gas": 400,
                "mobile_combustion": 600,
                "fugitive_emissions": 200,
            },
            "scope2_detail": {
                "location_based": 1500,
                "market_based": 1500,
            },
            "scope3_detail": {
                "cat1_purchased_goods": 2000,
                "cat4_upstream_transport": 500,
                "cat5_waste": 200,
                "cat6_business_travel": 300,
                "cat7_commuting": 400,
            },
        }

    def test_recommendations_generated(self):
        recs = generate_recommendations(
            self._sample_emissions(),
            self._sample_breakdown(),
            "manufacturing",
        )
        assert len(recs) > 0
        assert all("title" in r for r in recs)
        assert all("co2_reduction_tco2e" in r for r in recs)

    def test_recommendations_sorted_by_priority(self):
        recs = generate_recommendations(
            self._sample_emissions(),
            self._sample_breakdown(),
            "manufacturing",
        )
        priorities = [r["priority_score"] for r in recs]
        assert priorities == sorted(priorities, reverse=True)

    def test_summary(self):
        recs = generate_recommendations(
            self._sample_emissions(),
            self._sample_breakdown(),
            "manufacturing",
        )
        summary = summarize_reduction_potential(recs, 8500)
        assert summary["recommendation_count"] == len(recs)
        assert summary["total_reduction_tco2e"] > 0
        assert summary["total_reduction_pct"] > 0

    def test_no_recommendations_for_zero_emissions(self):
        recs = generate_recommendations(
            {"scope1": 0, "scope2": 0, "scope3": 0, "total": 0},
            {},
            "technology",
        )
        assert len(recs) == 0

    def test_each_recommendation_has_cost_tier(self):
        recs = generate_recommendations(
            self._sample_emissions(),
            self._sample_breakdown(),
            "manufacturing",
        )
        for r in recs:
            assert r["cost_tier"] in ("low", "medium", "high")


# ── Audit trail ──────────────────────────────────────────────────────


class TestAuditTrail:
    def test_local_audit_trail(self):
        text = generate_audit_trail_local(
            company="TestCorp",
            industry="manufacturing",
            year=2024,
            scope1=1000,
            scope2=800,
            scope3=3000,
            total=4800,
            breakdown={
                "scope1_detail": {"stationary_combustion": 1000},
                "scope2_detail": {"location_based": 800},
            },
            assumptions=["No fleet data provided"],
            sources=["EPA Emission Factors"],
            confidence=0.65,
        )
        assert "TestCorp" in text
        assert "4,800" in text
        assert "Scope 1" in text

    def test_audit_trail_low_confidence(self):
        text = generate_audit_trail_local(
            company="SmallCo",
            industry="retail",
            year=2024,
            scope1=100,
            scope2=200,
            scope3=500,
            total=800,
            breakdown={},
            assumptions=[],
            sources=[],
            confidence=0.3,
        )
        assert "limited" in text.lower()
