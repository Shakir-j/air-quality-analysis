from pathlib import Path
from datetime import datetime
import gc
import json
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.features import build_features
from src.model_trainer import _get_models, _compute_metrics

DATA_PATH = ROOT / "data" / "processed" / "air_quality_processed.parquet"
MODELS_DIR = ROOT / "models"
MAX_TRAIN_ROWS = 800_000
RANDOM_STATE = 42


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Processed dataset not found: {DATA_PATH}")

    print("AIRWISE: timestamp-aligned candidate training")
    print("Production model files will not be modified.")

    raw_df = pd.read_parquet(DATA_PATH)
    print(f"Loaded {len(raw_df):,} processed rows.")

    X, y, meta = build_features(raw_df, verbose=True)
    del raw_df
    gc.collect()

    timestamps = pd.to_datetime(meta["timestamp"], errors="coerce")
    valid = timestamps.notna() & y.notna()

    X = X.loc[valid].reset_index(drop=True)
    y = y.loc[valid].reset_index(drop=True)
    meta = meta.loc[valid].reset_index(drop=True)

    timestamps = pd.to_datetime(meta["timestamp"], errors="coerce")
    order = np.argsort(timestamps.to_numpy(), kind="stable")

    X = X.iloc[order].reset_index(drop=True)
    y = y.iloc[order].reset_index(drop=True)
    meta = meta.iloc[order].reset_index(drop=True)
    timestamps = pd.to_datetime(meta["timestamp"], errors="coerce")

    unique_times = pd.DatetimeIndex(timestamps.unique()).sort_values()
    if len(unique_times) < 100:
        raise ValueError("Not enough unique timestamps for a reliable chronological split.")

    # Define global chronological windows: 70% train, 15% validation, 15% test.
    validation_start = unique_times[int(len(unique_times) * 0.70)]
    test_start = unique_times[int(len(unique_times) * 0.85)]

    train_mask = (timestamps < validation_start).to_numpy()
    validation_mask = (
        (timestamps >= validation_start) & (timestamps < test_start)
    ).to_numpy()
    test_mask = (timestamps >= test_start).to_numpy()

    train_idx_all = np.flatnonzero(train_mask)
    validation_idx = np.flatnonzero(validation_mask)
    test_idx = np.flatnonzero(test_mask)

    if min(len(train_idx_all), len(validation_idx), len(test_idx)) == 0:
        raise ValueError("Chronological split produced an empty partition.")

    available_train_rows = len(train_idx_all)

    # Deterministic row sample to keep candidate training more manageable
    # on an 8 GB machine. Validation and test periods remain unsampled.
    if len(train_idx_all) > MAX_TRAIN_ROWS:
        rng = np.random.default_rng(RANDOM_STATE)
        train_idx = np.sort(
            rng.choice(train_idx_all, size=MAX_TRAIN_ROWS, replace=False)
        )
    else:
        train_idx = train_idx_all

    print("\nChronological split:")
    print(f"  Training period:   before {validation_start}")
    print(f"  Validation period: {validation_start} to before {test_start}")
    print(f"  Test period:       {test_start} onward")
    print(f"  Available train rows: {available_train_rows:,}")
    print(f"  Train rows used:     {len(train_idx):,}")
    print(f"  Validation rows:     {len(validation_idx):,}")
    print(f"  Test rows:           {len(test_idx):,}")

    X_train = X.iloc[train_idx].copy()
    X_validation = X.iloc[validation_idx].copy()
    X_test = X.iloc[test_idx].copy()

    y_train = y.iloc[train_idx].to_numpy(dtype=np.float32)
    y_validation = y.iloc[validation_idx].to_numpy(dtype=np.float32)
    y_test = y.iloc[test_idx].to_numpy(dtype=np.float32)

    del X, y, meta, timestamps
    del train_mask, validation_mask, test_mask
    del train_idx_all, train_idx, validation_idx, test_idx, order
    gc.collect()

    # Normalize invalid numeric values and convert each frame safely.
    # Reassign the converted DataFrames instead of setting through frame[:].
    X_train = X_train.replace([np.inf, -np.inf], np.nan).astype(np.float32)
    X_validation = X_validation.replace([np.inf, -np.inf], np.nan).astype(np.float32)
    X_test = X_test.replace([np.inf, -np.inf], np.nan).astype(np.float32)

    feature_names = list(X_train.columns)
    if list(X_validation.columns) != feature_names or list(X_test.columns) != feature_names:
        raise ValueError("Training, validation and test feature columns do not match.")

    col_medians = X_train.median(axis=0, numeric_only=True)
    if col_medians.isna().any():
        missing = col_medians[col_medians.isna()].index.tolist()
        raise ValueError(f"Features have no usable training median: {missing}")

    X_train = X_train.fillna(col_medians)
    X_validation = X_validation.fillna(col_medians)
    X_test = X_test.fillna(col_medians)

    print(f"\nFeatures: {len(feature_names)}")
    print("Training XGBoost candidate; this can use substantial CPU and RAM.")

    models = _get_models()
    if "XGBoost" not in models:
        raise KeyError("The existing model definitions do not contain 'XGBoost'.")

    model = models["XGBoost"]
    model.set_params(n_jobs=min(4, os.cpu_count() or 1))

    start = time.time()
    model.fit(X_train, y_train, verbose=False)
    training_seconds = round(time.time() - start, 2)

    # Validation is evaluated first. The fixed candidate is not selected
    # or tuned using the test results.
    validation_pred = model.predict(X_validation)
    validation_metrics = _compute_metrics(y_validation, validation_pred)
    print("\nValidation metrics:")
    print(json.dumps(validation_metrics, indent=2))

    # One final held-out evaluation for this fixed candidate.
    test_pred = model.predict(X_test)
    test_metrics = _compute_metrics(y_test, test_pred)
    print("\nFinal test metrics:")
    print(json.dumps(test_metrics, indent=2))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = MODELS_DIR / f"candidate_validation_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=False)

    preprocessor_info = {
        "col_medians": col_medians,
        "feature_names": feature_names,
        "model_name": "XGBoost (timestamp-aligned candidate)",
    }

    joblib.dump(model, output_dir / "candidate_model.pkl")
    joblib.dump(preprocessor_info, output_dir / "candidate_preprocessor.pkl")

    metrics_table = pd.DataFrame([
        {"Split": "Validation", "Rows": len(y_validation), **validation_metrics},
        {"Split": "Test", "Rows": len(y_test), **test_metrics},
    ])
    metrics_table.to_csv(output_dir / "candidate_metrics.csv", index=False)

    summary = {
        "model": "XGBoost",
        "status": "candidate_only_not_promoted",
        "target": "PM2.5 at target timestamp t",
        "feature_alignment": (
            "Historical pollutant lags and meteorology use the exact preceding "
            "clock-hour where required."
        ),
        "split_policy": "Chronological 70/15/15 by unique timestamp",
        "validation_start": str(validation_start),
        "test_start": str(test_start),
        "available_training_rows": available_train_rows,
        "training_rows_used": len(y_train),
        "validation_rows": len(y_validation),
        "test_rows": len(y_test),
        "max_training_rows": MAX_TRAIN_ROWS,
        "feature_count": len(feature_names),
        "training_seconds": training_seconds,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "production_model_replaced": False,
    }

    (output_dir / "training_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    # Verify that the saved candidate can be loaded and make a finite prediction.
    reloaded_model = joblib.load(output_dir / "candidate_model.pkl")
    probe = np.asarray(reloaded_model.predict(X_test.iloc[:1])).reshape(-1)
    if len(probe) != 1 or not np.isfinite(probe[0]):
        raise RuntimeError("Saved candidate failed the inference smoke test.")

    print("\nCandidate saved successfully.")
    print(f"Output folder: {output_dir}")
    print("Files: candidate_model.pkl, candidate_preprocessor.pkl,")
    print("       candidate_metrics.csv, training_summary.json")
    print(f"Inference smoke test: PASS (prediction={float(probe[0]):.2f} µg/m³)")
    print("The active production model and production metrics were not replaced.")


if __name__ == "__main__":
    main()
