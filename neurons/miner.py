"""CarbonScope Miner — Bittensor Axon server for carbon emission estimation.

Receives CarbonSynapse queries from validators, estimates corporate
Scope 1/2/3 emissions using emission factor databases, and returns
structured results with confidence scores and audit trails.
"""

from __future__ import annotations

import argparse
import time
import traceback

import bittensor as bt

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


class CarbonMiner:
    """Bittensor miner that estimates corporate carbon emissions."""

    def __init__(self) -> None:
        self.config = self._get_config()
        bt.logging.set_config(self.config.logging)

        self.wallet = bt.Wallet(config=self.config)
        self.subtensor = bt.Subtensor(config=self.config)
        self.metagraph = bt.Metagraph(
            netuid=self.config.netuid,
            network=self.subtensor.network,
        )

        bt.logging.info(f"Wallet: {self.wallet}")
        bt.logging.info(f"Subtensor: {self.subtensor}")
        bt.logging.info(f"Metagraph: {self.metagraph}")

        self.axon = bt.Axon(wallet=self.wallet, config=self.config)
        self.axon.attach(
            forward_fn=self.forward,
            blacklist_fn=self.blacklist,
        )

        bt.logging.info(f"Axon created on port {self.axon.port}")

    # ── Config ──────────────────────────────────────────────────────

    @staticmethod
    def _get_config() -> bt.Config:
        parser = argparse.ArgumentParser(description="CarbonScope Miner")
        parser.add_argument("--netuid", type=int, default=1, help="Subnet UID")
        bt.Wallet.add_args(parser)
        bt.Subtensor.add_args(parser)
        bt.Axon.add_args(parser)
        bt.logging.add_args(parser)
        return bt.Config(parser)

    # ── Blacklist ───────────────────────────────────────────────────

    def blacklist(self, synapse: CarbonSynapse) -> tuple[bool, str]:
        """Reject requests from unregistered or non-validator hotkeys."""
        caller = synapse.dendrite.hotkey
        if caller not in self.metagraph.hotkeys:
            return True, "Unregistered hotkey"

        uid = list(self.metagraph.hotkeys).index(caller)
        if not self.metagraph.validator_permit[uid]:
            return True, "Caller is not a validator"

        return False, ""

    # ── Forward — the main estimation logic ─────────────────────────

    def forward(self, synapse: CarbonSynapse) -> CarbonSynapse:
        """Estimate corporate emissions from the questionnaire data."""
        try:
            return self._estimate(synapse)
        except Exception:
            bt.logging.error(f"Estimation failed:\n{traceback.format_exc()}")
            # Signal error with negative confidence so validators can skip
            synapse.emissions = {"scope1": 0, "scope2": 0, "scope3": 0, "total": 0}
            synapse.confidence = -1.0
            synapse.sources = []
            synapse.assumptions = ["Estimation failed due to internal error"]
            return synapse

    def _estimate(self, synapse: CarbonSynapse) -> CarbonSynapse:
        q = synapse.questionnaire
        data = q.get("provided_data", {})
        industry = q.get("industry", "manufacturing")
        region = q.get("region", "US")
        ctx = synapse.context or {}

        assumptions: list[str] = []
        sources: list[str] = []

        # ── Scope 1: Direct emissions ───────────────────────────────

        scope1 = 0.0
        scope1_detail: dict[str, float] = {}

        # Stationary combustion (fuel)
        fuel_liters = data.get("fuel_use_liters") or 0
        fuel_type = data.get("fuel_type", "diesel")
        if fuel_liters > 0:
            val = calc_stationary_combustion(fuel_type, fuel_liters, "liters")
            scope1_detail["stationary_combustion"] = val
            scope1 += val
            sources.append("EPA emission factors v2025")

        # Natural gas
        ng_m3 = data.get("natural_gas_m3") or 0
        if ng_m3 > 0:
            val = calc_stationary_combustion("natural_gas", ng_m3, "m3")
            scope1_detail["stationary_combustion"] = scope1_detail.get("stationary_combustion", 0) + val
            scope1 += val

        # Mobile combustion (vehicle fleet)
        vehicle_km = data.get("vehicle_km") or 0
        if vehicle_km > 0:
            val = calc_mobile_combustion("heavy_truck_diesel", distance_km=vehicle_km)
            scope1_detail["mobile_combustion"] = val
            scope1 += val
            assumptions.append("Assumed heavy diesel truck for vehicle fleet")

        # Fugitive emissions (refrigerants)
        ref_type = data.get("refrigerant_type")
        ref_leaked = data.get("refrigerant_kg_leaked") or 0
        if ref_type and ref_leaked > 0:
            val = calc_fugitive_emissions(ref_type, ref_leaked)
            scope1_detail["fugitive_emissions"] = val
            scope1 += val

        # ── Scope 2: Purchased energy ──────────────────────────────

        scope2 = 0.0
        scope2_detail: dict[str, float] = {}

        electricity_kwh = data.get("electricity_kwh") or 0
        if electricity_kwh > 0:
            grid_override = ctx.get("grid_factor_override")
            rec_kwh = data.get("rec_kwh") or 0

            loc = calc_location_based(electricity_kwh, region)
            mkt = calc_market_based(electricity_kwh, region, grid_override, rec_kwh)

            scope2_detail["location_based"] = loc
            scope2_detail["market_based"] = mkt
            scope2 = loc  # Default to location-based per GHG Protocol
            sources.append(f"Grid factor for region {region}")

            if grid_override:
                assumptions.append(f"Market-based factor override: {grid_override} gCO2e/kWh")
            if rec_kwh > 0:
                assumptions.append(f"RECs cover {rec_kwh} kWh")

        # ── Scope 3: Value chain ────────────────────────────────────

        scope3_detail: dict[str, float] = {}

        # Cat 1: Purchased goods & services
        supplier_spend = data.get("supplier_spend_usd") or 0
        if supplier_spend > 0:
            scope3_detail["cat1_purchased_goods"] = calc_cat1_purchased_goods(supplier_spend, industry)
            assumptions.append("Scope 3 Cat 1: spend-based estimate using industry factors")

        # Cat 4: Upstream transport
        shipping_tkm = data.get("shipping_ton_km") or 0
        if shipping_tkm > 0:
            scope3_detail["cat4_upstream_transport"] = calc_cat4_transport(shipping_tkm, "road")
            assumptions.append("Scope 3 Cat 4: assumed road transport")
            sources.append("GLEC Framework transport factors")

        # Cat 5: Waste
        waste_kg = data.get("waste_kg") or 0
        if waste_kg > 0:
            scope3_detail["cat5_waste"] = calc_cat5_waste(waste_kg)

        # Cat 6: Business travel
        travel_spend = data.get("business_travel_usd") or 0
        employees = data.get("employee_count") or 0
        if travel_spend > 0 or employees > 0:
            scope3_detail["cat6_business_travel"] = calc_cat6_business_travel(
                employees, industry, travel_spend
            )

        # Cat 7: Employee commuting
        if employees > 0:
            scope3_detail["cat7_commuting"] = calc_cat7_commuting(employees, region)
            assumptions.append(f"Scope 3 Cat 7: regional avg commuting for {region}")

        # Fill remaining categories from industry averages
        scope3_detail = fill_industry_defaults(scope3_detail, industry, data)
        if any(k not in ("cat1_purchased_goods", "cat4_upstream_transport", "cat5_waste",
                          "cat6_business_travel", "cat7_commuting")
               for k in scope3_detail):
            assumptions.append("Missing Scope 3 categories filled using industry averages")
            sources.append("Industry average benchmarks (CDP/EPA)")

        scope3 = sum(scope3_detail.values())

        # ── Assemble response ──────────────────────────────────────

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

        bt.logging.info(
            f"Estimated emissions: S1={scope1:.1f} S2={scope2:.1f} S3={scope3:.1f} "
            f"Total={total:.1f} kgCO2e (confidence={confidence:.2f})"
        )

        return synapse

    # ── Main loop ───────────────────────────────────────────────────

    def run(self) -> None:
        """Start the Axon server and run the metagraph sync loop."""
        self.axon.serve(netuid=self.config.netuid, subtensor=self.subtensor)
        self.axon.start()
        bt.logging.info("Miner started. Listening for queries...")

        try:
            while True:
                self.metagraph.sync(subtensor=self.subtensor)
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
