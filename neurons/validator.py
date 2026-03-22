"""CarbonScope Validator — Bittensor Dendrite client for scoring miners.

Generates test queries (curated + synthetic), sends them to all active miners,
scores responses on 5 axes (accuracy, compliance, completeness,
anti-hallucination, benchmark), and sets weights on-chain via EMA.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
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
# Validate the score file path to prevent directory traversal
_SCORES_DIR = os.path.abspath(os.path.dirname(_SCORES_FILE) or ".")
if not os.path.abspath(_SCORES_FILE).startswith(_SCORES_DIR):
    raise SystemExit(f"VALIDATOR_SCORES_PATH resolves outside its parent directory: {_SCORES_FILE}")
_SCORES_HMAC_FILE = _SCORES_FILE + ".sig"


def _score_hmac_key() -> bytes:
    """Return HMAC key for score file integrity check.

    On test networks, an unset key is allowed with a warning so developers can
    run validators without pre-configuring secrets.  On mainnet (finney) the key
    is mandatory; omitting it causes a hard exit to prevent operating without
    tamper-detection.
    """
    key = os.getenv("VALIDATOR_SCORE_HMAC_KEY", "")
    if not key:
        network = os.getenv("BT_NETWORK", "finney")
        if network == "test":
            bt.logging.warning(
                "VALIDATOR_SCORE_HMAC_KEY not set — score file will be stored unsigned. "
                "This is acceptable on the test network. Set this env var before going to mainnet."
            )
            return b""
        bt.logging.error(
            "VALIDATOR_SCORE_HMAC_KEY not set — score file integrity cannot be verified. "
            "Set this env var to a secure random string."
        )
        raise SystemExit("Missing VALIDATOR_SCORE_HMAC_KEY")
    return key.encode("utf-8")


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

        # Per-miner adaptive alpha: new miners learn faster
        self._query_counts: dict[int, int] = {}
        self._cold_start_rounds = 10  # queries before miner is "established"
        self._cold_start_alpha = min(0.3, self.alpha * 3)  # higher learning rate for new miners
        self._cold_start_seed = 0.3   # neutral starting score for new miners

        # Track how many blocks since last weight update
        self.last_weight_block = 0

        # Circuit breaker state
        self._consecutive_failures = 0
        self._max_failures = getattr(self.config, "circuit_breaker_max_failures", 3)
        self._backoff_seconds = getattr(self.config, "circuit_breaker_base_backoff", 2.0)
        self._max_backoff = getattr(self.config, "circuit_breaker_max_backoff", 60.0)

        # Metagraph sync config
        self._metagraph_sync_interval = getattr(self.config, "metagraph_sync_interval", 120)
        self._last_metagraph_sync = 0.0  # epoch seconds

        # Dynamic miner skipping: skip miners with N consecutive zero scores
        self._skip_zero_after = getattr(self.config, "skip_zero_after", 10)
        self._consecutive_zeros: dict[int, int] = {}

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
        parser.add_argument("--metagraph_sync_interval", type=int, default=120,
                            help="Seconds between metagraph syncs (default 120)")
        parser.add_argument("--skip_zero_after", type=int, default=10,
                            help="Skip miners with this many consecutive zero scores")
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
        """Load persisted EMA scores from disk with HMAC integrity verification."""
        try:
            with open(_SCORES_FILE) as f:
                raw_data = f.read()
                data = json.loads(raw_data)
            # Verify HMAC if signature file exists
            if os.path.exists(_SCORES_HMAC_FILE):
                hmac_key = _score_hmac_key()
                if hmac_key:
                    with open(_SCORES_HMAC_FILE) as f:
                        stored_sig = f.read().strip()
                    expected_sig = hmac.new(
                        hmac_key, raw_data.encode("utf-8"), hashlib.sha256
                    ).hexdigest()
                    if not hmac.compare_digest(stored_sig, expected_sig):
                        bt.logging.error("Score file integrity check failed — possible tampering. Starting fresh.")
                        return {}
            scores = {int(k): float(v) for k, v in data.items()}
            bt.logging.info(f"Loaded {len(scores)} persisted scores from {_SCORES_FILE}")
            return scores
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return {}

    def _save_scores(self) -> None:
        """Persist EMA scores to disk atomically with HMAC signature."""
        tmp = _SCORES_FILE + ".tmp"
        try:
            raw_data = json.dumps({str(k): v for k, v in self.scores.items()})
            with open(tmp, "w") as f:
                f.write(raw_data)
            os.replace(tmp, _SCORES_FILE)
            # Write HMAC signature (skipped in unsigned/dev mode)
            hmac_key = _score_hmac_key()
            if hmac_key:
                sig = hmac.new(
                    hmac_key, raw_data.encode("utf-8"), hashlib.sha256
                ).hexdigest()
                sig_tmp = _SCORES_HMAC_FILE + ".tmp"
                with open(sig_tmp, "w") as f:
                    f.write(sig)
                os.replace(sig_tmp, _SCORES_HMAC_FILE)
        except OSError:
            bt.logging.error("Failed to persist scores to disk — data may be lost on restart")

    # ── Weight management ───────────────────────────────────────────

    def update_scores(self, uid: int, score: float) -> None:
        """Update EMA score for a miner with adaptive alpha.

        New miners use a higher learning rate (cold_start_alpha) so they can
        prove themselves quickly.  Established miners use the base alpha for
        stability.  First-time miners are seeded with a blended neutral score
        to avoid over-rewarding or over-penalizing on a single query.
        """
        # Track consecutive zeros for dynamic skipping
        if score == 0.0:
            self._consecutive_zeros[uid] = self._consecutive_zeros.get(uid, 0) + 1
        else:
            self._consecutive_zeros[uid] = 0

        if uid in self.scores:
            self._query_counts[uid] = self._query_counts.get(uid, 0) + 1
            alpha = (
                self._cold_start_alpha
                if self._query_counts[uid] <= self._cold_start_rounds
                else self.alpha
            )
            self.scores[uid] = (1 - alpha) * self.scores[uid] + alpha * score
        else:
            # Cold start: blend neutral seed with first observed score
            self._query_counts[uid] = 1
            self.scores[uid] = (
                self._cold_start_seed * (1 - self._cold_start_alpha)
                + score * self._cold_start_alpha
            )
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
            # All miners scored zero — assign uniform weights so miners remain visible
            weights = [1.0 / len(uids)] * len(uids)

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
                    # Add random jitter to avoid synchronized retry storms across validators
                    jitter = random.uniform(0, delay * 0.3)
                    bt.logging.warning(
                        f"Query attempt {q_attempt + 1} failed, retrying in {delay + jitter:.2f}s:\n"
                        f"{traceback.format_exc()}"
                    )
                    time.sleep(delay + jitter)
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
                # Sync metagraph at configurable interval
                now = time.time()
                if now - self._last_metagraph_sync >= self._metagraph_sync_interval:
                    self.metagraph.sync(subtensor=self.subtensor)
                    self._last_metagraph_sync = now

                miner_uids = [
                    uid for uid in range(self.metagraph.n)
                    if not self.metagraph.validator_permit[uid]
                    and self.metagraph.active[uid]
                ]

                # Skip miners with too many consecutive zero scores
                if self._skip_zero_after > 0:
                    skipped = [
                        uid for uid in miner_uids
                        if self._consecutive_zeros.get(uid, 0) >= self._skip_zero_after
                    ]
                    if skipped:
                        bt.logging.debug(
                            f"Skipping {len(skipped)} miners with {self._skip_zero_after}+ "
                            f"consecutive zeros: {skipped[:10]}{'...' if len(skipped) > 10 else ''}"
                        )
                        miner_uids = [uid for uid in miner_uids if uid not in skipped]
                        # Periodically give skipped miners another chance (every 10th round)
                        if self.case_index % 10 == 0 and skipped:
                            probe = random.sample(skipped, min(3, len(skipped)))
                            miner_uids.extend(probe)
                            bt.logging.debug(f"Probing {len(probe)} skipped miners: {probe}")

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
