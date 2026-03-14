"""Tests for forecasting module."""

import numpy as np
import pandas as pd
import pytest

from cpg_forecast.forecast import (
    ALGORITHMS,
    ForecastResult,
    fit_forecast,
    forecast_all_skus,
)


def test_fit_forecast_sparse_data_fallback() -> None:
    """Sparse data falls back to simple mean when using holt_winters."""
    series = pd.Series(
        [10, 12, 11, 13, 10],
        index=pd.date_range("2024-01-01", periods=5, freq="D"),
    )
    result = fit_forecast(series, horizon_days=7, sku="SKU-001")
    assert result.model_used == "simple_mean"
    assert result.daily_avg == pytest.approx(11.2, rel=0.01)
    assert len(result.forecast) == 7


def test_simple_mean_uses_positive_values_only() -> None:
    """Simple mean uses mean of positive values only (avoids zero dilution)."""
    # 10 days: 5 zeros, 5 values of 20 each
    values = [0, 20, 0, 20, 0, 20, 0, 20, 0, 20]
    series = pd.Series(
        values,
        index=pd.date_range("2024-01-01", periods=10, freq="D"),
    )
    result = fit_forecast(series, horizon_days=7, sku="X", algorithm="simple_mean")
    assert result.model_used == "simple_mean"
    # Mean of positive only = 20, not overall mean of 10
    assert result.daily_avg == pytest.approx(20.0, rel=0.01)
    assert result.forecast_90d_total == pytest.approx(20.0 * 7, rel=0.01)


def test_naive_repeats_last_value() -> None:
    """Naive algorithm repeats last observed value."""
    series = pd.Series(
        [5, 10, 15, 25],
        index=pd.date_range("2024-01-01", periods=4, freq="D"),
    )
    result = fit_forecast(series, horizon_days=10, sku="Y", algorithm="naive")
    assert result.model_used == "naive"
    assert result.daily_avg == 25.0
    assert result.forecast_90d_total == 25.0 * 10
    assert (result.forecast == 25.0).all()


def test_rolling_ma_uses_last_n_values() -> None:
    """Rolling MA uses mean of last N days."""
    series = pd.Series(
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        index=pd.date_range("2024-01-01", periods=15, freq="D"),
    )
    result = fit_forecast(
        series, horizon_days=5, sku="Z", algorithm="rolling_ma", rolling_window=5
    )
    assert result.model_used == "rolling_ma"
    # Last 5 values: 11, 12, 13, 14, 15 -> mean = 13
    assert result.daily_avg == pytest.approx(13.0, rel=0.01)
    assert result.forecast_90d_total == pytest.approx(13.0 * 5, rel=0.01)


def test_exp_smoothing_returns_valid_forecast() -> None:
    """Exponential smoothing returns valid forecast."""
    series = pd.Series(
        [10, 12, 11, 13, 14, 12, 15] * 5,  # 35 days
        index=pd.date_range("2024-01-01", periods=35, freq="D"),
    )
    result = fit_forecast(series, horizon_days=14, sku="W", algorithm="exp_smoothing")
    assert result.model_used == "exp_smoothing"
    assert len(result.forecast) == 14
    assert result.forecast_90d_total > 0
    assert (result.forecast >= 0).all()


def test_fit_forecast_sufficient_data() -> None:
    """Sufficient data uses Holt-Winters."""
    # 35 days of data
    import numpy as np
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=35, freq="D")
    values = 10 + np.cumsum(np.random.randn(35) * 0.5) + np.sin(np.arange(35) * 2 * np.pi / 7) * 2
    values = np.clip(values, 1, 30)
    series = pd.Series(values, index=dates)

    result = fit_forecast(series, horizon_days=14, sku="SKU-001")
    assert result.model_used == "holt_winters"
    assert len(result.forecast) == 14
    assert result.forecast_90d_total > 0


def test_forecast_all_skus() -> None:
    """Forecast multiple SKUs."""
    aggregated = {
        "SKU-A": pd.Series(
            [10] * 35,
            index=pd.date_range("2024-01-01", periods=35, freq="D"),
        ),
        "SKU-B": pd.Series(
            [20] * 35,
            index=pd.date_range("2024-01-01", periods=35, freq="D"),
        ),
    }
    results = forecast_all_skus(aggregated, horizon_days=10)
    assert "SKU-A" in results
    assert "SKU-B" in results
    assert results["SKU-A"].forecast_90d_total < results["SKU-B"].forecast_90d_total


def test_forecast_all_skus_with_algorithm() -> None:
    """Forecast with explicit algorithm."""
    # Use 35 days so holt_winters has enough data
    np.random.seed(1)
    values = 10 + np.cumsum(np.random.randn(35) * 0.3)
    values = np.clip(values, 1, 30)
    aggregated = {
        "SKU-X": pd.Series(
            values,
            index=pd.date_range("2024-01-01", periods=35, freq="D"),
        ),
    }
    for algo in ALGORITHMS:
        results = forecast_all_skus(aggregated, horizon_days=7, algorithm=algo)
        assert "SKU-X" in results
        assert results["SKU-X"].model_used == algo
        assert len(results["SKU-X"].forecast) == 7
