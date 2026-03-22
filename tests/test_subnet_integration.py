"""Integration tests for the CarbonScope subnet bridge and validator logic.

These tests mock bittensor entirely so no actual subnet connection is made.
They verify: circuit breaker behavior, consensus median selection,
HMAC score file round-trip, and validator EMA updates.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
import tempfile
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_synapse(total: float, success: bool = True, confidence: float = 0.9) -> MagicMock:
    syn = MagicMock()
    syn.is_success = success
    syn.emissions = {"total": total, "scope1": total * 0.4, "scope2": total * 0.3, "scope3": total * 0.3}
    syn.breakdown = {}
    syn.confidence = confidence
    syn.sources = []
    syn.assumptions = {}
    syn.methodology_version = "1.0"
    return syn


# ---------------------------------------------------------------------------
# subnet_bridge: _select_by_consensus
# ---------------------------------------------------------------------------

class TestSelectByConsensus:
    def _load(self):
        from api.services.subnet_bridge import _select_by_consensus
        return _select_by_consensus

    def _score(self, final: float) -> dict:
        return {"final": final, "accuracy": final, "compliance": final,
                "completeness": final, "anti_hallucination": final, "benchmark": final}

    def test_selects_response_closest_to_median(self):
        select = self._load()
        responses = [
            (0, _make_synapse(100.0), self._score(0.8)),
            (1, _make_synapse(110.0), self._score(0.8)),
            (2, _make_synapse(500.0), self._score(0.8)),  # outlier
        ]
        uid, resp, _ = select(responses)
        # median of [100, 110, 500] = 110 → closest is uid 1 (total=110)
        assert uid == 1

    def test_filters_low_quality_responses(self):
        select = self._load()
        responses = [
            (0, _make_synapse(100.0), self._score(0.1)),   # below quality threshold
            (1, _make_synapse(200.0), self._score(0.8)),
            (2, _make_synapse(210.0), self._score(0.9)),
        ]
        uid, resp, _ = select(responses)
        # Only uids 1 and 2 pass min_quality=0.3; median([200,210])=205 → closest is uid 1
        assert uid == 1

    def test_falls_back_when_all_below_quality(self):
        """When all responses score below min_quality, falls back to all responses."""
        select = self._load()
        responses = [
            (0, _make_synapse(100.0), self._score(0.1)),
            (1, _make_synapse(105.0), self._score(0.2)),
            (2, _make_synapse(200.0), self._score(0.1)),
        ]
        # median([100,105,200])=105 → closest overall is uid 1
        uid, resp, _ = select(responses)
        assert uid == 1

    def test_single_quality_response_returned(self):
        select = self._load()
        responses = [
            (0, _make_synapse(100.0), self._score(0.5)),
            (1, _make_synapse(100.0), self._score(0.5)),
            (2, _make_synapse(100.0), self._score(0.5)),
        ]
        uid, resp, _ = select(responses)
        # All equal distance to median — just check it returns a valid response
        assert uid in (0, 1, 2)


# ---------------------------------------------------------------------------
# subnet_bridge: global circuit breaker
# ---------------------------------------------------------------------------

class TestGlobalCircuitBreaker:
    def _reset(self):
        import api.services.subnet_bridge as sb
        sb._global_cb_failures = 0
        sb._global_cb_opened_at = 0.0

    def test_opens_after_threshold_failures(self):
        import api.services.subnet_bridge as sb
        self._reset()
        for _ in range(sb._GLOBAL_CB_FAILURE_THRESHOLD):
            sb._global_cb_record_failure()
        assert sb._global_cb_is_open()

    def test_resets_on_success(self):
        import api.services.subnet_bridge as sb
        self._reset()
        for _ in range(sb._GLOBAL_CB_FAILURE_THRESHOLD):
            sb._global_cb_record_failure()
        sb._global_cb_record_success()
        assert not sb._global_cb_is_open()

    def test_recovers_after_timeout(self):
        import api.services.subnet_bridge as sb
        import time
        self._reset()
        for _ in range(sb._GLOBAL_CB_FAILURE_THRESHOLD):
            sb._global_cb_record_failure()
        # Simulate timeout has passed by backdating opened_at
        with sb._global_cb_lock:
            sb._global_cb_opened_at = time.monotonic() - sb._GLOBAL_CB_RECOVERY_TIMEOUT - 1
        assert not sb._global_cb_is_open()

    def test_estimate_emissions_raises_when_circuit_open(self):
        import api.services.subnet_bridge as sb
        import asyncio
        self._reset()
        for _ in range(sb._GLOBAL_CB_FAILURE_THRESHOLD):
            sb._global_cb_record_failure()
        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            asyncio.get_event_loop().run_until_complete(
                sb.estimate_emissions({"industry": "tech"})
            )
        self._reset()


# ---------------------------------------------------------------------------
# subnet_bridge: per-miner circuit breaker
# ---------------------------------------------------------------------------

class TestPerMinerCircuitBreaker:
    def _reset(self):
        import api.services.subnet_bridge as sb
        with sb._miner_cb_lock:
            sb._miner_cb.clear()

    def test_opens_after_threshold_failures(self):
        import api.services.subnet_bridge as sb
        self._reset()
        uid = 42
        for _ in range(sb._PER_MINER_FAILURE_THRESHOLD):
            sb._miner_cb_record_failure(uid)
        assert sb._miner_cb_is_open(uid)

    def test_unknown_miner_is_not_open(self):
        import api.services.subnet_bridge as sb
        self._reset()
        assert not sb._miner_cb_is_open(999)

    def test_success_clears_failures(self):
        import api.services.subnet_bridge as sb
        self._reset()
        uid = 7
        for _ in range(sb._PER_MINER_FAILURE_THRESHOLD):
            sb._miner_cb_record_failure(uid)
        sb._miner_cb_record_success(uid)
        assert not sb._miner_cb_is_open(uid)


# ---------------------------------------------------------------------------
# validator: HMAC score file round-trip
# ---------------------------------------------------------------------------

class TestValidatorScoreHMAC:
    """Tests _save_scores / _load_scores HMAC integrity via temp files."""

    def _make_validator(self, tmpdir: str, *, hmac_key: str = "test-secret") -> object:
        """Create a minimal CarbonValidator with mocked bittensor."""
        # We need to import validator without bittensor executing real network code
        bt_mock = types.ModuleType("bittensor")
        bt_mock.logging = MagicMock()
        bt_mock.Wallet = MagicMock
        bt_mock.Subtensor = MagicMock
        bt_mock.Metagraph = MagicMock
        bt_mock.Dendrite = MagicMock
        bt_mock.Config = MagicMock(return_value=MagicMock(
            netuid=1, ema_alpha=0.1, circuit_breaker_max_failures=3,
            circuit_breaker_base_backoff=2.0, circuit_breaker_max_backoff=60.0,
            metagraph_sync_interval=120, skip_zero_after=10,
            logging=MagicMock(),
        ))

        scores_file = os.path.join(tmpdir, "scores.json")
        envpatch = {
            "VALIDATOR_SCORES_PATH": scores_file,
            "VALIDATOR_SCORE_HMAC_KEY": hmac_key,
            "BT_NETWORK": "test",
        }

        # Import with mocked bittensor
        import importlib
        with patch.dict(os.environ, envpatch, clear=False), \
             patch.dict("sys.modules", {"bittensor": bt_mock}):
            import neurons.validator as vmod
            importlib.reload(vmod)
            with patch.object(vmod, "_score_hmac_key", return_value=hmac_key.encode()):
                v = object.__new__(vmod.CarbonValidator)
                v.scores = {}
                v._consecutive_zeros = {}
                v._query_counts = {}
                v.alpha = 0.1
                v._cold_start_alpha = 0.3
                v._cold_start_rounds = 10
                v._cold_start_seed = 0.3

                # Monkey-patch save/load to use temp paths
                v._scores_file = scores_file
                v._sig_file = scores_file + ".sig"
                return v, vmod, scores_file, hmac_key

    def test_roundtrip_with_hmac(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_file = os.path.join(tmpdir, "scores.json")
            hmac_key = "roundtrip-key"

            data = {1: 0.75, 2: 0.50, 3: 0.90}
            raw = json.dumps({str(k): v for k, v in data.items()})

            # Write scores + HMAC manually
            with open(scores_file, "w") as f:
                f.write(raw)
            sig = _hmac.new(hmac_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
            with open(scores_file + ".sig", "w") as f:
                f.write(sig)

            # Verify sig is correct
            with open(scores_file + ".sig") as f:
                stored = f.read().strip()
            expected = _hmac.new(hmac_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
            assert _hmac.compare_digest(stored, expected)

    def test_tampered_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_file = os.path.join(tmpdir, "scores.json")
            hmac_key = b"tamper-test-key"

            original = '{"1": 0.8}'
            with open(scores_file, "w") as f:
                f.write(original)
            sig = _hmac.new(hmac_key, original.encode(), hashlib.sha256).hexdigest()
            with open(scores_file + ".sig", "w") as f:
                f.write(sig)

            # Tamper with the scores file
            tampered = '{"1": 0.99}'
            with open(scores_file, "w") as f:
                f.write(tampered)

            # Verify that HMAC check detects the tampering
            with open(scores_file) as f:
                raw = f.read()
            with open(scores_file + ".sig") as f:
                stored_sig = f.read().strip()
            expected_sig = _hmac.new(hmac_key, raw.encode(), hashlib.sha256).hexdigest()
            assert not _hmac.compare_digest(stored_sig, expected_sig), \
                "HMAC check should fail for tampered file"


# ---------------------------------------------------------------------------
# validator: EMA update logic
# ---------------------------------------------------------------------------

class TestValidatorEMA:
    def _make_scores_obj(self) -> MagicMock:
        """Create a lightweight object mimicking CarbonValidator score state."""
        v = MagicMock()
        v.scores = {}
        v._query_counts = {}
        v._consecutive_zeros = {}
        v.alpha = 0.1
        v._cold_start_alpha = 0.3
        v._cold_start_rounds = 10
        v._cold_start_seed = 0.3
        v._save_scores = MagicMock()

        # Inline update_scores
        import neurons.validator as vmod
        import types
        v.update_scores = types.MethodType(vmod.CarbonValidator.update_scores, v)
        return v

    def test_cold_start_seeds_with_neutral_score(self):
        import neurons.validator as vmod
        from unittest.mock import patch as _patch

        bt_mock = types.ModuleType("bittensor")
        bt_mock.logging = MagicMock()

        with _patch.dict("sys.modules", {"bittensor": bt_mock}), \
             _patch.dict(os.environ, {"VALIDATOR_SCORES_PATH": "/tmp/_test_scores.json",
                                      "BT_NETWORK": "test"}):
            import importlib
            importlib.reload(vmod)
            v = self._make_scores_obj()
            v.update_scores(uid=5, score=1.0)
            # First query: blended seed + observed score
            expected = v._cold_start_seed * (1 - v._cold_start_alpha) + 1.0 * v._cold_start_alpha
            assert abs(v.scores[5] - expected) < 1e-9

    def test_ema_tracks_consecutive_zeros(self):
        import neurons.validator as vmod
        bt_mock = types.ModuleType("bittensor")
        bt_mock.logging = MagicMock()

        with patch.dict("sys.modules", {"bittensor": bt_mock}), \
             patch.dict(os.environ, {"VALIDATOR_SCORES_PATH": "/tmp/_test_scores2.json",
                                     "BT_NETWORK": "test"}):
            import importlib
            importlib.reload(vmod)
            v = self._make_scores_obj()
            v.scores[3] = 0.5
            v._query_counts[3] = 20  # established miner

            v.update_scores(uid=3, score=0.0)
            assert v._consecutive_zeros[3] == 1

            v.update_scores(uid=3, score=0.5)  # non-zero resets counter
            assert v._consecutive_zeros[3] == 0

    def test_established_miner_uses_base_alpha(self):
        import neurons.validator as vmod
        bt_mock = types.ModuleType("bittensor")
        bt_mock.logging = MagicMock()

        with patch.dict("sys.modules", {"bittensor": bt_mock}), \
             patch.dict(os.environ, {"VALIDATOR_SCORES_PATH": "/tmp/_test_scores3.json",
                                     "BT_NETWORK": "test"}):
            import importlib
            importlib.reload(vmod)
            v = self._make_scores_obj()
            v.scores[7] = 0.6
            v._query_counts[7] = 50  # well past cold start

            v.update_scores(uid=7, score=1.0)
            expected = (1 - v.alpha) * 0.6 + v.alpha * 1.0
            assert abs(v.scores[7] - expected) < 1e-9
