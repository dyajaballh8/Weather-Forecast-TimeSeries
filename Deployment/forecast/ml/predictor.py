"""
Model loading and prediction.

* ``ModelRegistry`` loads every trained model ONCE (called from ``ForecastConfig.ready``).
* ``forecast()`` is the single entry point used by the HTML view and the JSON API.
* Identical requests are answered from an in-memory LRU cache.
"""
import json
import logging
import threading
from dataclasses import dataclass, replace
from datetime import date
from functools import lru_cache

import joblib
from django.conf import settings

from .features import INPUT_ORDER, build_feature_row

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Holds the fitted scikit-learn pipelines and their metadata."""

    def __init__(self):
        self._lock = threading.Lock()
        self.loaded = False
        self.models = {}
        self.meta = {}

    def load(self, force: bool = False):
        with self._lock:
            if self.loaded and not force:
                return self
            meta_path = settings.ARTIFACTS_DIR / "metadata.json"
            self.meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.models = {
                key: joblib.load(settings.ARTIFACTS_DIR / info["file"])
                for key, info in self.meta["models"].items()
            }
            self.loaded = True
            _cached_forecast.cache_clear()
            logger.info("Loaded %d models: %s", len(self.models), ", ".join(self.models))
        return self

    def ensure_loaded(self):
        return self if self.loaded else self.load()

    @property
    def default_key(self) -> str:
        return self.meta["default_model"]

    def choices(self):
        """[(key, label)] for the model dropdown, best model first."""
        order = sorted(self.meta["models"].items(), key=lambda kv: kv[1]["cv_mae"])
        return [(key, f'{info["label"]}  (CV MAE {info["cv_mae"]:.2f} °C)') for key, info in order]


_registry = ModelRegistry()


def get_registry() -> ModelRegistry:
    return _registry


@dataclass(frozen=True)
class Forecast:
    value: float
    low80: float
    high80: float
    low95: float
    high95: float
    model_key: str
    model_label: str
    cv_mae: float
    cached: bool = False


@lru_cache(maxsize=512)
def _cached_forecast(model_key: str, date_iso: str, values: tuple) -> Forecast:
    registry = get_registry().ensure_loaded()
    inputs = dict(zip(INPUT_ORDER, values))
    row = build_feature_row(date.fromisoformat(date_iso), inputs)
    value = float(registry.models[model_key].predict(row)[0])
    info = registry.meta["models"][model_key]
    q = info["residual_quantiles"]  # empirical quantiles of (actual - predicted) from time-series CV
    return Forecast(
        value=value,
        low80=value + q["q10"], high80=value + q["q90"],
        low95=value + q["q025"], high95=value + q["q975"],
        model_key=model_key, model_label=info["label"], cv_mae=info["cv_mae"],
    )


def forecast(model_key: str, forecast_date: date, inputs: dict) -> Forecast:
    """Predict the temperature for ``forecast_date`` from the six recent-temperature inputs."""
    values = tuple(float(inputs[k]) for k in INPUT_ORDER)      # exact floats: cache key == what the model sees
    hits_before = _cached_forecast.cache_info().hits
    result = _cached_forecast(model_key, forecast_date.isoformat(), values)
    return replace(result, cached=_cached_forecast.cache_info().hits > hits_before)


def describe_band(value: float) -> dict:
    """Colour / icon / wording for the result panel."""
    if value < 15:
        return {"key": "cool", "label": "Cool", "icon": "bi-snow2", "hint": "bring a jacket"}
    if value < 22:
        return {"key": "mild", "label": "Mild", "icon": "bi-cloud-sun", "hint": "comfortable weather"}
    if value < 30:
        return {"key": "warm", "label": "Warm", "icon": "bi-sun", "hint": "light clothes, stay hydrated"}
    return {"key": "hot", "label": "Hot", "icon": "bi-thermometer-sun", "hint": "avoid the midday sun"}
