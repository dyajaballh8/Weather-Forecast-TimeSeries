"""
Read-only access to the Cairo temperature history (data/cairo_target_2day.csv).

It powers the "load real data" presets and the "observed value" hint. The history is a
regular 2-day grid, so the features for any date are plain look-ups on integer positions.
"""
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
from django.conf import settings

from .features import INPUT_ORDER, STEP_DAYS, TARGET

MAX_LAG = 183  # the longest feature look-back; earlier dates have no complete feature row


@lru_cache(maxsize=1)
def load_series() -> pd.Series:
    frame = pd.read_csv(settings.DATA_DIR / "cairo_target_2day.csv", parse_dates=["date"])
    return frame.set_index("date")[TARGET].sort_index()


def first_date() -> date:
    return load_series().index[0].date()


def last_date() -> date:
    return load_series().index[-1].date()


def _position(d: date):
    """Integer position of ``d`` on the 2-day grid (may point past the end), or None if off-grid."""
    delta = (d - first_date()).days
    if delta < 0 or delta % STEP_DAYS:
        return None
    return delta // STEP_DAYS


def _inputs_at(position: int, decimals=2) -> dict:
    """The six inputs for the grid position (rounded for the UI; ``decimals=None`` keeps full precision)."""
    s = load_series()
    values = {
        "temp_2d_ago": s.iloc[position - 1],
        "temp_24d_ago": s.iloc[position - 12],
        "temp_1y_ago": s.iloc[position - 183],
        "avg_8d": s.iloc[position - 4: position].mean(),
        "avg_30d": s.iloc[position - 15: position].mean(),
        "avg_62d": s.iloc[position - 31: position].mean(),
    }
    return {k: (float(values[k]) if decimals is None else round(float(values[k]), decimals)) for k in INPUT_ORDER}


def inputs_for_date(d: date):
    """Real inputs for forecasting ``d``, or None when the date is off-grid / too early / too late."""
    position = _position(d)
    n = len(load_series())
    if position is None or position < MAX_LAG or position > n:
        return None
    return {"forecast_date": d.isoformat(), **_inputs_at(position)}


def latest_inputs() -> dict:
    """Inputs for the next, not-yet-observed forecast date (last observation + 2 days)."""
    return inputs_for_date(last_date() + timedelta(days=STEP_DAYS))


def observed_value(d: date):
    """The value recorded for ``d`` if it is part of the history, else None."""
    position = _position(d)
    s = load_series()
    if position is None or position >= len(s):
        return None
    return float(s.iloc[position])


def sample_dates(count: int = 8):
    """Dropdown entries: the next forecast date first, then the most recent observed dates."""
    nxt = last_date() + timedelta(days=STEP_DAYS)
    entries = [{"value": nxt.isoformat(), "label": f"{nxt:%d %b %Y} · next forecast (not observed yet)"}]
    s = load_series()
    for ts in reversed(s.index[-count:]):
        d = ts.date()
        entries.append({"value": d.isoformat(), "label": f"{d:%d %b %Y} · observed {s[ts]:.1f} °C"})
    return entries
