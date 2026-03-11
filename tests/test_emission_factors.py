"""Tests for emission factor calculation modules — Scope 1, 2, 3 and loader."""

import pytest

from carbonscope.emission_factors.loader import (
    load_factors,
    get_factor,
    get_fuel_factor,
    get_grid_factor,
    get_transport_factor,
    get_industry_profile,
)
from carbonscope.emission_factors.scope1 import (
    calc_stationary_combustion,
    calc_mobile_combustion,
    calc_fugitive_emissions,
)
from carbonscope.emission_factors.scope2 import (
    calc_location_based,
    calc_market_based,
    calc_steam_heating,
)
from carbonscope.emission_factors.scope3 import (
    calc_cat1_purchased_goods,
    calc_cat4_transport,
    calc_cat5_waste,
    calc_cat6_business_travel,
    calc_cat7_commuting,
    calc_spend_based,
    fill_industry_defaults,
)


# ── Loader ──────────────────────────────────────────────────────────


class TestLoader:
    def test_load_known_dataset(self):
        data = load_factors("epa_stationary")
        assert "fuels" in data

    def test_load_unknown_dataset_raises(self):
        with pytest.raises(ValueError, match="Unknown dataset"):
            load_factors("nonexistent_dataset")

    def test_get_factor_nested(self):
        val = get_factor("epa_stationary", "fuels", "diesel", "total_kgco2e_per_unit")
        assert isinstance(val, (int, float))
        assert val > 0

    def test_get_fuel_factor_diesel(self):
        f = get_fuel_factor("diesel")
        assert f == pytest.approx(2.71, rel=0.05)

    def test_get_fuel_factor_unknown_falls_back(self):
        f = get_fuel_factor("unicorn_oil")
        assert f == get_fuel_factor("diesel")  # fallback

    def test_get_grid_factor_us(self):
        f = get_grid_factor("US")
        assert f > 0

    def test_get_grid_factor_egrid_subregion(self):
        f = get_grid_factor("CAMX")
        assert f == pytest.approx(240, rel=0.1)

    def test_get_grid_factor_country(self):
        f = get_grid_factor("FR")
        assert f == pytest.approx(55, rel=0.2)

    def test_get_grid_factor_global_fallback(self):
        f = get_grid_factor("ZZ")
        assert f > 0  # Should get global average

    def test_get_transport_factor_road(self):
        f = get_transport_factor("road")
        assert f > 0

    def test_get_industry_profile_manufacturing(self):
        p = get_industry_profile("manufacturing")
        assert "typical_scope_split" in p


# ── Scope 1 ─────────────────────────────────────────────────────────


class TestScope1:
    def test_stationary_combustion_diesel(self):
        result = calc_stationary_combustion("diesel", 1000, "liters")
        assert result > 0
        assert result == pytest.approx(1000 * 2.71, rel=0.05)

    def test_stationary_combustion_zero_quantity(self):
        assert calc_stationary_combustion("diesel", 0, "liters") == 0.0

    def test_stationary_combustion_negative_quantity(self):
        assert calc_stationary_combustion("diesel", -100, "liters") == 0.0

    def test_mobile_combustion_distance(self):
        result = calc_mobile_combustion("heavy_truck_diesel", distance_km=100)
        assert result > 0

    def test_mobile_combustion_fuel(self):
        result = calc_mobile_combustion("heavy_truck_diesel", fuel_liters=50)
        assert result > 0

    def test_mobile_combustion_zero(self):
        assert calc_mobile_combustion("heavy_truck_diesel", 0, 0) == 0.0

    def test_fugitive_emissions_r134a(self):
        result = calc_fugitive_emissions("R_134a", 10)
        assert result > 0

    def test_fugitive_emissions_zero_leak(self):
        assert calc_fugitive_emissions("R_134a", 0) == 0.0


# ── Scope 2 ─────────────────────────────────────────────────────────


class TestScope2:
    def test_location_based_us(self):
        result = calc_location_based(10000, "US")
        assert result > 0

    def test_location_based_france(self):
        # France has low-carbon grid
        result_fr = calc_location_based(10000, "FR")
        result_us = calc_location_based(10000, "US")
        assert result_fr < result_us

    def test_location_based_zero(self):
        assert calc_location_based(0, "US") == 0.0

    def test_market_based_no_override(self):
        result = calc_market_based(10000, "US")
        assert result > 0

    def test_market_based_with_override(self):
        result = calc_market_based(10000, "US", factor_override=100)
        expected = 10000 * 100 / 1000.0
        assert result == pytest.approx(expected, rel=0.01)

    def test_market_based_full_rec_coverage(self):
        result = calc_market_based(10000, "US", rec_kwh=10000)
        assert result == 0.0

    def test_steam_heating_gas(self):
        result = calc_steam_heating(1000, "natural_gas")
        assert result == pytest.approx(1000 * 0.21, rel=0.01)

    def test_steam_heating_zero(self):
        assert calc_steam_heating(0) == 0.0


# ── Scope 3 ─────────────────────────────────────────────────────────


class TestScope3:
    def test_cat1_purchased_goods(self):
        result = calc_cat1_purchased_goods(1_000_000, "manufacturing")
        assert result > 0

    def test_cat1_zero_spend(self):
        assert calc_cat1_purchased_goods(0) == 0.0

    def test_cat4_transport_road(self):
        result = calc_cat4_transport(10000, "road")
        assert result > 0

    def test_cat4_transport_sea(self):
        road = calc_cat4_transport(10000, "road")
        sea = calc_cat4_transport(10000, "sea")
        assert sea < road  # Sea freight is more efficient

    def test_cat5_waste_landfill(self):
        result = calc_cat5_waste(1000, "landfill")
        assert result == pytest.approx(1000 * 0.586, rel=0.01)

    def test_cat6_business_travel_spend(self):
        result = calc_cat6_business_travel(0, "manufacturing", travel_spend_usd=100_000)
        assert result > 0

    def test_cat6_business_travel_employee(self):
        result = calc_cat6_business_travel(100, "technology")
        assert result > 0

    def test_cat7_commuting(self):
        result = calc_cat7_commuting(100, "US")
        assert result > 0

    def test_cat7_commuting_zero_employees(self):
        assert calc_cat7_commuting(0) == 0.0

    def test_spend_based(self):
        result = calc_spend_based(1_000_000, "manufacturing")
        assert result > 0

    def test_fill_industry_defaults_adds_missing(self):
        existing = {"cat1_purchased_goods": 5000.0}
        data = {"revenue_usd": 10_000_000, "employee_count": 100}
        filled = fill_industry_defaults(existing, "manufacturing", data)
        assert len(filled) > len(existing)
        # Original value should be preserved
        assert filled["cat1_purchased_goods"] == 5000.0
