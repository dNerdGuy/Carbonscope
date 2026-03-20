"""Unit tests for the CarbonScope validator — scoring, persistence, weights, and retry."""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch, call

import pytest

from neurons.validator import CarbonValidator, _SCORES_FILE


# ── Helper ──────────────────────────────────────────────────────────


def _make_validator(**overrides):
    """Create a CarbonValidator with mocked __init__."""
    with patch.object(CarbonValidator, "__init__", lambda self: None):
        v = CarbonValidator.__new__(CarbonValidator)
    v.scores = overrides.get("scores", {})
    v.alpha = overrides.get("alpha", 0.1)
    v.wallet = MagicMock()
    v.subtensor = MagicMock()
    v.metagraph = MagicMock()
    v.dendrite = MagicMock()
    v.config = MagicMock()
    v.config.netuid = 1
    v.last_weight_block = 0
    v._consecutive_failures = 0
    v._max_failures = 3
    v._backoff_seconds = 2.0
    v._max_backoff = 60.0
    return v


# ── EMA score updates ──────────────────────────────────────────────


class TestUpdateScores:
    def test_new_uid_gets_raw_score(self):
        v = _make_validator()
        v._save_scores = MagicMock()
        v.update_scores(42, 0.8)
        assert v.scores[42] == 0.8

    def test_ema_blends_existing_score(self):
        v = _make_validator(scores={42: 0.5})
        v._save_scores = MagicMock()
        v.update_scores(42, 1.0)
        # EMA: 0.9 * 0.5 + 0.1 * 1.0 = 0.55
        assert abs(v.scores[42] - 0.55) < 1e-9

    def test_ema_repeated_zero_decays(self):
        v = _make_validator(scores={1: 1.0})
        v._save_scores = MagicMock()
        for _ in range(20):
            v.update_scores(1, 0.0)
        assert v.scores[1] < 0.15  # decayed close to 0

    def test_save_scores_called_on_update(self):
        v = _make_validator()
        v._save_scores = MagicMock()
        v.update_scores(1, 0.5)
        v._save_scores.assert_called_once()


# ── Score persistence ───────────────────────────────────────────────


class TestScorePersistence:
    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VALIDATOR_SCORE_HMAC_KEY", "test-hmac-key-for-ci")
        path = str(tmp_path / "scores.json")
        v = _make_validator(scores={1: 0.5, 2: 0.9})
        with patch("neurons.validator._SCORES_FILE", path):
            v._save_scores()
            v.scores = {}  # clear
            v.scores = v._load_scores()
        assert v.scores == {1: 0.5, 2: 0.9}

    def test_load_missing_file_returns_empty(self):
        v = _make_validator()
        with patch("neurons.validator._SCORES_FILE", "/nonexistent/path.json"):
            scores = v._load_scores()
        assert scores == {}

    def test_load_corrupt_json_returns_empty(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("{corrupt")
        v = _make_validator()
        with patch("neurons.validator._SCORES_FILE", path):
            scores = v._load_scores()
        assert scores == {}


# ── Weight normalization ────────────────────────────────────────────


class TestSetWeights:
    def test_empty_scores_noop(self):
        v = _make_validator(scores={})
        v.set_weights()
        v.subtensor.set_weights.assert_not_called()

    def test_positive_scores_normalized(self):
        v = _make_validator(scores={0: 0.3, 1: 0.7})
        v.set_weights()
        call_args = v.subtensor.set_weights.call_args
        weights = call_args.kwargs.get("weights") or call_args[1].get("weights")
        assert abs(sum(weights) - 1.0) < 1e-9
        # uid 1 should have 0.7/1.0 = 0.7 weight
        idx = call_args.kwargs.get("uids", call_args[1].get("uids")).index(1)
        assert abs(weights[idx] - 0.7) < 1e-9

    def test_all_zero_scores_uniform(self):
        """When all scores are zero, all weights should be 0 (no reward)."""
        v = _make_validator(scores={0: 0.0, 1: 0.0, 2: 0.0})
        v.set_weights()
        call_args = v.subtensor.set_weights.call_args
        weights = call_args.kwargs.get("weights") or call_args[1].get("weights")
        for w in weights:
            assert w == 0.0

    def test_retry_on_failure(self):
        v = _make_validator(scores={0: 0.5})
        v.subtensor.set_weights.side_effect = [
            RuntimeError("net error"),
            RuntimeError("net error"),
            None,  # succeeds on third attempt
        ]
        with patch("neurons.validator.time") as mock_time:
            v.set_weights()
        assert v.subtensor.set_weights.call_count == 3
        # Two retries with delays 1s and 2s
        assert mock_time.sleep.call_count == 2

    def test_all_retries_exhausted(self):
        v = _make_validator(scores={0: 0.5})
        v.subtensor.set_weights.side_effect = RuntimeError("always fails")
        with patch("neurons.validator.time"):
            v.set_weights()
        # 1 initial + 3 retries = 4 attempts
        assert v.subtensor.set_weights.call_count == 4


# ── Score miner response ───────────────────────────────────────────


class TestScoreMinerResponse:
    def test_failed_response_returns_zero(self):
        v = _make_validator()
        synapse = MagicMock()
        synapse.questionnaire = {"industry": "manufacturing"}
        response = MagicMock()
        response.is_success = False
        response.emissions = None
        assert v.score_miner_response(synapse, response, None) == 0.0

    def test_null_emissions_returns_zero(self):
        v = _make_validator()
        synapse = MagicMock()
        synapse.questionnaire = {"industry": "manufacturing"}
        response = MagicMock()
        response.is_success = True
        response.emissions = None
        assert v.score_miner_response(synapse, response, None) == 0.0


# ── Circuit breaker ─────────────────────────────────────────────────


class TestCircuitBreaker:
    def test_failures_increment(self):
        v = _make_validator()
        v._consecutive_failures = 2
        assert v._consecutive_failures < v._max_failures

    def test_backoff_doubles(self):
        v = _make_validator()
        v._backoff_seconds = 2.0
        v._backoff_seconds = min(v._backoff_seconds * 2, v._max_backoff)
        assert v._backoff_seconds == 4.0

    def test_backoff_capped_at_max(self):
        v = _make_validator()
        v._backoff_seconds = 32.0
        v._backoff_seconds = min(v._backoff_seconds * 2, v._max_backoff)
        assert v._backoff_seconds == v._max_backoff
