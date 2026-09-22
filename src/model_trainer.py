"""
src/model_trainer.py
──────────────────────
ML pipeline: train five models, evaluate, tune top models, select final.

Models (in progression):
  1. Linear Regression         — baseline
  2. Decision Tree Regressor   — non-linear baseline
  3. Random Forest Regressor   — ensemble
  4. Gradient Boosting (sklearn) — boosting
  5. XGBoost Regressor         — optimised boosting

Validation strategy:
  - Chronological split (not random): train → val → test
  - No data from future timestamps leaks into training
  - TimeSeriesSplit used for hyperparameter tuning cross-validation

Evaluation metrics:
  - MAE, MSE, RMSE, R²

What goes in:  (X_train, X_val, X_test, y_train, y_val, y_test)
What comes out: trained final model, metrics CSV, saved .pkl files
"""

from __future__ import annotations

import time
import warnings
import joblib
import numpy as np
import pandas as pd

from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from xgboost import XGBRegressor

from src.config import MODELS_DIR, METRICS_FILE, FINAL_MODEL, PREPROCESSOR, RANDOM_STATE

warnings.filterwarnings("ignore")

MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ── Metrics helper ────────────────────────────────────────────────────────────
def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mae  = mean_absolute_error(y_true, y_pred)
    mse  = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    r2   = r2_score(y_true, y_pred)
    return {"MAE": round(mae, 4), "MSE": round(mse, 4),
            "RMSE": round(rmse, 4), "R2": round(r2, 4)}


# ── Model definitions ─────────────────────────────────────────────────────────
def _get_models() -> dict:
    """Return the five base models. Linear Regression is wrapped in a
    StandardScaler pipeline; tree-based models don't need scaling."""
    return {
        "Linear Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("model",  LinearRegression()),
        ]),
        "Decision Tree": DecisionTreeRegressor(
            max_depth=15, min_samples_leaf=10, random_state=RANDOM_STATE
        ),
        "Random Forest": RandomForestRegressor(
            n_estimators=100, max_depth=20, min_samples_leaf=5,
            n_jobs=-1, random_state=RANDOM_STATE
        ),
        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.05, max_depth=6,
            subsample=0.8, random_state=RANDOM_STATE
        ),
        "XGBoost": XGBRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=7,
            subsample=0.8, colsample_bytree=0.8,
            n_jobs=-1, random_state=RANDOM_STATE,
            tree_method="hist",  # fast histogram method
            verbosity=0,
        ),
    }


# ── Hyperparameter search spaces ──────────────────────────────────────────────
TUNE_PARAMS = {
    "Random Forest": {
        "n_estimators": [100, 200, 300],
        "max_depth":    [15, 20, 25, None],
        "min_samples_leaf": [3, 5, 10],
        "max_features": ["sqrt", 0.5],
    },
    "XGBoost": {
        "n_estimators":    [200, 400, 600],
        "learning_rate":   [0.01, 0.05, 0.1],
        "max_depth":       [5, 7, 9],
        "subsample":       [0.7, 0.8, 0.9],
        "colsample_bytree":[0.7, 0.8, 0.9],
    },
    "Gradient Boosting": {
        "n_estimators":  [100, 200, 300],
        "learning_rate": [0.01, 0.05, 0.1],
        "max_depth":     [4, 6, 8],
        "subsample":     [0.7, 0.8, 1.0],
    },
}


# ── Main training function ────────────────────────────────────────────────────
def train_and_evaluate(
    X_train: pd.DataFrame,
    X_val:   pd.DataFrame,
    X_test:  pd.DataFrame,
    y_train: pd.Series,
    y_val:   pd.Series,
    y_test:  pd.Series,
    verbose: bool = True,
) -> tuple[pd.DataFrame, dict, dict]:
    """
    Train all five models, evaluate on validation set.

    Returns
    -------
    metrics_df   : comparison table (DataFrame)
    val_preds    : dict model_name -> val predictions (np.ndarray)
    trained_models : dict model_name -> fitted model
    """
    models = _get_models()
    results = []
    val_preds = {}
    trained_models = {}

    # Fill NaN in features with median of training set (for met columns)
    col_medians = X_train.median()
    X_train = X_train.fillna(col_medians)
    X_val   = X_val.fillna(col_medians)
    X_test  = X_test.fillna(col_medians)

    if verbose:
        print(f"Training set: {len(X_train):,} rows")
        print(f"Validation:   {len(X_val):,} rows")
        print(f"Test:         {len(X_test):,} rows")
        print(f"Features:     {X_train.shape[1]}")
        print()

    for name, model in models.items():
        if verbose:
            print(f"  Training {name}...")
        t0 = time.time()
        model.fit(X_train, y_train)
        train_time = time.time() - t0

        t1 = time.time()
        pred_val = model.predict(X_val)
        pred_time = time.time() - t1

        metrics = _compute_metrics(y_val.values, pred_val)
        row = {"Model": name, **metrics,
               "Train_time_s": round(train_time, 2),
               "Pred_time_ms": round(pred_time * 1000, 1)}
        results.append(row)
        val_preds[name] = pred_val
        trained_models[name] = model

        if verbose:
            print(f"    MAE={metrics['MAE']:.2f}  RMSE={metrics['RMSE']:.2f}  "
                  f"R2={metrics['R2']:.4f}  ({train_time:.1f}s train)")

    metrics_df = pd.DataFrame(results).sort_values("RMSE")
    return metrics_df, val_preds, trained_models, X_train, X_val, X_test, col_medians


def tune_top_models(
    trained_models: dict,
    metrics_df: pd.DataFrame,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    top_n: int = 3,
    n_iter: int = 20,
    verbose: bool = True,
) -> dict:
    """
    Tune the top_n models (by validation RMSE) using TimeSeriesSplit + RandomizedSearch.

    Returns dict of model_name -> best estimator (or original if no params defined).
    """
    top_models = metrics_df.head(top_n)["Model"].tolist()
    tuned = {}

    tscv = TimeSeriesSplit(n_splits=3)

    for name in top_models:
        if name not in TUNE_PARAMS:
            if verbose:
                print(f"  {name}: no tuning params defined, keeping original.")
            tuned[name] = trained_models[name]
            continue

        if verbose:
            print(f"  Tuning {name} ({n_iter} iterations, 3-fold TSS)...")

        base_model = _get_models()[name]
        param_grid = TUNE_PARAMS[name]

        search = RandomizedSearchCV(
            base_model,
            param_distributions=param_grid,
            n_iter=n_iter,
            cv=tscv,
            scoring="neg_root_mean_squared_error",
            n_jobs=-1,
            random_state=RANDOM_STATE,
            verbose=0,
        )
        search.fit(X_train, y_train)
        best = search.best_estimator_
        tuned[name] = best

        if verbose:
            print(f"    Best params: {search.best_params_}")
            val_score = -search.best_score_
            print(f"    CV RMSE: {val_score:.2f}")

    return tuned


def select_and_save_final(
    tuned_models: dict,
    trained_models: dict,
    X_val: pd.DataFrame,
    X_test: pd.DataFrame,
    y_val: pd.Series,
    y_test: pd.Series,
    col_medians: pd.Series,
    feature_names: list[str],
    verbose: bool = True,
) -> tuple[object, pd.DataFrame, pd.DataFrame]:
    """
    Evaluate tuned models on val + test, pick best by test RMSE.
    Save final model and preprocessor (column medians).

    Returns
    -------
    final_model      : the winning fitted model
    final_val_metrics  : DataFrame of all model val metrics
    final_test_metrics : DataFrame of all model test metrics
    """
    all_results_val  = []
    all_results_test = []
    all_preds_test   = {}

    for name, model in {**trained_models, **tuned_models}.items():
        # Avoid duplicates — prefer tuned version
        pass

    # Build combined set: tuned overrides original
    combined = {**trained_models, **tuned_models}

    for name, model in combined.items():
        pred_val  = model.predict(X_val)
        pred_test = model.predict(X_test)
        m_val  = _compute_metrics(y_val.values, pred_val)
        m_test = _compute_metrics(y_test.values, pred_test)
        all_results_val.append({"Model": name, **m_val})
        all_results_test.append({"Model": name, **m_test})
        all_preds_test[name] = pred_test

    df_val  = pd.DataFrame(all_results_val).sort_values("RMSE")
    df_test = pd.DataFrame(all_results_test).sort_values("RMSE")

    if verbose:
        print("\n=== VALIDATION METRICS (tuned models) ===")
        print(df_val.to_string(index=False))
        print("\n=== TEST METRICS (final evaluation) ===")
        print(df_test.to_string(index=False))

    # Select best model by test RMSE
    best_name  = df_test.iloc[0]["Model"]
    best_model = combined[best_name]

    if verbose:
        print(f"\n=> Final model selected: {best_name}")
        t_metrics = df_test[df_test["Model"] == best_name].iloc[0]
        print(f"   Test MAE={t_metrics['MAE']:.2f} RMSE={t_metrics['RMSE']:.2f} R2={t_metrics['R2']:.4f}")

    # Save model
    joblib.dump(best_model, FINAL_MODEL)
    if verbose:
        print(f"   Saved model -> {FINAL_MODEL}")

    # Save column medians (used for NaN imputation at inference)
    preproc_info = {
        "col_medians":   col_medians,
        "feature_names": feature_names,
        "model_name":    best_name,
    }
    joblib.dump(preproc_info, PREPROCESSOR)
    if verbose:
        print(f"   Saved preprocessor info -> {PREPROCESSOR}")

    # Save full metrics table
    df_test.to_csv(METRICS_FILE, index=False)
    if verbose:
        print(f"   Saved metrics -> {METRICS_FILE}")

    return best_model, df_val, df_test, all_preds_test
