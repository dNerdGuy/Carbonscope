"""Tests for compliance report generation."""

import pytest

from api.services.compliance import (
    generate_cdp_responses,
    generate_ghg_inventory,
    generate_sbti_pathway,
    generate_tcfd_disclosure,
)


class TestGHGInventory:
    def test_basic_inventory(self):
        report = generate_ghg_inventory(
            company_name="TestCorp",
            industry="manufacturing",
            region="US",
            year=2024,
            scope1=2000,
            scope2=1500,
            scope3=5000,
            total=8500,
            breakdown={
                "scope1_detail": {"stationary_combustion": 2000},
                "scope2_detail": {"location_based": 1500, "market_based": 1400},
                "scope3_detail": {"cat1_purchased_goods": 3000, "cat7_commuting": 500},
            },
            sources=["EPA Emission Factors"],
            assumptions=["Gap-filled Scope 3"],
            confidence=0.72,
        )
        assert report["framework"] == "GHG Protocol Corporate Standard"
        assert report["emissions_summary"]["total_tco2e"] == 8500
        assert report["emissions_summary"]["scope1_tco2e"] == 2000
        assert len(report["scope3_categories"]) == 15

    def test_scope3_has_15_categories(self):
        report = generate_ghg_inventory(
            company_name="Co", industry="tech", region="US",
            year=2024, scope1=10, scope2=20, scope3=50, total=80,
            breakdown={}, sources=[], assumptions=[], confidence=0.5,
        )
        cats = report["scope3_categories"]
        assert len(cats) == 15
        assert cats[0]["category_number"] == 1
        assert cats[-1]["category_number"] == 15


class TestCDP:
    def test_cdp_modules(self):
        report = generate_cdp_responses(
            company_name="TestCorp",
            industry="technology",
            year=2024,
            scope1=500,
            scope2=800,
            scope3=2000,
            total=3300,
            breakdown={"scope2_detail": {"location_based": 800, "market_based": 750}},
            confidence=0.8,
        )
        assert report["framework"] == "CDP Climate Change Questionnaire"
        assert "C6_emissions" in report["modules"]
        assert report["modules"]["C6_emissions"]["C6.1_scope1"] == 500


class TestTCFD:
    def test_tcfd_pillars(self):
        report = generate_tcfd_disclosure(
            company_name="TestCorp",
            industry="manufacturing",
            year=2024,
            scope1=1000,
            scope2=800,
            scope3=3000,
            total=4800,
        )
        assert "governance" in report["pillars"]
        assert "strategy" in report["pillars"]
        assert "risk_management" in report["pillars"]
        assert "metrics_and_targets" in report["pillars"]
        assert report["pillars"]["metrics_and_targets"]["emissions"]["total_tco2e"] == 4800


class TestSBTi:
    def test_sbti_pathway(self):
        report = generate_sbti_pathway(
            company_name="TestCorp",
            year=2024,
            scope1=1000,
            scope2=800,
            scope3=3000,
            total=4800,
        )
        assert report["framework"] == "Science Based Targets initiative (SBTi)"
        assert report["baseline"]["total_tco2e"] == 4800
        pathway = report["pathway"]
        assert len(pathway) == 11  # base year + 10 target years
        assert pathway[0]["year"] == 2024
        assert pathway[-1]["year"] == 2034
        # Emissions should decrease over time
        assert pathway[-1]["total_tco2e"] < pathway[0]["total_tco2e"]

    def test_sbti_reduction_rates(self):
        report = generate_sbti_pathway(
            company_name="Co", year=2024,
            scope1=500, scope2=500, scope3=2000, total=3000,
        )
        # After 10 years at 4.2% annual reduction, S1+2 should be ~65% of original
        target_s12 = report["target"]["scope1_2_target_tco2e"]
        # 1000 * (1-0.042)^10 ≈ 650
        assert 600 < target_s12 < 700
