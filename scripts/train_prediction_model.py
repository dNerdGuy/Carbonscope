#!/usr/bin/env python3
"""Train the ML-based Scope 3 emissions predictor.

Generates synthetic training data using the CarbonScope test-case generator,
trains a GradientBoostingRegressor for each of scope1/scope2/scope3, and
persists the models + feature metadata to ``data/model/scope3_predictor.pkl``.

Usage:
    python scripts/train_prediction_model.py [--samples N] [--output PATH]

The model is a thin sklearn Pipeline:
    OrdinalEncoder (industry + region)  →  GradientBoostingRegressor

Features:
    industry (ordinal-encoded), region (ordinal-encoded),
    employee_count, revenue_usd, log_employee_count, log_revenue_usd
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Allow importing from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import joblib
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from sklearn.compose import ColumnTransformer

from api.services.prediction import (
    _REVENUE_INTENSITIES,
    _EMPLOYEE_INTENSITIES,
    predict_missing_emissions,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

INDUSTRIES = list(_REVENUE_INTENSITIES.keys())
REGIONS = ["US", "EU", "UK", "CA", "AU", "DE", "FR", "GB", "CAMX", "RMPA", "unknown"]

DEFAULT_OUTPUT = str(Path(__file__).resolve().parent.parent / "data" / "model" / "scope3_predictor.pkl")


def _generate_sample(
    rng: np.random.Generator,
    industry: str,
    region: str,
    revenue_usd: float,
    employee_count: int,
) -> dict[str, float]:
    """Generate a noisy ground-truth emission estimate using the rule-based predictor."""
    prediction = predict_missing_emissions(
        known_data={"revenue_usd": revenue_usd, "employee_count": employee_count},
        industry=industry,
        region=region,
    )
    preds = prediction["predictions"]
    # Add realistic multiplicative noise ±30%
    noise = rng.uniform(0.70, 1.30, size=3)
    return {
        "scope1": float(preds.get("scope1", 0) * noise[0]),
        "scope2": float(preds.get("scope2", 0) * noise[1]),
        "scope3": float(preds.get("scope3", 0) * noise[2]),
    }


def build_training_data(n_samples: int, rng: np.random.Generator) -> tuple:
    """Return (X, y_scope1, y_scope2, y_scope3) numpy arrays."""
    X_rows: list[tuple] = []
    y1: list[float] = []
    y2: list[float] = []
    y3: list[float] = []

    for _ in range(n_samples):
        industry = rng.choice(INDUSTRIES)
        region = rng.choice(REGIONS)
        # Revenue: log-uniform $500k – $10B
        revenue_usd = float(np.exp(rng.uniform(np.log(500_000), np.log(10_000_000_000))))
        # Employees: log-uniform 5 – 50000
        employee_count = int(np.exp(rng.uniform(np.log(5), np.log(50_000))))

        gt = _generate_sample(rng, industry, region, revenue_usd, employee_count)

        X_rows.append((
            industry,
            region,
            float(employee_count),
            revenue_usd,
            float(np.log1p(employee_count)),
            float(np.log1p(revenue_usd)),
        ))
        y1.append(gt["scope1"])
        y2.append(gt["scope2"])
        y3.append(gt["scope3"])

    X = np.array(X_rows, dtype=object)
    return X, np.array(y1), np.array(y2), np.array(y3)


def _build_pipeline() -> Pipeline:
    """Build a sklearn Pipeline with ordinal encoding + gradient boosting."""
    categorical_features = [0, 1]   # industry, region columns
    numeric_features = [2, 3, 4, 5]  # employee_count, revenue_usd, log_*

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
             categorical_features),
            ("num", "passthrough", numeric_features),
        ]
    )

    regressor = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        min_samples_leaf=10,
        random_state=42,
    )

    return Pipeline([("preprocessor", preprocessor), ("regressor", regressor)])


def train(n_samples: int = 8_000, output_path: str = DEFAULT_OUTPUT, seed: int = 42) -> None:
    logger.info("Generating %d synthetic training samples…", n_samples)
    rng = np.random.default_rng(seed)
    X, y1, y2, y3 = build_training_data(n_samples, rng)

    models = {}
    for scope_name, y in [("scope1", y1), ("scope2", y2), ("scope3", y3)]:
        logger.info("Training %s model (n=%d)…", scope_name, len(y))
        pipe = _build_pipeline()
        pipe.fit(X, y)
        models[scope_name] = pipe
        logger.info("  %s — training R²: %.3f", scope_name,
                    pipe.score(X, y))

    artifact = {
        "models": models,
        "industries": INDUSTRIES,
        "regions": REGIONS,
        "feature_names": [
            "industry", "region",
            "employee_count", "revenue_usd",
            "log_employee_count", "log_revenue_usd",
        ],
        "version": "1.0.0",
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output_path)
    logger.info("Model saved to %s", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train CarbonScope Scope 3 prediction model")
    parser.add_argument("--samples", type=int, default=8_000, help="Number of synthetic training samples")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output .pkl path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    train(n_samples=args.samples, output_path=args.output, seed=args.seed)
