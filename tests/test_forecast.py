"""Tests for forecasting module."""

import pandas as pd
import pytest

from cpg_forecast.forecast import (
    ForecastResult,
    fit_forecast,
    forecast_all_skus,
)


def test_fit_forecast_sparse_data_fallback() -> None:
    """Sparse data falls back to moving average."""
    series = pd.Series(
        [10, 12, 11, 13, 10],
        index=pd.date_range("2024-01-01", periods=5, freq="D"),
    )
    result = fit_forecast(series, horizon_days=7, sku="SKU-001")
    assert result.model_used == "moving_avg"
    assert result.daily_avg == pytest.approx(11.2, rel=0.01)
    assert len(result.forecast) == 7


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
