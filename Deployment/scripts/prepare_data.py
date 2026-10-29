"""
Rebuild data/cairo_target_2day.csv (the history behind the presets) from the preprocessed table:

    python scripts/prepare_data.py path/to/cairo_weather_preprocessed_2day.csv
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "cairo_weather_preprocessed_2day.csv"
frame = pd.read_csv(source, parse_dates=["date"]).sort_values("date")
frame[["date", "target_temperature_c"]].to_csv(ROOT / "data" / "cairo_target_2day.csv", index=False)
print("wrote", ROOT / "data" / "cairo_target_2day.csv", len(frame), "rows")
