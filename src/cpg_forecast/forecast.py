"""Time-series forecasting using Holt-Winters exponential smoothing."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

logger = logging.getLogger(__name__)

MIN_POINTS_FOR_HOLTWINTERS = 30
MIN_POINTS_FOR_SEASONAL = 14  # Need at least 2 full seasonal periods for weekly


@dataclass
class ForecastResult:
    """Result of a single-SKU forecast."""

    sku: str
    history: pd.Series
    forecast: pd.Series
    daily_avg: float
    forecast_90d_total: float
    forecast_std: float | None  # For safety stock calc
    model_used: str  # "holt_winters" | "moving_avg" | "naive"


def _fallback_forecast(series: pd.Series, horizon_days: int) -> ForecastResult:
    """Use simple moving average when data is too sparse for Holt-Winters."""
    daily_avg = float(series.mean())
    if daily_avg <= 0:
        daily_avg = 1.0  # Avoid zero
    forecast_values = np.full(horizon_days, daily_avg)
    forecast_dates = pd.date_range(
        start=series.index.max() + pd.Timedelta(days=1),
        periods=horizon_days,
        freq="D",
    )
    forecast_series = pd.Series(forecast_values, index=forecast_dates)
    return ForecastResult(
        sku="",
        history=series,
        forecast=forecast_series,
        daily_avg=daily_avg,
        forecast_90d_total=float(forecast_series.sum()),
        forecast_std=float(series.std()) if len(series) > 1 else None,
        model_used="moving_avg",
    )


def fit_forecast(
    series: pd.Series,
    horizon_days: int = 90,
    sku: str = "",
) -> ForecastResult:
    """Fit time-series model and produce forecast.

    Uses Holt-Winters with additive seasonality when sufficient data.
    Falls back to moving average for sparse data (< 30 points).

    Args:
        series: Time series of daily demand (DatetimeIndex).
        horizon_days: Forecast horizon in days.
        sku: SKU identifier for the result.

    Returns:
        ForecastResult with history, forecast, and summary stats.
    """
    series = series.copy()
    series = series.asfreq("D", fill_value=0)

    if len(series) < MIN_POINTS_FOR_HOLTWINTERS:
        logger.warning(
            "Insufficient data for Holt-Winters (%d points), using moving average",
            len(series),
        )
        result = _fallback_forecast(series, horizon_days)
        result.sku = sku
        return result

    # Try Holt-Winters with weekly seasonality (period=7)
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
        logger.warning("Holt-Winters failed (%s), falling back to moving average", e)
        result = _fallback_forecast(series, horizon_days)
        result.sku = sku
        return result

    forecast_dates = pd.date_range(
        start=series.index.max() + pd.Timedelta(days=1),
        periods=horizon_days,
        freq="D",
    )
    forecast_series = pd.Series(forecast.values, index=forecast_dates)
    forecast_series = forecast_series.clip(lower=0)

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


def forecast_all_skus(
    aggregated: dict[str, pd.Series],
    horizon_days: int = 90,
) -> dict[str, ForecastResult]:
    """Forecast demand for all SKUs.

    Args:
        aggregated: Dict from ETL: sku -> demand series.
        horizon_days: Forecast horizon.

    Returns:
        Dict mapping sku -> ForecastResult.
    """
    results: dict[str, ForecastResult] = {}
    for sku, series in aggregated.items():
        results[sku] = fit_forecast(series, horizon_days=horizon_days, sku=sku)
    return results
