"""CarbonScope Miner — Bittensor Axon server for carbon emission estimation.

Receives CarbonSynapse queries from validators, estimates corporate
Scope 1/2/3 emissions using emission factor databases, and returns
structured results with confidence scores and audit trails.
"""

from __future__ import annotations

import argparse
import time
import traceback
from collections import deque

import bittensor as bt
from pydantic import BaseModel, Field, ValidationError, field_validator

from carbonscope.protocol import CarbonSynapse
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
from carbonscope.emission_factors.loader import log_dataset_versions


# ── Input validation schemas ────────────────────────────────────────

VALID_INDUSTRIES = {
    "manufacturing", "transportation", "technology", "retail",
    "energy", "financial_services", "construction", "food_beverage", "healthcare",
}

VALID_FUEL_TYPES = {
    "diesel", "gasoline", "natural_gas", "propane", "fuel_oil",
    "kerosene", "lpg", "coal", "biomass",
}


class ProvidedDataInput(BaseModel):
    fuel_use_liters: float = Field(default=0, ge=0, le=10_000_000)
    fuel_type: str = "diesel"
    natural_gas_m3: float = Field(default=0, ge=0, le=100_000_000)
    electricity_kwh: float = Field(default=0, ge=0, le=1_000_000_000)
    vehicle_km: float = Field(default=0, ge=0, le=100_000_000)
    employee_count: int = Field(default=0, ge=0, le=1_000_000)
    revenue_usd: float = Field(default=0, ge=0, le=1_000_000_000_000)
    supplier_spend_usd: float = Field(default=0, ge=0, le=1_000_000_000_000)
    shipping_ton_km: float = Field(default=0, ge=0, le=10_000_000_000)
    office_sqm: float = Field(default=0, ge=0, le=100_000_000)
    business_travel_usd: float = Field(default=0, ge=0, le=1_000_000_000)
    waste_kg: float = Field(default=0, ge=0, le=1_000_000_000)
    refrigerant_type: str | None = None
    refrigerant_kg_leaked: float = Field(default=0, ge=0, le=1_000_000)
    rec_kwh: float = Field(default=0, ge=0, le=1_000_000_000)

    @field_validator("fuel_type")
    @classmethod
    def validate_fuel_type(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in VALID_FUEL_TYPES:
            raise ValueError(f"Invalid fuel_type '{v}'. Valid: {sorted(VALID_FUEL_TYPES)}")
        return v_lower

    model_config = {"extra": "allow"}


class QuestionnaireInput(BaseModel):
    company: str = ""
    industry: str = "manufacturing"
    services_used: list[str] = []
    provided_data: ProvidedDataInput = ProvidedDataInput()
    region: str = "US"
    year: int = Field(default=2025, ge=1990, le=2100)

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in VALID_INDUSTRIES:
            raise ValueError(f"Invalid industry '{v}'. Valid: {sorted(VALID_INDUSTRIES)}")
        return v_lower

    model_config = {"extra": "allow"}


class CarbonMiner:
    """Bittensor miner that estimates corporate carbon emissions."""

    # Per-hotkey rate limiting defaults (overridden by CLI args)
    _RATE_LIMIT_MAX = 10
    _RATE_LIMIT_WINDOW = 60  # seconds
    _MAX_TRACKED_HOTKEYS = 1000  # bound rate limiter memory

    def __init__(self) -> None:
        self.config = self._get_config()
        bt.logging.set_config(self.config.logging)

        # Apply CLI rate limit overrides
        self._RATE_LIMIT_MAX = getattr(self.config, "rate_limit_max", 10)
        self._RATE_LIMIT_WINDOW = getattr(self.config, "rate_limit_window", 60)
        bt.logging.set_config(self.config.logging)

        self.wallet = bt.Wallet(config=self.config)
        self.subtensor = bt.Subtensor(config=self.config)
        self.metagraph = bt.Metagraph(
            netuid=self.config.netuid,
            network=self.subtensor.network,
        )

        # Verify hotkey is registered
        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            bt.logging.error("Hotkey not registered in metagraph — register before starting miner")
            raise RuntimeError("Miner hotkey not registered on subnet")

        bt.logging.info(f"Wallet: {self.wallet}")
        bt.logging.info(f"Subtensor: {self.subtensor}")
        bt.logging.info(f"Metagraph: {self.metagraph}")

        self.axon = bt.Axon(wallet=self.wallet, config=self.config)
        self.axon.attach(
            forward_fn=self.forward,
            blacklist_fn=self.blacklist,
        )

        # Per-hotkey request tracking for rate limiting
        self._request_times: dict[str, deque] = {}

        bt.logging.info(f"Axon created on port {self.axon.port}")

        # Log emission factor dataset versions at startup
        log_dataset_versions()

    # ── Config ──────────────────────────────────────────────────────

    @staticmethod
    def _get_config() -> bt.Config:
        parser = argparse.ArgumentParser(description="CarbonScope Miner")
        parser.add_argument("--netuid", type=int, default=1, help="Subnet UID")
        parser.add_argument("--rate_limit_max", type=int, default=10,
                            help="Max requests per hotkey per rate limit window")
        parser.add_argument("--rate_limit_window", type=int, default=60,
                            help="Rate limit window in seconds")
        bt.Wallet.add_args(parser)
        bt.Subtensor.add_args(parser)
        bt.Axon.add_args(parser)
        bt.logging.add_args(parser)
        return bt.Config(parser)

    # ── Blacklist ───────────────────────────────────────────────────

    def blacklist(self, synapse: CarbonSynapse) -> tuple[bool, str]:
        """Reject requests from unregistered, non-validator, or rate-limited hotkeys."""
        caller = synapse.dendrite.hotkey
        if caller not in self.metagraph.hotkeys:
            return True, "Unregistered hotkey"

        uid = list(self.metagraph.hotkeys).index(caller)
        if not self.metagraph.validator_permit[uid]:
            return True, "Caller is not a validator"

        # Per-hotkey rate limiting (bounded)
        now = time.time()
        if caller not in self._request_times:
            # Evict oldest entries if at capacity
            if len(self._request_times) >= self._MAX_TRACKED_HOTKEYS:
                oldest_key = next(iter(self._request_times))
                del self._request_times[oldest_key]
            self._request_times[caller] = deque()
        times = self._request_times[caller]
        # Remove entries outside the window
        while times and times[0] < now - self._RATE_LIMIT_WINDOW:
            times.popleft()
        if len(times) >= self._RATE_LIMIT_MAX:
            bt.logging.warning(f"Rate limited hotkey {caller}: {len(times)} requests in {self._RATE_LIMIT_WINDOW}s")
            return True, "Rate limited"
        times.append(now)

        return False, ""

    # ── Forward — the main estimation logic ─────────────────────────

    def forward(self, synapse: CarbonSynapse) -> CarbonSynapse:
        """Estimate corporate emissions from the questionnaire data."""
        try:
            return self._estimate(synapse)
        except (ValueError, ValidationError) as e:
            bt.logging.warning(f"Input validation failed: {e}")
            synapse.emissions = {"scope1": 0, "scope2": 0, "scope3": 0, "total": 0}
            synapse.confidence = -1.0
            synapse.sources = []
            synapse.assumptions = [f"Validation error: {e}"]
            return synapse
        except Exception:
            bt.logging.error(f"Internal estimation error:\n{traceback.format_exc()}")
            synapse.emissions = {"scope1": 0, "scope2": 0, "scope3": 0, "total": 0}
            synapse.confidence = -2.0
            synapse.sources = []
            synapse.assumptions = ["Estimation failed due to internal error"]
            return synapse

    def _estimate(self, synapse: CarbonSynapse) -> CarbonSynapse:
        validated = QuestionnaireInput(**synapse.questionnaire)
        q = validated.model_dump()
        data = q["provided_data"]
        industry = q["industry"]
        region = q["region"]
        ctx = synapse.context or {}

        assumptions: list[str] = []
        sources: list[str] = []

        scope1, scope1_detail = self._estimate_scope1(data, assumptions, sources)
        scope2, scope2_detail = self._estimate_scope2(data, region, ctx, assumptions, sources)
        scope3, scope3_detail = self._estimate_scope3(data, industry, region, assumptions, sources)

        total = scope1 + scope2 + scope3
        confidence = calc_data_completeness(data, industry)

        synapse.emissions = {
            "scope1": round(scope1, 2),
            "scope2": round(scope2, 2),
            "scope3": round(scope3, 2),
            "total": round(total, 2),
        }
        synapse.breakdown = {
            "scope1_detail": scope1_detail,
            "scope2_detail": scope2_detail,
            "scope3_detail": scope3_detail,
        }
        synapse.confidence = round(confidence, 4)
        synapse.data_completeness = round(confidence, 4)
        synapse.sources = sources or ["EPA emission factors v2025"]
        synapse.assumptions = assumptions or ["Standard GHG Protocol methodology applied"]
        synapse.methodology_version = "ghg_protocol_v2025"
        synapse.request_hash = synapse.compute_request_hash()

        bt.logging.info(
            f"Estimated emissions: S1={scope1:.1f} S2={scope2:.1f} S3={scope3:.1f} "
            f"Total={total:.1f} kgCO2e (confidence={confidence:.2f})"
        )

        return synapse

    @staticmethod
    def _estimate_scope1(
        data: dict, assumptions: list[str], sources: list[str],
    ) -> tuple[float, dict[str, float]]:
        """Estimate Scope 1 (direct) emissions."""
        scope1 = 0.0
        detail: dict[str, float] = {}

        fuel_liters = data.get("fuel_use_liters") or 0
        fuel_type = data.get("fuel_type", "diesel")
        if fuel_liters > 0:
            val = calc_stationary_combustion(fuel_type, fuel_liters, "liters")
            detail["stationary_combustion"] = val
            scope1 += val
            sources.append("EPA emission factors v2025")

        ng_m3 = data.get("natural_gas_m3") or 0
        if ng_m3 > 0:
            val = calc_stationary_combustion("natural_gas", ng_m3, "m3")
            detail["stationary_combustion"] = detail.get("stationary_combustion", 0) + val
            scope1 += val

        vehicle_km = data.get("vehicle_km") or 0
        if vehicle_km > 0:
            val = calc_mobile_combustion("heavy_truck_diesel", distance_km=vehicle_km)
            detail["mobile_combustion"] = val
            scope1 += val
            assumptions.append("Assumed heavy diesel truck for vehicle fleet")

        ref_type = data.get("refrigerant_type")
        ref_leaked = data.get("refrigerant_kg_leaked") or 0
        if ref_type and ref_leaked > 0:
            val = calc_fugitive_emissions(ref_type, ref_leaked)
            detail["fugitive_emissions"] = val
            scope1 += val

        return scope1, detail

    @staticmethod
    def _estimate_scope2(
        data: dict, region: str, ctx: dict,
        assumptions: list[str], sources: list[str],
    ) -> tuple[float, dict[str, float]]:
        """Estimate Scope 2 (purchased energy) emissions."""
        scope2 = 0.0
        detail: dict[str, float] = {}

        electricity_kwh = data.get("electricity_kwh") or 0
        if electricity_kwh > 0:
            grid_override = ctx.get("grid_factor_override")
            rec_kwh = data.get("rec_kwh") or 0

            loc = calc_location_based(electricity_kwh, region)
            mkt = calc_market_based(electricity_kwh, region, grid_override, rec_kwh)

            detail["location_based"] = loc
            detail["market_based"] = mkt
            scope2 = loc  # Default to location-based per GHG Protocol
            sources.append(f"Grid factor for region {region}")

            if grid_override:
                assumptions.append(f"Market-based factor override: {grid_override} gCO2e/kWh")
            if rec_kwh > 0:
                assumptions.append(f"RECs cover {rec_kwh} kWh")

        return scope2, detail

    @staticmethod
    def _estimate_scope3(
        data: dict, industry: str, region: str,
        assumptions: list[str], sources: list[str],
    ) -> tuple[float, dict[str, float]]:
        """Estimate Scope 3 (value chain) emissions."""
        detail: dict[str, float] = {}

        supplier_spend = data.get("supplier_spend_usd") or 0
        if supplier_spend > 0:
            detail["cat1_purchased_goods"] = calc_cat1_purchased_goods(supplier_spend, industry)
            assumptions.append("Scope 3 Cat 1: spend-based estimate using industry factors")

        shipping_tkm = data.get("shipping_ton_km") or 0
        if shipping_tkm > 0:
            detail["cat4_upstream_transport"] = calc_cat4_transport(shipping_tkm, "road")
            assumptions.append("Scope 3 Cat 4: assumed road transport")
            sources.append("GLEC Framework transport factors")

        waste_kg = data.get("waste_kg") or 0
        if waste_kg > 0:
            detail["cat5_waste"] = calc_cat5_waste(waste_kg)

        travel_spend = data.get("business_travel_usd") or 0
        employees = data.get("employee_count") or 0
        if travel_spend > 0 or employees > 0:
            detail["cat6_business_travel"] = calc_cat6_business_travel(
                employees, industry, travel_spend
            )

        if employees > 0:
            detail["cat7_commuting"] = calc_cat7_commuting(employees, region)
            assumptions.append(f"Scope 3 Cat 7: regional avg commuting for {region}")

        detail = fill_industry_defaults(detail, industry, data)
        if any(k not in ("cat1_purchased_goods", "cat4_upstream_transport", "cat5_waste",
                          "cat6_business_travel", "cat7_commuting")
               for k in detail):
            assumptions.append("Missing Scope 3 categories filled using industry averages")
            sources.append("Industry average benchmarks (CDP/EPA)")

        return sum(detail.values()), detail

    # ── Main loop ───────────────────────────────────────────────────

    def run(self) -> None:
        """Start the Axon server and run the metagraph sync loop."""
        self.axon.serve(netuid=self.config.netuid, subtensor=self.subtensor)
        self.axon.start()
        bt.logging.info("Miner started. Listening for queries...")

        try:
            while True:
                self.metagraph.sync(subtensor=self.subtensor)
                # Verify hotkey is still registered after metagraph sync
                if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
                    bt.logging.error("Hotkey deregistered from subnet — shutting down miner")
                    break
                bt.logging.debug(f"Metagraph synced. Neurons: {self.metagraph.n}")
                time.sleep(120)  # Sync every ~10 blocks
        except KeyboardInterrupt:
            bt.logging.info("Shutting down miner...")
        finally:
            self.axon.stop()


def main() -> None:
    miner = CarbonMiner()
    miner.run()


if __name__ == "__main__":
    main()
