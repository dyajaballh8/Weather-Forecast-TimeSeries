"""
Model-integration tests: the app must give the same numbers as the notebook / training script.

1. Serving features == the rows of the Preprocessing notebook's model-ready CSV (all 872 rows).
2. Models are loaded once and reused.
3. App predictions == the models called directly == holdout_predictions.csv written at training time.
"""
import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.test import SimpleTestCase

from forecast.ml import history
from forecast.ml.features import FEATURE_ORDER, INPUT_ORDER, TARGET, build_feature_row
from forecast.ml.predictor import forecast, get_registry

MODEL_READY = settings.DATA_DIR / "cairo_weather_model_ready_2day.csv"


def _model_ready():
    return pd.read_csv(MODEL_READY, parse_dates=["date"]).set_index("date")


class FeatureParityTests(SimpleTestCase):
    def test_serving_features_match_all_model_ready_rows(self):
        frame = _model_ready()
        self.assertEqual(len(frame), 872)
        worst = 0.0
        for ts, expected in frame.iterrows():
            d = ts.date()
            position = history._position(d)
            built = build_feature_row(d, history._inputs_at(position, decimals=None))
            diff = np.abs(built.iloc[0].to_numpy(dtype=float) - expected[FEATURE_ORDER].to_numpy(dtype=float)).max()
            worst = max(worst, diff)
        self.assertLess(worst, 1e-9, f"serving features differ from the notebook by up to {worst}")

    def test_history_target_matches_model_ready_target(self):
        frame = _model_ready()
        series = history.load_series()
        self.assertTrue(np.allclose(series.loc[frame.index].to_numpy(), frame[TARGET].to_numpy(), atol=1e-3))


class RegistryTests(SimpleTestCase):
    def test_models_are_loaded_once(self):
        registry = get_registry().ensure_loaded()
        before = {key: id(model) for key, model in registry.models.items()}
        registry.load()                                  # second call must be a no-op
        self.assertEqual(before, {key: id(model) for key, model in registry.models.items()})
        self.assertEqual(set(before), {"ridge", "random_forest", "gradient_boosting"})

    def test_default_model_is_the_best_by_cv(self):
        meta = get_registry().ensure_loaded().meta
        best = min(meta["models"], key=lambda k: meta["models"][k]["cv_mae"])
        self.assertEqual(meta["default_model"], best)


class PredictionParityTests(SimpleTestCase):
    def test_app_equals_direct_model_equals_training_output(self):
        registry = get_registry().ensure_loaded()
        frame = _model_ready()
        holdout = pd.read_csv(settings.ARTIFACTS_DIR / "holdout_predictions.csv", parse_dates=["date"]).set_index("date")
        self.assertEqual(len(holdout), registry.meta["holdout"]["rows"])
        for key in registry.models:
            direct_model = joblib.load(settings.ARTIFACTS_DIR / registry.meta["models"][key]["file"])
            for ts in holdout.index:
                d = ts.date()
                inputs = history._inputs_at(history._position(d), decimals=None)
                app_value = forecast(key, d, inputs).value
                direct_value = float(direct_model.predict(frame.loc[[ts], FEATURE_ORDER])[0])
                self.assertAlmostEqual(app_value, direct_value, places=9, msg=f"{key} {d}")
                self.assertAlmostEqual(app_value, float(holdout.loc[ts, key]), places=9, msg=f"{key} {d} vs training")

    def test_hold_out_error_is_sensible(self):
        meta = get_registry().ensure_loaded().meta
        for info in meta["models"].values():
            self.assertLess(info["holdout_mae"], 2.0)

    def test_identical_requests_are_served_from_cache(self):
        d = history.last_date()
        inputs = history._inputs_at(history._position(d), decimals=None)
        forecast("ridge", d, {**inputs, "avg_8d": inputs["avg_8d"] + 0.123})      # warm the cache
        again = forecast("ridge", d, {**inputs, "avg_8d": inputs["avg_8d"] + 0.123})
        self.assertTrue(again.cached)
        self.assertEqual(set(INPUT_ORDER), set(inputs))
