"""
Feature engineering used at *serving* time.

It mirrors the Preprocessing notebook exactly (same names, same formulas), so a row
built here is identical to a row of ``cairo_weather_model_ready_2day.csv``.
`tests/test_parity.py` proves it for every one of the 872 model-ready rows.

The series is sampled every 2 days, therefore one "lag" is one 2-day step.
"""
import math
from datetime import date

import pandas as pd

TARGET = "target_temperature_c"
STEP_DAYS = 2

# Order matters: it is the column order the models were trained with.
FEATURE_ORDER = [
    "day_of_year_sin",
    "day_of_year_cos",
    f"{TARGET}_lag_1",           # 2 days before the forecast date
    f"{TARGET}_lag_12",          # 24 days before
    f"{TARGET}_lag_183",         # about one year before (366 days)
    f"{TARGET}_roll_mean_4",     # mean of the previous 4 readings  (8 days)
    f"{TARGET}_roll_mean_15",    # mean of the previous 15 readings (30 days)
    f"{TARGET}_roll_mean_31",    # mean of the previous 31 readings (62 days)
]

# user-facing form field  ->  model feature
INPUT_TO_FEATURE = {
    "temp_2d_ago": f"{TARGET}_lag_1",
    "temp_24d_ago": f"{TARGET}_lag_12",
    "temp_1y_ago": f"{TARGET}_lag_183",
    "avg_8d": f"{TARGET}_roll_mean_4",
    "avg_30d": f"{TARGET}_roll_mean_15",
    "avg_62d": f"{TARGET}_roll_mean_31",
}
INPUT_ORDER = list(INPUT_TO_FEATURE)


def calendar_features(forecast_date: date) -> dict:
    """Cyclical encoding of the day of the year (Dec 31 sits next to Jan 1)."""
    day_of_year = forecast_date.timetuple().tm_yday
    angle = 2 * math.pi * day_of_year / 365.25
    return {"day_of_year_sin": math.sin(angle), "day_of_year_cos": math.cos(angle)}


def build_feature_row(forecast_date: date, inputs: dict) -> pd.DataFrame:
    """One-row DataFrame, columns in FEATURE_ORDER, ready for ``model.predict``."""
    row = calendar_features(forecast_date)
    for field, feature in INPUT_TO_FEATURE.items():
        row[feature] = float(inputs[field])
    return pd.DataFrame([row], columns=FEATURE_ORDER)
