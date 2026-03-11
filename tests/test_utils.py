"""Tests for carbonscope.utils — unit conversions, GWP, data completeness."""

import pytest

from carbonscope.utils import (
    convert_units,
    get_gwp,
    to_co2e,
    calc_data_completeness,
)


# ── Unit conversions ────────────────────────────────────────────────


class TestConvertUnits:
    def test_gallons_to_liters(self):
        assert abs(convert_units(100, "gallons_to_liters") - 378.541) < 0.01

    def test_miles_to_km(self):
        assert abs(convert_units(1, "miles_to_km") - 1.60934) < 0.001

    def test_therms_to_kwh(self):
        assert abs(convert_units(1, "therms_to_kwh") - 29.3001) < 0.01

    def test_tonnes_to_kg(self):
        assert convert_units(1, "tonnes_to_kg") == 1000.0

    def test_unknown_conversion_raises(self):
        with pytest.raises(ValueError, match="Unknown conversion"):
            convert_units(1, "lightyears_to_km")


# ── GWP helpers ─────────────────────────────────────────────────────


class TestGWP:
    def test_co2_gwp(self):
        assert get_gwp("CO2") == 1

    def test_ch4_gwp(self):
        assert get_gwp("CH4") == 27

    def test_n2o_gwp(self):
        assert get_gwp("N2O") == 273

    def test_sf6_gwp(self):
        assert get_gwp("SF6") == 25200

    def test_unknown_gas_raises(self):
        with pytest.raises(ValueError, match="Unknown gas"):
            get_gwp("XYZ_999")

    def test_to_co2e_simple(self):
        result = to_co2e(co2_kg=100, ch4_kg=1, n2o_kg=0)
        assert result == 100 * 1 + 1 * 27 + 0  # 127

    def test_to_co2e_all_zero(self):
        assert to_co2e() == 0.0

    def test_to_co2e_n2o_only(self):
        assert to_co2e(n2o_kg=2) == 2 * 273


# ── Data completeness ──────────────────────────────────────────────


class TestDataCompleteness:
    def test_full_manufacturing_data(self):
        data = {
            "fuel_use_liters": 1000,
            "fuel_type": "diesel",
            "natural_gas_m3": 500,
            "electricity_kwh": 10000,
            "employee_count": 50,
            "revenue_usd": 1_000_000,
            "supplier_spend_usd": 500_000,
            "shipping_ton_km": 10_000,
            "office_sqm": 200,
            "vehicle_km": 5000,
        }
        score = calc_data_completeness(data, "manufacturing")
        assert score == 1.0

    def test_empty_data(self):
        assert calc_data_completeness({}, "manufacturing") == 0.0

    def test_partial_data(self):
        data = {"electricity_kwh": 10000, "employee_count": 50}
        score = calc_data_completeness(data, "manufacturing")
        assert 0.0 < score < 1.0

    def test_unknown_industry_uses_default(self):
        data = {"electricity_kwh": 10000}
        score = calc_data_completeness(data, "space_tourism")
        assert 0.0 < score < 1.0

    def test_zero_values_not_counted(self):
        data = {"electricity_kwh": 0, "fuel_use_liters": 0}
        assert calc_data_completeness(data, "manufacturing") == 0.0
