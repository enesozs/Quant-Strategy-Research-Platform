"""Convert pandas/numpy research output into JSON-safe structures.

Every non-finite float (NaN, +/-inf) becomes None, timestamps become ISO
dates and numpy scalars become plain Python values.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
import pandas as pd


def to_date_string(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def clean_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def to_jsonable(value: Any) -> Any:
    """Recursively convert a value into something json.dumps accepts strictly."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return clean_float(value)
    if isinstance(value, (pd.Timestamp, dt.datetime, dt.date, np.datetime64)):
        return to_date_string(value)
    if value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, pd.DataFrame):
        return frame_to_rows(value)
    if isinstance(value, pd.Series):
        return [to_jsonable(item) for item in value.tolist()]
    if isinstance(value, np.ndarray):
        return [to_jsonable(item) for item in value.tolist()]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (pd.Timedelta, dt.timedelta)):
        return str(value)
    return str(value)


def frame_to_rows(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    """DataFrame -> list of JSON-safe row dicts (the index is dropped)."""
    if frame is None or frame.empty:
        return []
    return [
        {str(key): to_jsonable(item) for key, item in record.items()}
        for record in frame.to_dict(orient="records")
    ]


def _numeric_column(series: pd.Series) -> list[float | None]:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    return [float(item) if math.isfinite(item) else None for item in values]


def to_timeseries(
    frame: pd.DataFrame | pd.Series | None,
    columns: Iterable[str] | Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build the contract's TimeSeries: {dates, columns: {name: [Num]}}.

    ``columns`` may be a list of names (missing ones are skipped) or a mapping
    of source column -> output name.
    """
    if frame is None:
        return {"dates": [], "columns": {}}
    if isinstance(frame, pd.Series):
        frame = frame.to_frame(name=str(frame.name or "value"))

    if columns is None:
        mapping = {str(name): str(name) for name in frame.columns}
    elif isinstance(columns, Mapping):
        mapping = dict(columns)
    else:
        mapping = {name: name for name in columns}

    dates = [pd.Timestamp(item).strftime("%Y-%m-%d") for item in frame.index]
    output: dict[str, list[float | None]] = {}
    for source, target in mapping.items():
        if source in frame.columns:
            output[target] = _numeric_column(frame[source])

    return {"dates": dates, "columns": output}


METRIC_KEYS = (
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "max_drawdown",
    "calmar_ratio",
    "final_value",
    "rebalancing_days",
    "turnover",
    "average_exposure",
)


def metrics_to_json(metrics: Mapping[str, Any]) -> dict[str, float | None]:
    """Return the Metrics shape: the core keys always present, optional ones if given."""
    output: dict[str, float | None] = {}
    for key in METRIC_KEYS[:6]:
        output[key] = clean_float(metrics.get(key))
    for key in METRIC_KEYS[6:]:
        if key in metrics:
            output[key] = clean_float(metrics[key])
    return output
