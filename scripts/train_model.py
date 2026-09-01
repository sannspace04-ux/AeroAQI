"""
scripts/train_model.py
=======================
CLI training script for the AeroAQI XGBoost forecasting model.

Loads historical observations from the database, builds the feature matrix,
trains one XGBRegressor per (target × forecast hour), evaluates on a
held-out 20% split, and saves the models to data/models/.

The ingestion pipeline (scripts/run_ingestion.py) automatically loads and
runs these models after each ingestion run (step 7).

Usage
-----
    # Train on all data in the DB:
    python scripts/train_model.py

    # Specify a date range:
    python scripts/train_model.py --start 2022-01-01 --end 2024-12-31

    # Quick smoke test on small dataset (fewer trees):
    python scripts/train_model.py --quick

Requirements
------------
  - The database must have at least a few hundred observation rows.
  - Run the ingestion pipeline first:
      python scripts/run_ingestion.py --mode realtime
  - Or run a historical backfill for ERA5 + OpenAQ data.
  - No external API keys are needed at training time.

Output
------
  data/models/pm25_t+1.joblib … pm25_t+72.joblib
  data/models/pm10_t+1.joblib … (and so on for pm10, o3, no2, aqi_computed)
  data/models/_meta.joblib      (feature names and metadata)
  Printed evaluation metrics (RMSE, MAE per target per horizon).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env", override=False)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train AeroAQI XGBoost forecasting model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--start",
        metavar="YYYY-MM-DD",
        default=None,
        help="Start date for training data (default: all data in DB)",
    )
    p.add_argument(
        "--end",
        metavar="YYYY-MM-DD",
        default=None,
        help="End date for training data (default: all data in DB)",
    )
    p.add_argument(
        "--model-dir",
        default=str(_PROJECT_ROOT / "data" / "models"),
        help="Directory to save trained models (default: data/models/)",
    )
    p.add_argument(
        "--test-fraction",
        type=float,
        default=0.2,
        help="Fraction of data to hold out for evaluation (default: 0.2)",
    )
    p.add_argument(
        "--quick",
        action="store_true",
        help="Use fewer trees and a smaller dataset for quick smoke testing",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        import pandas as pd
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        print(f"ERROR: Required package not installed: {exc}")
        print("Install with: pip install scikit-learn pandas")
        return 1

    try:
        from xgboost import XGBRegressor
    except ImportError:
        print("ERROR: xgboost not installed. Install with: pip install xgboost==2.1.1")
        return 1

    from src.storage.db_client import DBClient
    from src.models.feature_builder import FeatureBuilder
    from src.models.aqi_forecaster import AQIForecaster
    from src.utils.logger import get_logger

    log = get_logger("train_model")

    # ── Load observations ───────────────────────────────────────────────
    print("\nAeroAQI — Model Training")
    print("─" * 50)
    db = DBClient()

    from datetime import datetime, timezone
    start_time = None
    end_time = None
    if args.start:
        start_time = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    if args.end:
        end_time = datetime.fromisoformat(args.end).replace(hour=23, minute=59, tzinfo=timezone.utc)

    print(f"Loading observations from DB...")
    obs_df = db.read_observations(start_time=start_time, end_time=end_time)

    if obs_df.empty:
        print(
            "\nERROR: No observations in the database.\n"
            "Run the ingestion pipeline first:\n"
            "  python scripts/run_ingestion.py --mode realtime\n"
            "Or backfill historical data:\n"
            "  python scripts/run_ingestion.py --mode historical --start 2023-01-01 --end 2023-12-31"
        )
        return 1

    print(f"Loaded {len(obs_df):,} observation rows.")

    # Quick mode: subsample for speed
    if args.quick:
        obs_df = obs_df.tail(500).copy()
        print(f"Quick mode: using last {len(obs_df)} rows.")

    # ── Build features ──────────────────────────────────────────────────
    print("Building feature matrix...")
    fb = FeatureBuilder(target_hours=72)
    X, y_dict, feature_names = fb.build(obs_df)

    if X.empty or not y_dict:
        print(
            "\nERROR: Feature matrix is empty. This usually means the observations "
            "table has insufficient data (need at least 50+ rows per station)."
        )
        return 1

    print(f"Feature matrix: {X.shape[0]} rows × {X.shape[1]} features")
    print(f"Target columns: {len(y_dict)}")

    # ── Train/test split ────────────────────────────────────────────────
    n_test = max(1, int(len(X) * args.test_fraction))
    X_train, X_test = X.iloc[:-n_test], X.iloc[-n_test:]
    y_train_dict = {k: v.iloc[:-n_test] for k, v in y_dict.items()}
    y_test_dict = {k: v.iloc[-n_test:] for k, v in y_dict.items()}

    print(f"Train: {len(X_train)} rows, Test: {len(X_test)} rows")

    # ── Train model ─────────────────────────────────────────────────────
    model_params = None
    if args.quick:
        model_params = {
            "n_estimators": 20,
            "max_depth": 3,
            "learning_rate": 0.1,
            "objective": "reg:squarederror",
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": 0,
        }

    forecaster = AQIForecaster(target_hours=72, model_params=model_params)
    print("Training XGBoost models...")
    forecaster.fit(X_train, y_train_dict, feature_names=feature_names)
    print(f"Trained {forecaster.n_models} models.")

    # ── Evaluate ─────────────────────────────────────────────────────────
    print("\nEvaluation on held-out test set:")
    metrics = forecaster.evaluate(X_test, y_test_dict)

    if metrics:
        # Aggregate by target across all horizons
        from collections import defaultdict
        agg: dict[str, list] = defaultdict(list)
        for key, m in metrics.items():
            target = key.split("_t+")[0]
            agg[f"{target}_rmse"].append(m["rmse"])
            agg[f"{target}_mae"].append(m["mae"])

        print(f"  {'Target':<20} {'Mean RMSE':>10} {'Mean MAE':>10}")
        print("  " + "─" * 44)
        from src.models.feature_builder import FORECAST_TARGETS
        for tgt in FORECAST_TARGETS:
            rmse_vals = agg.get(f"{tgt}_rmse", [])
            mae_vals = agg.get(f"{tgt}_mae", [])
            if rmse_vals:
                print(
                    f"  {tgt:<20} "
                    f"{sum(rmse_vals)/len(rmse_vals):>10.2f} "
                    f"{sum(mae_vals)/len(mae_vals):>10.2f}"
                )
    else:
        print("  (insufficient test data for evaluation)")

    # ── Save ─────────────────────────────────────────────────────────────
    model_dir = Path(args.model_dir)
    forecaster.save(str(model_dir))
    print(f"\nModels saved to: {model_dir.resolve()}")
    print("\nTraining complete. Run the ingestion pipeline to generate forecasts:")
    print("  python scripts/run_ingestion.py --mode realtime")
    return 0


if __name__ == "__main__":
    sys.exit(main())
