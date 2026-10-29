"""
Train, evaluate and save the models served by the app.

Input : data/cairo_weather_model_ready_2day.csv  (output of the Preprocessing notebook)
Output: artifacts/<model>.joblib, artifacts/metadata.json, artifacts/holdout_predictions.csv

Run it with:  python scripts/train_models.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURE_ORDER, TARGET

HOLDOUT_DAYS = 21           # same chronological hold-out as the Preprocessing notebook
SEED = 42
RIDGE_ALPHAS = (0.1, 1, 10, 30, 100)


def _model_factories(ridge_alpha):
    return {
        "ridge": ("Ridge regression", lambda: make_pipeline(StandardScaler(), Ridge(alpha=ridge_alpha))),
        "random_forest": ("Random forest", lambda: RandomForestRegressor(
            n_estimators=300, min_samples_leaf=5, random_state=SEED, n_jobs=1)),
        "gradient_boosting": ("Gradient boosting", lambda: GradientBoostingRegressor(
            n_estimators=200, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=SEED)),
    }


def _cv_scores(factory, X, y, n_splits=5):
    """Expanding-window CV: always train on the past, test on the next block."""
    maes, residuals = [], []
    for train_idx, test_idx in TimeSeriesSplit(n_splits=n_splits).split(X):
        model = factory()
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        error = y.iloc[test_idx].to_numpy() - model.predict(X.iloc[test_idx])
        maes.append(float(np.mean(np.abs(error))))
        residuals.extend(error.tolist())
    return float(np.mean(maes)), np.asarray(residuals)


def train_and_save(model_ready_csv: Path, out_dir: Path, verbose: bool = True) -> dict:
    frame = pd.read_csv(model_ready_csv, parse_dates=["date"]).set_index("date").sort_index()
    X_all, y_all = frame[FEATURE_ORDER], frame[TARGET]

    split_date = frame.index.max() - pd.Timedelta(days=HOLDOUT_DAYS)
    train, test = frame[frame.index <= split_date], frame[frame.index > split_date]
    X_tr, y_tr, X_te, y_te = train[FEATURE_ORDER], train[TARGET], test[FEATURE_ORDER], test[TARGET]

    # choose the Ridge penalty by time-series CV on the TRAIN rows only (never on the hold-out)
    ridge_cv = {a: _cv_scores(_model_factories(a)["ridge"][1], X_tr, y_tr)[0] for a in RIDGE_ALPHAS}
    best_alpha = min(ridge_cv, key=ridge_cv.get)

    out_dir.mkdir(parents=True, exist_ok=True)
    registry, holdout = {}, pd.DataFrame({"actual": y_te})
    for key, (label, factory) in _model_factories(best_alpha).items():
        cv_mae, residuals = _cv_scores(factory, X_tr, y_tr)
        model = factory().fit(X_tr, y_tr)
        pred = model.predict(X_te)
        joblib.dump(model, out_dir / f"{key}.joblib", compress=3)
        holdout[key] = pred
        q = np.quantile(residuals, [0.025, 0.10, 0.90, 0.975])
        registry[key] = {
            "label": label, "file": f"{key}.joblib",
            "cv_mae": round(cv_mae, 4),
            "cv_rmse": round(float(np.sqrt(np.mean(residuals ** 2))), 4),
            "holdout_mae": round(float(mean_absolute_error(y_te, pred)), 4),
            "holdout_rmse": round(float(np.sqrt(mean_squared_error(y_te, pred))), 4),
            "residual_quantiles": {"q025": float(q[0]), "q10": float(q[1]), "q90": float(q[2]), "q975": float(q[3])},
        }
        if verbose:
            print(f"{label:18s} CV MAE {cv_mae:.3f} | hold-out MAE {registry[key]['holdout_mae']:.3f}")

    # reference baselines (not deployed): any model must beat them to be worth serving
    def cv_baseline(column):
        return float(np.mean([mean_absolute_error(y_tr.iloc[b], X_tr[column].iloc[b])
                              for _, b in TimeSeriesSplit(n_splits=5).split(X_tr)]))
    baselines = {
        "persistence": {"label": "Persistence (same as 2 days ago)", "cv_mae": round(cv_baseline(f"{TARGET}_lag_1"), 4),
                        "holdout_mae": round(float(mean_absolute_error(y_te, X_te[f"{TARGET}_lag_1"])), 4)},
        "seasonal_naive": {"label": "Seasonal naive (same day last year)", "cv_mae": round(cv_baseline(f"{TARGET}_lag_183"), 4),
                           "holdout_mae": round(float(mean_absolute_error(y_te, X_te[f"{TARGET}_lag_183"])), 4)},
    }

    default_key = min(registry, key=lambda k: registry[k]["cv_mae"])
    meta = {
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "target": TARGET, "feature_order": FEATURE_ORDER,
        "step_days": 2, "ridge_alpha": best_alpha,
        "train": {"rows": len(train), "start": str(train.index.min().date()), "end": str(train.index.max().date())},
        "holdout": {"rows": len(test), "start": str(test.index.min().date()), "end": str(test.index.max().date())},
        "target_range": {"min": float(y_tr.min()), "max": float(y_tr.max())},
        "default_model": default_key, "models": registry, "baselines": baselines,
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    holdout.to_csv(out_dir / "holdout_predictions.csv", index_label="date")
    if verbose:
        print(f"Default model: {registry[default_key]['label']} | alpha={best_alpha} | saved to {out_dir}")
    return meta
