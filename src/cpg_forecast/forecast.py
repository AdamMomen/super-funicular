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
    """Mean of positive historical values only (avoids zero dilution)."""
    positive = series[series > 0]
    daily_avg = float(positive.mean()) if len(positive) > 0 else float(series.mean())
    if daily_avg <= 0:
        daily_avg = 1.0
    forecast_values = np.full(horizon_days, daily_avg)
    forecast_series = _make_forecast_series(series, forecast_values, horizon_days)
    forecast_std = float(positive.std()) if len(positive) > 1 else None
    return ForecastResult(
        sku=sku,
        history=series,
        forecast=forecast_series,
        daily_avg=daily_avg,
        forecast_90d_total=float(forecast_series.sum()),
        forecast_std=forecast_std,
        model_used="simple_mean",
    )


def _fit_naive(series: pd.Series, horizon_days: int, sku: str) -> ForecastResult:
    """Last observed value, repeated for horizon."""
    last_val = float(series.iloc[-1])
    if last_val < 0:
        last_val = 0.0
    forecast_values = np.full(horizon_days, last_val)
    forecast_series = _make_forecast_series(series, forecast_values, horizon_days)
    daily_avg = last_val
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
    """Mean of last N days."""
    window = min(window, len(series))
    tail = series.tail(window)
    daily_avg = float(tail.mean())
    if daily_avg <= 0:
        daily_avg = 1.0
    forecast_values = np.full(horizon_days, daily_avg)
    forecast_series = _make_forecast_series(series, forecast_values, horizon_days)
    forecast_std = float(tail.std()) if len(tail) > 1 else None
    return ForecastResult(
        sku=sku,
        history=series,
        forecast=forecast_series,
        daily_avg=daily_avg,
        forecast_90d_total=float(forecast_series.sum()),
        forecast_std=forecast_std,
        model_used="rolling_ma",
    )


def _fit_exp_smoothing(series: pd.Series, horizon_days: int, sku: str) -> ForecastResult:
    """Simple exponential smoothing from statsmodels."""
    try:
        model = SimpleExpSmoothing(series)
        fitted = model.fit(optimized=True)
        forecast = fitted.forecast(steps=horizon_days)
        forecast_values = np.clip(forecast.values, 0, None)
    except Exception as e:
        logger.warning("Exp smoothing failed (%s), falling back to simple mean", e)
        return _fit_simple_mean(series, horizon_days, sku)

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
