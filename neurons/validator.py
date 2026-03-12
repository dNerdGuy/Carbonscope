"""CarbonScope Validator — Bittensor Dendrite client for scoring miners.

Generates test queries (curated + synthetic), sends them to all active miners,
scores responses on 5 axes (accuracy, compliance, completeness,
anti-hallucination, benchmark), and sets weights on-chain via EMA.
"""

from __future__ import annotations

import argparse
import random
import time
import traceback

import bittensor as bt

from carbonscope.protocol import CarbonSynapse
from carbonscope.scoring import score_response
from carbonscope.test_cases.generator import get_curated_cases, generate_synthetic_query


class CarbonValidator:
    """Bittensor validator that queries and scores carbon emission miners."""

    def __init__(self) -> None:
        self.config = self._get_config()
        bt.logging.set_config(self.config.logging)

        self.wallet = bt.Wallet(config=self.config)
        self.subtensor = bt.Subtensor(config=self.config)
        self.metagraph = bt.Metagraph(
            netuid=self.config.netuid,
            network=self.subtensor.network,
        )
        self.dendrite = bt.Dendrite(wallet=self.wallet)

        bt.logging.info(f"Wallet: {self.wallet}")
        bt.logging.info(f"Subtensor: {self.subtensor}")
        bt.logging.info(f"Metagraph: {self.metagraph}")

        # Load curated test cases
        self.curated_cases = get_curated_cases()
        self.case_index = 0

        # Moving average scores per miner UID — EMA α = 0.1
        self.scores: dict[int, float] = {}
        self.alpha = 0.1

        # Track how many blocks since last weight update
        self.last_weight_block = 0

        # Circuit breaker state
        self._consecutive_failures = 0
        self._max_failures = 3
        self._backoff_seconds = 2.0
        self._max_backoff = 60.0

    # ── Config ──────────────────────────────────────────────────────

    @staticmethod
    def _get_config() -> bt.Config:
        parser = argparse.ArgumentParser(description="CarbonScope Validator")
        parser.add_argument("--netuid", type=int, default=1, help="Subnet UID")
        parser.add_argument("--query_interval", type=int, default=60,
                            help="Seconds between query rounds")
        parser.add_argument("--query_timeout", type=float, default=30.0,
                            help="Timeout for miner queries (seconds)")
        bt.Wallet.add_args(parser)
        bt.Subtensor.add_args(parser)
        bt.logging.add_args(parser)
        return bt.Config(parser)

    # ── Query generation ────────────────────────────────────────────

    def next_query(self) -> tuple[CarbonSynapse, dict | None]:
        """Return the next test query and its ground truth (if available).

        Alternates: 70% curated (has ground truth), 30% synthetic.
        """
        if random.random() < 0.7 and self.curated_cases:
            case = self.curated_cases[self.case_index % len(self.curated_cases)]
            self.case_index += 1
        else:
            case = generate_synthetic_query(completeness_level=random.uniform(0.3, 1.0))

        synapse = CarbonSynapse(
            questionnaire=case["questionnaire"],
            context=case.get("context", {}),
        )
        ground_truth = case.get("ground_truth")
        return synapse, ground_truth

    # ── Scoring ─────────────────────────────────────────────────────

    def score_miner_response(
        self,
        synapse: CarbonSynapse,
        response: CarbonSynapse,
        ground_truth: dict | None,
    ) -> float:
        """Score a single miner response. Returns 0.0–1.0."""
        if not response.is_success or response.emissions is None:
            return 0.0

        industry = synapse.questionnaire.get("industry", "manufacturing")

        result = score_response(
            emissions=response.emissions,
            breakdown=response.breakdown,
            confidence=response.confidence,
            sources=response.sources,
            assumptions=response.assumptions,
            questionnaire=synapse.questionnaire,
            ground_truth=ground_truth,
            industry=industry,
        )
        return result["final"]

    # ── Weight management ───────────────────────────────────────────

    def update_scores(self, uid: int, score: float) -> None:
        """Update EMA score for a miner."""
        if uid in self.scores:
            self.scores[uid] = (1 - self.alpha) * self.scores[uid] + self.alpha * score
        else:
            self.scores[uid] = score

    def should_set_weights(self) -> bool:
        """Check if enough blocks have passed since last weight update."""
        try:
            current_block = self.subtensor.block
            tempo = self.subtensor.tempo(self.config.netuid)
            return (current_block - self.last_weight_block) >= tempo
        except Exception:
            # Fallback: set weights every 100 blocks
            return True

    def set_weights(self) -> None:
        """Normalize scores and set weights on-chain."""
        if not self.scores:
            return

        uids = list(self.scores.keys())
        raw = [self.scores[uid] for uid in uids]
        total = sum(raw)

        if total > 0:
            weights = [w / total for w in raw]
        else:
            weights = [1.0 / len(uids)] * len(uids)

        bt.logging.info(
            f"Setting weights for {len(uids)} miners. "
            f"Top score: {max(raw):.3f}, Min: {min(raw):.3f}"
        )

        try:
            self.subtensor.set_weights(
                wallet=self.wallet,
                netuid=self.config.netuid,
                uids=uids,
                weights=weights,
                wait_for_inclusion=True,
            )
            self.last_weight_block = self.subtensor.block
            bt.logging.info("Weights set successfully.")
        except Exception:
            bt.logging.error(f"Failed to set weights:\n{traceback.format_exc()}")

    # ── Main loop ───────────────────────────────────────────────────

    def run(self) -> None:
        """Run the validator query-score-weight loop."""
        bt.logging.info("Validator started. Beginning query loop...")

        try:
            while True:
                # 1. Sync metagraph
                self.metagraph.sync(subtensor=self.subtensor)

                # 2. Find active miners (not validators)
                miner_uids = [
                    uid for uid in range(self.metagraph.n)
                    if not self.metagraph.validator_permit[uid]
                    and self.metagraph.active[uid]
                ]

                if not miner_uids:
                    bt.logging.warning("No active miners found. Waiting...")
                    time.sleep(self.config.query_interval)
                    continue

                miner_axons = [self.metagraph.axons[uid] for uid in miner_uids]

                # 3. Generate query
                synapse, ground_truth = self.next_query()
                bt.logging.info(
                    f"Querying {len(miner_uids)} miners. "
                    f"Industry: {synapse.questionnaire.get('industry', '?')}"
                )

                # 4. Query all miners (with circuit breaker)
                try:
                    responses: list[CarbonSynapse] = self.dendrite.query(
                        axons=miner_axons,
                        synapse=synapse,
                        timeout=self.config.query_timeout,
                    )
                    self._consecutive_failures = 0
                    self._backoff_seconds = 2.0
                except Exception:
                    self._consecutive_failures += 1
                    bt.logging.error(
                        f"Query failed ({self._consecutive_failures}/{self._max_failures}):\n"
                        f"{traceback.format_exc()}"
                    )
                    if self._consecutive_failures >= self._max_failures:
                        backoff = min(self._backoff_seconds, self._max_backoff)
                        bt.logging.warning(
                            f"Circuit breaker: {self._consecutive_failures} consecutive failures. "
                            f"Backing off {backoff:.0f}s..."
                        )
                        time.sleep(backoff)
                        self._backoff_seconds = min(self._backoff_seconds * 2, self._max_backoff)
                    else:
                        time.sleep(self.config.query_interval)
                    continue

                # 5. Score each response
                for uid, response in zip(miner_uids, responses):
                    try:
                        # Skip error responses (miner signaled failure via confidence < 0)
                        if response.confidence is not None and response.confidence < 0:
                            bt.logging.info(f"  UID {uid}: error response (confidence={response.confidence}), score=0")
                            self.update_scores(uid, 0.0)
                            continue

                        sc = self.score_miner_response(synapse, response, ground_truth)
                    except Exception:
                        bt.logging.error(f"Scoring failed for UID {uid}:\n{traceback.format_exc()}")
                        sc = 0.0

                    self.update_scores(uid, sc)

                    status = "OK" if response.is_success else (
                        "TIMEOUT" if response.is_timeout else "FAIL"
                    )
                    bt.logging.info(f"  UID {uid}: score={sc:.3f} [{status}]")

                # 6. Set weights if tempo allows
                if self.should_set_weights():
                    self.set_weights()

                # 7. Wait
                time.sleep(self.config.query_interval)

        except KeyboardInterrupt:
            bt.logging.info("Shutting down validator...")
        finally:
            self.dendrite.close_session()


def main() -> None:
    validator = CarbonValidator()
    validator.run()


if __name__ == "__main__":
    main()
