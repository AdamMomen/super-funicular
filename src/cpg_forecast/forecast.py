"""Time-series forecasting: Holt-Winters, simple mean, naive, rolling MA, exponential smoothing."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing

logger = logging.getLogger(__name__)

MIN_POINTS_FOR_HOLTWINTERS = 30
MIN_POINTS_FOR_SEASONAL = 14  # Need at least 2 full seasonal periods for weekly
DEFAULT_ROLLING_WINDOW = 14
MIN_DAYS_FOR_WEEKLY_PATTERN = 14  # Need 2 weeks to estimate weekday pattern


def _weekly_pattern(series: pd.Series) -> np.ndarray | None:
    """Compute mean demand per weekday (Mon=0..Sun=6). Returns 7 values or None if insufficient data."""
    if len(series) < MIN_DAYS_FOR_WEEKLY_PATTERN:
        return None
    positive = series[series > 0]
    if len(positive) < 7:
        return None
    by_dow = positive.groupby(positive.index.dayofweek)
    pattern = np.zeros(7)
    for dow, grp in by_dow:
        pattern[int(dow)] = float(grp.mean())
    if np.any(pattern <= 0):
        # Fill any missing weekdays with overall mean
        overall = float(positive.mean())
        pattern[pattern <= 0] = overall
    return pattern


def _project_weekly_pattern(
    pattern: np.ndarray,
    series: pd.Series,
    horizon_days: int,
) -> np.ndarray:
    """Project weekly pattern for horizon_days starting the day after series ends."""
    start_dow = (series.index[-1].dayofweek + 1) % 7
    out = np.zeros(horizon_days)
    for i in range(horizon_days):
        out[i] = pattern[(start_dow + i) % 7]
    return out


@dataclass
class ForecastResult:
    """Result of a single-SKU forecast."""

    sku: str
    history: pd.Series
    forecast: pd.Series
    daily_avg: float
    forecast_90d_total: float
    forecast_std: float | None  # For safety stock calc
    model_used: str


ALGORITHMS = ("holt_winters", "simple_mean", "naive", "rolling_ma", "exp_smoothing")


def _make_forecast_series(series: pd.Series, values: np.ndarray, horizon_days: int) -> pd.Series:
    """Create forecast Series with correct dates."""
    forecast_dates = pd.date_range(
        start=series.index.max() + pd.Timedelta(days=1),
        periods=horizon_days,
        freq="D",
    )
    return pd.Series(values, index=forecast_dates)


def _fit_simple_mean(series: pd.Series, horizon_days: int, sku: str) -> ForecastResult:
    """Mean of positive values, with weekly seasonality when 14+ days of data."""
    positive = series[series > 0]
    daily_avg = float(positive.mean()) if len(positive) > 0 else float(series.mean())
    if daily_avg <= 0:
        daily_avg = 1.0

    pattern = _weekly_pattern(series)
    if pattern is not None:
        forecast_values = _project_weekly_pattern(pattern, series, horizon_days)
    else:
        forecast_values = np.full(horizon_days, daily_avg)

    forecast_series = _make_forecast_series(series, forecast_values, horizon_days)
    daily_avg_actual = float(forecast_series.mean())
    forecast_std = float(positive.std()) if len(positive) > 1 else None
    return ForecastResult(
        sku=sku,
        history=series,
        forecast=forecast_series,
        daily_avg=daily_avg_actual,
        forecast_90d_total=float(forecast_series.sum()),
        forecast_std=forecast_std,
        model_used="simple_mean",
    )


def _fit_naive(series: pd.Series, horizon_days: int, sku: str) -> ForecastResult:
    """Last week's pattern repeated, or last value if < 7 days. If last value is 0, use last non-zero or mean."""
    last_val = float(series.iloc[-1])
    if last_val < 0:
        last_val = 0.0

    # If last value is 0, use last non-zero or fall back to mean
    if last_val == 0:
        positive = series[series > 0]
        if len(positive) > 0:
            last_val = float(positive.iloc[-1])
        else:
            last_val = float(series.mean()) if series.mean() > 0 else 1.0

    if len(series) >= 7:
        # Use last 7 days as weekly pattern (naive seasonal)
        last_week = np.maximum(series.tail(7).values.astype(float), 0)
        if np.any(last_week > 0):
            fill = float(np.mean(last_week[last_week > 0]))
            pattern = np.where(last_week > 0, last_week, fill)
            forecast_values = _project_weekly_pattern(pattern, series, horizon_days)
        else:
            forecast_values = np.full(horizon_days, last_val)
    else:
        forecast_values = np.full(horizon_days, last_val)

    forecast_series = _make_forecast_series(series, forecast_values, horizon_days)
    daily_avg = float(forecast_series.mean())
    forecast_std = float(series.std()) if len(series) > 1 else None
    return ForecastResult(
        sku=sku,
        history=series,
        forecast=forecast_series,
        daily_avg=daily_avg,
        forecast_90d_total=float(forecast_series.sum()),
        forecast_std=forecast_std,
        model_used="naive",
    )


def _fit_rolling_ma(
    series: pd.Series,
    horizon_days: int,
    sku: str,
    window: int = DEFAULT_ROLLING_WINDOW,
) -> ForecastResult:
    """Mean of last N days, with weekly seasonality when window >= 14."""
    window = min(window, len(series))
    tail = series.tail(window)
    daily_avg = float(tail.mean())
    if daily_avg <= 0:
        daily_avg = 1.0

    if window >= 14:
        # Compute rolling mean per weekday from tail
        by_dow = tail.groupby(tail.index.dayofweek)
        pattern = np.zeros(7)
        for dow, grp in by_dow:
            pattern[int(dow)] = float(grp.mean())
        if np.any(pattern <= 0):
            pattern[pattern <= 0] = daily_avg
        forecast_values = _project_weekly_pattern(pattern, series, horizon_days)
    else:
        forecast_values = np.full(horizon_days, daily_avg)

    forecast_series = _make_forecast_series(series, forecast_values, horizon_days)
    daily_avg_actual = float(forecast_series.mean())
    forecast_std = float(tail.std()) if len(tail) > 1 else None
    return ForecastResult(
        sku=sku,
        history=series,
        forecast=forecast_series,
        daily_avg=daily_avg_actual,
        forecast_90d_total=float(forecast_series.sum()),
        forecast_std=forecast_std,
        model_used="rolling_ma",
    )


def _fit_exp_smoothing(series: pd.Series, horizon_days: int, sku: str) -> ForecastResult:
    """Simple exponential smoothing; apply weekly seasonality when 14+ days of data."""
    try:
        model = SimpleExpSmoothing(series)
        fitted = model.fit(optimized=True)
        level = float(fitted.level.iloc[-1]) if hasattr(fitted, "level") and len(fitted.level) > 0 else float(series.mean())
    except Exception as e:
        logger.warning("Exp smoothing failed (%s), falling back to simple mean", e)
        return _fit_simple_mean(series, horizon_days, sku)

    pattern = _weekly_pattern(series)
    if pattern is not None:
        # Scale pattern so mean = level, then project
        pattern_mean = float(np.mean(pattern))
        if pattern_mean > 0:
            scaled = pattern * (level / pattern_mean)
            forecast_values = _project_weekly_pattern(scaled, series, horizon_days)
        else:
            forecast_values = np.full(horizon_days, max(level, 0.1))
    else:
        forecast_values = np.full(horizon_days, max(level, 0.1))

    forecast_values = np.clip(forecast_values, 0, None)
    forecast_series = _make_forecast_series(series, forecast_values, horizon_days)
    daily_avg = float(forecast_series.mean())
    forecast_std = float(series.std()) if len(series) > 1 else None
    return ForecastResult(
        sku=sku,
        history=series,
        forecast=forecast_series,
        daily_avg=daily_avg,
        forecast_90d_total=float(forecast_series.sum()),
        forecast_std=forecast_std,
        model_used="exp_smoothing",
    )


def _fit_holt_winters(series: pd.Series, horizon_days: int, sku: str) -> ForecastResult:
    """Holt-Winters with additive trend and optional weekly seasonality."""
    if len(series) < MIN_POINTS_FOR_HOLTWINTERS:
        logger.warning(
            "Insufficient data for Holt-Winters (%d points), using simple mean",
            len(series),
        )
        return _fit_simple_mean(series, horizon_days, sku)

    try:
        if len(series) >= MIN_POINTS_FOR_SEASONAL:
            model = ExponentialSmoothing(
                series,
                trend="add",
                seasonal="add",
                seasonal_periods=7,
                initialization_method="estimated",
            )
        else:
            model = ExponentialSmoothing(
                series,
                trend="add",
                seasonal=None,
                initialization_method="estimated",
            )
        fitted = model.fit(optimized=True)
        forecast = fitted.forecast(steps=horizon_days)
    except Exception as e:
        logger.warning("Holt-Winters failed (%s), falling back to simple mean", e)
        return _fit_simple_mean(series, horizon_days, sku)

    forecast_values = np.clip(forecast.values, 0, None)
    forecast_series = _make_forecast_series(series, forecast_values, horizon_days)
    daily_avg = float(forecast_series.mean())
    forecast_std = float(series.std()) if len(series) > 1 else None
    return ForecastResult(
        sku=sku,
        history=series,
        forecast=forecast_series,
        daily_avg=daily_avg,
        forecast_90d_total=float(forecast_series.sum()),
        forecast_std=forecast_std,
        model_used="holt_winters",
    )


def fit_forecast(
    series: pd.Series,
    horizon_days: int = 90,
    sku: str = "",
    algorithm: str = "holt_winters",
    rolling_window: int = DEFAULT_ROLLING_WINDOW,
) -> ForecastResult:
    """Fit time-series model and produce forecast.

    Args:
        series: Time series of daily demand (DatetimeIndex).
        horizon_days: Forecast horizon in days.
        sku: SKU identifier for the result.
        algorithm: One of holt_winters, simple_mean, naive, rolling_ma, exp_smoothing.
        rolling_window: Window size for rolling_ma (default 14).

    Returns:
        ForecastResult with history, forecast, and summary stats.
    """
    series = series.copy()
    series = series.asfreq("D", fill_value=0)

    if algorithm not in ALGORITHMS:
        algorithm = "holt_winters"

    if algorithm == "holt_winters":
        return _fit_holt_winters(series, horizon_days, sku)
    if algorithm == "simple_mean":
        return _fit_simple_mean(series, horizon_days, sku)
    if algorithm == "naive":
        return _fit_naive(series, horizon_days, sku)
    if algorithm == "rolling_ma":
        return _fit_rolling_ma(series, horizon_days, sku, window=rolling_window)
    if algorithm == "exp_smoothing":
        return _fit_exp_smoothing(series, horizon_days, sku)

    return _fit_holt_winters(series, horizon_days, sku)


def forecast_all_skus(
    aggregated: dict[str, pd.Series],
    horizon_days: int = 90,
    algorithm: str = "holt_winters",
    rolling_window: int = DEFAULT_ROLLING_WINDOW,
) -> dict[str, ForecastResult]:
    """Forecast demand for all SKUs.

    Args:
        aggregated: Dict from ETL: sku -> demand series.
        horizon_days: Forecast horizon.
        algorithm: One of holt_winters, simple_mean, naive, rolling_ma, exp_smoothing.
        rolling_window: Window for rolling_ma.

    Returns:
        Dict mapping sku -> ForecastResult.
    """
    if algorithm not in ALGORITHMS:
        algorithm = "holt_winters"
    results: dict[str, ForecastResult] = {}
    for sku, series in aggregated.items():
        results[sku] = fit_forecast(
            series,
            horizon_days=horizon_days,
            sku=sku,
            algorithm=algorithm,
            rolling_window=rolling_window,
        )
    return results
