"""
scripts/run_training.py
────────────────────────
Entry-point for the ML pipeline.

Steps:
  1. Load processed data
  2. Build feature matrix (lag, rolling, temporal, co-pollutant features)
  3. Chronological train/val/test split
  4. Train 5 models
  5. Tune top 3 models
  6. Select and save final model
  7. Save metrics

Usage:
    python scripts/run_training.py
    python scripts/run_training.py --no-tune   # skip hyperparameter tuning (faster)
"""

import sys
import os
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.preprocessor import load_processed
from src.features import build_features, time_aware_split
from src.model_trainer import train_and_evaluate, tune_top_models, select_and_save_final
from src.config import TRAIN_END_DATE, VAL_END_DATE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-tune", action="store_true",
                        help="Skip hyperparameter tuning (faster for development).")
    parser.add_argument("--n-iter", type=int, default=20,
                        help="Number of iterations for RandomizedSearchCV (default: 20).")
    args = parser.parse_args()

    # ── 1. Load ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print("PHASE 4+5+6: Feature Engineering + Model Training")
    print("=" * 60)
    print()
    print("Loading processed data...")
    df = load_processed()
    print(f"  {len(df):,} rows, {len(df.columns)} columns")
    print()

    # ── 2. Feature engineering ────────────────────────────────────────────────
    print("Building features...")
    X, y, meta = build_features(df, verbose=True)
    print()

    # ── 3. Time-aware split ───────────────────────────────────────────────────
    print(f"Time-aware split:")
    print(f"  Train : start -> {TRAIN_END_DATE}")
    print(f"  Val   : {TRAIN_END_DATE} -> {VAL_END_DATE}")
    print(f"  Test  : {VAL_END_DATE} -> end")

    (X_train, X_val, X_test,
     y_train, y_val, y_test,
     meta_train, meta_val, meta_test) = time_aware_split(
        X, y, meta, TRAIN_END_DATE, VAL_END_DATE
    )
    print(f"  Train rows: {len(X_train):,}  |  "
          f"Val rows: {len(X_val):,}  |  "
          f"Test rows: {len(X_test):,}")
    print()

    # ── 4. Train 5 models ─────────────────────────────────────────────────────
    print("Training 5 models (validation metrics)...")
    (metrics_df, val_preds, trained_models,
     X_train, X_val, X_test, col_medians) = train_and_evaluate(
        X_train, X_val, X_test,
        y_train, y_val, y_test,
        verbose=True,
    )
    print()
    print("=== INITIAL MODEL COMPARISON (sorted by RMSE) ===")
    print(metrics_df.to_string(index=False))
    print()

    # ── 5. Tune top 3 models ──────────────────────────────────────────────────
    if not args.no_tune:
        print("Tuning top 3 models...")
        tuned_models = tune_top_models(
            trained_models, metrics_df,
            X_train, y_train,
            top_n=3, n_iter=args.n_iter, verbose=True,
        )
        print()
    else:
        print("Skipping tuning (--no-tune).")
        tuned_models = {}

    # ── 6. Select + save final model ──────────────────────────────────────────
    print("Selecting final model...")
    (final_model, df_val_metrics, df_test_metrics, test_preds) = select_and_save_final(
        tuned_models=tuned_models,
        trained_models=trained_models,
        X_val=X_val,
        X_test=X_test,
        y_val=y_val,
        y_test=y_test,
        col_medians=col_medians,
        feature_names=list(X_train.columns),
        verbose=True,
    )

    print()
    print("=" * 60)
    print("Training complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
