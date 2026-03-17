"""CarbonScope Validator — Bittensor Dendrite client for scoring miners.

Generates test queries (curated + synthetic), sends them to all active miners,
scores responses on 5 axes (accuracy, compliance, completeness,
anti-hallucination, benchmark), and sets weights on-chain via EMA.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
import traceback

import bittensor as bt

from carbonscope.protocol import CarbonSynapse
from carbonscope.scoring import score_response
from carbonscope.test_cases.generator import get_curated_cases, generate_synthetic_query

# Path for persisting EMA scores across restarts
_SCORES_FILE = os.getenv("VALIDATOR_SCORES_PATH", "validator_scores.json")


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

        # Moving average scores per miner UID
        self.scores: dict[int, float] = self._load_scores()
        raw_alpha = getattr(self.config, "ema_alpha", 0.1)
        self.alpha = max(0.0, min(1.0, float(raw_alpha)))

        # Track how many blocks since last weight update
        self.last_weight_block = 0

        # Circuit breaker state
        self._consecutive_failures = 0
        self._max_failures = getattr(self.config, "circuit_breaker_max_failures", 3)
        self._backoff_seconds = getattr(self.config, "circuit_breaker_base_backoff", 2.0)
        self._max_backoff = getattr(self.config, "circuit_breaker_max_backoff", 60.0)

    # ── Config ──────────────────────────────────────────────────────

    @staticmethod
    def _get_config() -> bt.Config:
        parser = argparse.ArgumentParser(description="CarbonScope Validator")
        parser.add_argument("--netuid", type=int, default=1, help="Subnet UID")
        parser.add_argument("--query_interval", type=int, default=60,
                            help="Seconds between query rounds")
        parser.add_argument("--query_timeout", type=float, default=30.0,
                            help="Timeout for miner queries (seconds)")
        parser.add_argument("--ema_alpha", type=float, default=0.1,
                            help="EMA smoothing factor for scores (0.0–1.0)")
        parser.add_argument("--circuit_breaker_max_failures", type=int, default=3,
                            help="Consecutive failures before circuit breaker opens")
        parser.add_argument("--circuit_breaker_base_backoff", type=float, default=2.0,
                            help="Base backoff seconds for circuit breaker")
        parser.add_argument("--circuit_breaker_max_backoff", type=float, default=60.0,
                            help="Maximum backoff seconds for circuit breaker")
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

    # ── Score persistence ─────────────────────────────────────────────

    def _load_scores(self) -> dict[int, float]:
        """Load persisted EMA scores from disk."""
        try:
            with open(_SCORES_FILE) as f:
                data = json.load(f)
            scores = {int(k): float(v) for k, v in data.items()}
            bt.logging.info(f"Loaded {len(scores)} persisted scores from {_SCORES_FILE}")
            return scores
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return {}

    def _save_scores(self) -> None:
        """Persist EMA scores to disk atomically (write-then-rename)."""
        tmp = _SCORES_FILE + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump({str(k): v for k, v in self.scores.items()}, f)
            os.replace(tmp, _SCORES_FILE)
        except OSError:
            bt.logging.warning("Failed to persist scores to disk")

    # ── Weight management ───────────────────────────────────────────

    def update_scores(self, uid: int, score: float) -> None:
        """Update EMA score for a miner and persist to disk."""
        if uid in self.scores:
            self.scores[uid] = (1 - self.alpha) * self.scores[uid] + self.alpha * score
        else:
            self.scores[uid] = score
        self._save_scores()

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
        """Normalize scores and set weights on-chain with retry logic.

        Miners with a score of exactly 0.0 receive an explicit weight of 0
        (effectively banned from rewards until they improve).
        """
        if not self.scores:
            return

        uids = list(self.scores.keys())
        raw = [self.scores[uid] for uid in uids]
        total = sum(raw)

        if total > 0:
            weights = [w / total for w in raw]
        else:
            # All miners scored zero — assign uniform zero weights
            weights = [0.0] * len(uids)

        zero_count = sum(1 for w in raw if w == 0.0)
        bt.logging.info(
            f"Setting weights for {len(uids)} miners ({zero_count} with zero score). "
            f"Top score: {max(raw):.3f}, Min: {min(raw):.3f}"
        )

        retry_delays = [1, 2, 4]
        for attempt in range(len(retry_delays) + 1):
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
                return
            except Exception:
                if attempt < len(retry_delays):
                    delay = retry_delays[attempt]
                    bt.logging.warning(
                        f"set_weights attempt {attempt + 1} failed, retrying in {delay}s:\n"
                        f"{traceback.format_exc()}"
                    )
                    time.sleep(delay)
                else:
                    bt.logging.error(f"set_weights failed after {attempt + 1} attempts:\n{traceback.format_exc()}")

    # ── Main loop ───────────────────────────────────────────────────

    def _query_miners(self, miner_axons: list, synapse: CarbonSynapse) -> list | None:
        """Query all miners with retry and circuit breaker logic. Returns responses or None."""
        query_retry_delays = [0.5, 1.0, 2.0]
        for q_attempt in range(len(query_retry_delays) + 1):
            try:
                responses = self.dendrite.query(
                    axons=miner_axons,
                    synapse=synapse,
                    timeout=self.config.query_timeout,
                )
                self._consecutive_failures = 0
                self._backoff_seconds = getattr(
                    self.config, "circuit_breaker_base_backoff", 2.0
                )
                return responses
            except Exception:
                if q_attempt < len(query_retry_delays):
                    delay = query_retry_delays[q_attempt]
                    bt.logging.warning(
                        f"Query attempt {q_attempt + 1} failed, retrying in {delay}s:\n"
                        f"{traceback.format_exc()}"
                    )
                    time.sleep(delay)
                else:
                    self._consecutive_failures += 1
                    bt.logging.error(
                        f"Query failed after {q_attempt + 1} attempts "
                        f"({self._consecutive_failures}/{self._max_failures}):\n"
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
        return None

    def _score_and_update(
        self,
        miner_uids: list[int],
        responses: list,
        synapse: CarbonSynapse,
        ground_truth: dict | None,
    ) -> None:
        """Score each miner response and update EMA scores."""
        for uid, response in zip(miner_uids, responses):
            try:
                if response.confidence is not None and response.confidence < 0:
                    bt.logging.info(f"  UID {uid}: error response (confidence={response.confidence}), score=0")
                    self.update_scores(uid, 0.0)
                    continue
                sc = self.score_miner_response(synapse, response, ground_truth)
            except (ValueError, TypeError, KeyError):
                bt.logging.error(f"Scoring failed for UID {uid}:\n{traceback.format_exc()}")
                sc = 0.0

            self.update_scores(uid, sc)

            status = "OK" if response.is_success else (
                "TIMEOUT" if response.is_timeout else "FAIL"
            )
            bt.logging.info(f"  UID {uid}: score={sc:.3f} [{status}]")

    def run(self) -> None:
        """Run the validator query-score-weight loop."""
        bt.logging.info("Validator started. Beginning query loop...")

        try:
            while True:
                self.metagraph.sync(subtensor=self.subtensor)

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

                synapse, ground_truth = self.next_query()
                bt.logging.info(
                    f"Querying {len(miner_uids)} miners. "
                    f"Industry: {synapse.questionnaire.get('industry', '?')}"
                )

                responses = self._query_miners(miner_axons, synapse)
                if responses is None:
                    continue

                self._score_and_update(miner_uids, responses, synapse, ground_truth)

                if self.should_set_weights():
                    self.set_weights()

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
