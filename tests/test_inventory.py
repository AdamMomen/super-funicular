"""Tests for inventory recommendation logic."""

from pathlib import Path

import pandas as pd
import pytest

from cpg_forecast.forecast import ForecastResult, fit_forecast
from cpg_forecast.inventory import (
    compute_recommendations,
    compute_reorder_point,
)


def test_compute_reorder_point() -> None:
    """Reorder point = lead time demand + safety stock."""
    series = pd.Series(
        [10.0] * 35,
        index=pd.date_range("2024-01-01", periods=35, freq="D"),
    )
    forecast = fit_forecast(series, horizon_days=90, sku="SKU-001")
    rp = compute_reorder_point(forecast, lead_time_days=14, safety_days=7)
    # lead_time_demand = 10 * 14 = 140, safety = 10 * 7 = 70 -> 210
    assert rp >= 200
    assert rp <= 250


def test_compute_recommendations_order_now(tmp_path: Path) -> None:
    """When inventory below reorder point, recommend ORDER_NOW."""
    config_path = tmp_path / "config.json"
    config_path.write_text('''
    {
      "default_lead_time_days": 14,
      "default_safety_stock_days": 7,
      "skus": {
        "SKU-001": {
          "current_inventory": 10,
          "moq": 50
        }
      }
    }
    ''')

    series = pd.Series(
        [20.0] * 35,  # 20/day demand
        index=pd.date_range("2024-01-01", periods=35, freq="D"),
    )
    forecast = fit_forecast(series, horizon_days=90, sku="SKU-001")
    forecasts = {"SKU-001": forecast}

    recs = compute_recommendations(forecasts, config_path)
    assert len(recs) == 1
    assert recs[0].recommendation == "ORDER_NOW"
    assert recs[0].reorder_quantity >= 50
    assert recs[0].current_inventory == 10


def test_compute_recommendations_ok(tmp_path: Path) -> None:
    """When inventory above reorder point, recommend OK."""
    config_path = tmp_path / "config.json"
    config_path.write_text('''
    {
      "default_lead_time_days": 14,
      "default_safety_stock_days": 7,
      "skus": {
        "SKU-001": {
          "current_inventory": 1000,
          "moq": 50
        }
      }
    }
    ''')

    series = pd.Series(
        [5.0] * 35,  # 5/day demand
        index=pd.date_range("2024-01-01", periods=35, freq="D"),
    )
    forecast = fit_forecast(series, horizon_days=90, sku="SKU-001")
    forecasts = {"SKU-001": forecast}

    recs = compute_recommendations(forecasts, config_path)
    assert recs[0].recommendation == "OK"
    assert recs[0].reorder_quantity == 0
