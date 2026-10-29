"""Retrain the models:  python scripts/train_models.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from forecast.ml.training import train_and_save  # noqa: E402

if __name__ == "__main__":
    train_and_save(ROOT / "data" / "cairo_weather_model_ready_2day.csv", ROOT / "artifacts")
