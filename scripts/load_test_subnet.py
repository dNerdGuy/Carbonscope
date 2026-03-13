#!/usr/bin/env python3
"""Load/stress test for the CarbonScope Bittensor subnet.

Simulates concurrent validator-to-miner queries to measure throughput,
latency, and error rates. Requires the miner's Axon to be running.

Usage:
    python3 scripts/load_test_subnet.py --host 127.0.0.1 --port 8091 \
        --concurrency 10 --total 100

Environment:
    Requires bittensor to be installed (pip install bittensor).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass, field

# Attempt import — we handle missing bittensor gracefully for CI.
try:
    import bittensor as bt
    from carbonscope.protocol import CarbonSynapse

    HAS_BT = True
except ImportError:
    HAS_BT = False

INDUSTRIES = [
    "manufacturing", "transportation", "technology", "retail",
    "energy", "financial_services", "construction", "food_beverage", "healthcare",
]

REGIONS = ["US", "EU", "CN", "IN", "JP", "GB", "BR", "DE", "AU", "CA"]


def random_questionnaire() -> dict:
    """Generate a random but realistic company questionnaire."""
    industry = random.choice(INDUSTRIES)
    return {
        "company": f"LoadTestCorp-{random.randint(1000, 9999)}",
        "industry": industry,
        "services_used": random.sample(
            ["logistics", "manufacturing", "office", "fleet", "data_center"], k=random.randint(1, 3)
        ),
        "provided_data": {
            "fuel_use_liters": random.uniform(0, 50000),
            "fuel_type": random.choice(["diesel", "gasoline", "natural_gas"]),
            "natural_gas_m3": random.uniform(0, 10000),
            "electricity_kwh": random.uniform(10000, 500000),
            "vehicle_km": random.uniform(0, 100000),
            "employee_count": random.randint(10, 5000),
            "revenue_usd": random.uniform(100000, 50_000_000),
            "supplier_spend_usd": random.uniform(10000, 5_000_000),
            "shipping_ton_km": random.uniform(0, 500000),
            "office_sqm": random.uniform(100, 10000),
            "business_travel_usd": random.uniform(0, 500000),
        },
        "region": random.choice(REGIONS),
        "year": random.choice([2023, 2024, 2025]),
    }


@dataclass
class LoadTestResults:
    """Aggregated results from a load test run."""

    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    errors: dict[str, int] = field(default_factory=dict)
    latencies: list[float] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def rps(self) -> float:
        return self.total_requests / self.duration if self.duration > 0 else 0

    @property
    def success_rate(self) -> float:
        return (self.successful / self.total_requests * 100) if self.total_requests > 0 else 0

    def summary(self) -> str:
        lines = [
            "\n" + "=" * 60,
            "  CarbonScope Subnet Load Test Results",
            "=" * 60,
            f"  Total requests:  {self.total_requests}",
            f"  Successful:      {self.successful}",
            f"  Failed:          {self.failed}",
            f"  Success rate:    {self.success_rate:.1f}%",
            f"  Duration:        {self.duration:.2f}s",
            f"  Throughput:      {self.rps:.1f} req/s",
        ]
        if self.latencies:
            lines += [
                f"  Latency (min):   {min(self.latencies)*1000:.0f} ms",
                f"  Latency (avg):   {statistics.mean(self.latencies)*1000:.0f} ms",
                f"  Latency (p50):   {statistics.median(self.latencies)*1000:.0f} ms",
                f"  Latency (p95):   {sorted(self.latencies)[int(len(self.latencies)*0.95)]*1000:.0f} ms",
                f"  Latency (max):   {max(self.latencies)*1000:.0f} ms",
            ]
        if self.errors:
            lines.append("  Errors:")
            for err, count in sorted(self.errors.items(), key=lambda x: -x[1]):
                lines.append(f"    {err}: {count}")
        lines.append("=" * 60)
        return "\n".join(lines)


async def send_query(
    dendrite: "bt.dendrite",
    axon_info: "bt.AxonInfo",
    timeout: float,
) -> tuple[bool, float, str]:
    """Send a single CarbonSynapse query. Returns (success, latency, error_msg)."""
    synapse = CarbonSynapse(
        questionnaire=random_questionnaire(),
        context="load_test",
    )
    t0 = time.monotonic()
    try:
        response = await dendrite.call(
            target_axon=axon_info,
            synapse=synapse,
            timeout=timeout,
        )
        latency = time.monotonic() - t0

        # Check if the response has valid emissions
        if response.emissions is not None and response.emissions > 0:
            return True, latency, ""
        else:
            return False, latency, "empty_response"
    except Exception as e:
        latency = time.monotonic() - t0
        return False, latency, type(e).__name__


async def run_load_test(
    host: str,
    port: int,
    concurrency: int,
    total: int,
    timeout: float,
    ramp_up: float,
) -> LoadTestResults:
    """Run the load test against a miner Axon."""
    wallet = bt.wallet(name="load_test_ephemeral")
    try:
        wallet.create_if_non_existent(coldkey_use_password=False, hotkey_use_password=False)
    except Exception:
        pass  # Wallet may already exist

    dendrite = bt.dendrite(wallet=wallet)
    axon_info = bt.AxonInfo(
        version=1,
        ip=host,
        port=port,
        hotkey=wallet.hotkey.ss58_address,
        coldkey=wallet.coldkey.ss58_address,
    )

    results = LoadTestResults()
    semaphore = asyncio.Semaphore(concurrency)
    delay_per_request = ramp_up / total if ramp_up > 0 and total > 0 else 0

    async def worker(idx: int) -> None:
        if delay_per_request > 0:
            await asyncio.sleep(delay_per_request * idx)
        async with semaphore:
            success, latency, error = await send_query(dendrite, axon_info, timeout)
            results.total_requests += 1
            results.latencies.append(latency)
            if success:
                results.successful += 1
            else:
                results.failed += 1
                if error:
                    results.errors[error] = results.errors.get(error, 0) + 1

    print(f"Starting load test: {total} requests, {concurrency} concurrent, "
          f"target {host}:{port}")

    results.start_time = time.monotonic()
    tasks = [asyncio.create_task(worker(i)) for i in range(total)]
    await asyncio.gather(*tasks)
    results.end_time = time.monotonic()

    return results


async def run_http_load_test(
    host: str,
    port: int,
    concurrency: int,
    total: int,
    timeout: float,
    ramp_up: float,
) -> LoadTestResults:
    """HTTP-based load test against the miner's health endpoint (no bittensor required)."""
    try:
        import aiohttp
    except ImportError:
        print("aiohttp not available — install with: pip install aiohttp", file=sys.stderr)
        sys.exit(1)

    results = LoadTestResults()
    semaphore = asyncio.Semaphore(concurrency)
    delay_per_request = ramp_up / total if ramp_up > 0 and total > 0 else 0
    url = f"http://{host}:{port}/health"

    async def worker(idx: int, session: aiohttp.ClientSession) -> None:
        if delay_per_request > 0:
            await asyncio.sleep(delay_per_request * idx)
        async with semaphore:
            t0 = time.monotonic()
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    latency = time.monotonic() - t0
                    results.latencies.append(latency)
                    results.total_requests += 1
                    if resp.status == 200:
                        results.successful += 1
                    else:
                        results.failed += 1
                        results.errors[f"http_{resp.status}"] = results.errors.get(f"http_{resp.status}", 0) + 1
            except Exception as e:
                latency = time.monotonic() - t0
                results.latencies.append(latency)
                results.total_requests += 1
                results.failed += 1
                err_name = type(e).__name__
                results.errors[err_name] = results.errors.get(err_name, 0) + 1

    print(f"Starting HTTP load test: {total} requests, {concurrency} concurrent, "
          f"target {url}")

    results.start_time = time.monotonic()
    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(worker(i, session)) for i in range(total)]
        await asyncio.gather(*tasks)
    results.end_time = time.monotonic()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="CarbonScope Subnet Load Test")
    parser.add_argument("--host", default="127.0.0.1", help="Miner Axon host")
    parser.add_argument("--port", type=int, default=8091, help="Miner Axon port")
    parser.add_argument("--concurrency", type=int, default=10, help="Max concurrent requests")
    parser.add_argument("--total", type=int, default=100, help="Total number of requests")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout (seconds)")
    parser.add_argument("--ramp-up", type=float, default=0.0, help="Ramp-up period (seconds)")
    parser.add_argument(
        "--mode", choices=["synapse", "http"], default="synapse",
        help="Test mode: 'synapse' (Bittensor dendrite) or 'http' (health endpoint)",
    )
    args = parser.parse_args()

    if args.mode == "synapse":
        if not HAS_BT:
            print("bittensor not installed. Install with: pip install bittensor", file=sys.stderr)
            print("Alternatively, use --mode http for HTTP-only testing.", file=sys.stderr)
            sys.exit(1)
        results = asyncio.run(
            run_load_test(args.host, args.port, args.concurrency, args.total, args.timeout, args.ramp_up)
        )
    else:
        results = asyncio.run(
            run_http_load_test(args.host, args.port, args.concurrency, args.total, args.timeout, args.ramp_up)
        )

    print(results.summary())

    # Exit non-zero if too many failures
    if results.success_rate < 95.0:
        print(f"\n⚠ Success rate {results.success_rate:.1f}% below 95% threshold", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
