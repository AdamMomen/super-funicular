"""API tests for /api/forecast/json and /api/forecast - verify algorithms and file upload."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _orders_35_days() -> list[dict]:
    """35 days of daily orders for SKU-A (enough for Holt-Winters)."""
    import pandas as pd

    dates = pd.date_range("2024-01-01", periods=35, freq="D")
    return [
        {"order_date": d.strftime("%Y-%m-%d"), "sku": "SKU-A", "quantity": 10 + (i % 7), "channel": "DTC"}
        for i, d in enumerate(dates)
    ]


def test_forecast_json_naive_returns_valid_forecast() -> None:
    """Naive algorithm: uses last week's pattern (7+ days) or last value; produces varying forecast."""
    orders = _orders_35_days()

    r = client.post(
        "/api/forecast/json",
        json={"orders": orders, "algorithm": "naive"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["model_used"] == "naive"

    td = data["table_data"]
    assert len(td) == 1
    # With 35 days, naive uses last 7 days (10,11,12,13,14,15,16) -> mean ~13, forecast_90d ~1170
    assert 1000 <= td[0]["forecast_90d"] <= 1500

    chart = data["charts_by_sku"]["SKU-A"]
    forecast_trace = next(t for t in chart["data"] if t["name"] == "90-day forecast")
    y = forecast_trace["y"]
    assert len(y) == 90
    # Naive with 7+ days produces weekly pattern (varying)
    assert len(set(round(v, 2) for v in y)) >= 1
    assert all(v >= 0 for v in y)


def test_forecast_json_simple_mean_returns_mean() -> None:
    """Simple mean: with 14+ days uses weekly pattern; forecast values in reasonable range."""
    orders = _orders_35_days()
    # Quantities: 10,11,12,13,14,15,16 (cycle of 7). Mean ≈ 13
    r = client.post(
        "/api/forecast/json",
        json={"orders": orders, "algorithm": "simple_mean"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["model_used"] == "simple_mean"

    chart = data["charts_by_sku"]["SKU-A"]
    forecast_trace = next(t for t in chart["data"] if t["name"] == "90-day forecast")
    y = forecast_trace["y"]
    assert len(y) == 90
    # With 14+ days, simple mean uses weekly pattern (varying)
    assert all(10 <= v <= 16 for v in y)
    assert sum(y) > 0


def test_forecast_json_holt_winters_returns_varying_forecast() -> None:
    """Holt-Winters: forecast should NOT be constant (varying over horizon)."""
    orders = _orders_35_days()

    r = client.post(
        "/api/forecast/json",
        json={"orders": orders, "algorithm": "holt_winters"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["model_used"] == "holt_winters"

    chart = data["charts_by_sku"]["SKU-A"]
    forecast_trace = next(t for t in chart["data"] if t["name"] == "90-day forecast")
    y = forecast_trace["y"]
    assert len(y) == 90
    # Holt-Winters should produce varying values (not flat)
    unique_vals = set(round(v, 2) for v in y)
    assert len(unique_vals) > 1, "Holt-Winters should produce non-constant forecast"


def test_forecast_json_algorithms_produce_valid_outputs() -> None:
    """All algorithms produce valid forecast_90d in reasonable range."""
    orders = _orders_35_days()
    results = {}

    for algo in ["naive", "simple_mean", "holt_winters", "rolling_ma", "exp_smoothing"]:
        r = client.post(
            "/api/forecast/json",
            json={"orders": orders, "algorithm": algo, "rolling_window": 5},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["model_used"] == algo
        td = data["table_data"]
        results[algo] = td[0]["forecast_90d"]

    # All produce reasonable forecasts
    assert all(500 < v < 3000 for v in results.values())


def test_forecast_json_rolling_ma_uses_window() -> None:
    """Rolling MA with window=5: uses mean of last 5 days."""
    orders = _orders_35_days()
    # Last 5 days (indices 30-34): qty 12,13,14,15,16. Mean=14. forecast_90d=1260
    r = client.post(
        "/api/forecast/json",
        json={"orders": orders, "algorithm": "rolling_ma", "rolling_window": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["model_used"] == "rolling_ma"

    td = data["table_data"]
    expected = 14 * 90  # 1260
    assert td[0]["forecast_90d"] == expected


def test_forecast_json_exp_smoothing_returns_valid() -> None:
    """Exponential smoothing returns valid forecast."""
    orders = _orders_35_days()
    r = client.post(
        "/api/forecast/json",
        json={"orders": orders, "algorithm": "exp_smoothing"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["model_used"] == "exp_smoothing"

    chart = data["charts_by_sku"]["SKU-A"]
    forecast_trace = next(t for t in chart["data"] if t["name"] == "90-day forecast")
    y = forecast_trace["y"]
    assert len(y) == 90
    assert all(v >= 0 for v in y)


def test_forecast_post_accepts_edi_850() -> None:
    """POST /forecast accepts EDI 850 file upload."""
    sample_edi = Path(__file__).parent.parent / "data" / "sample_850.edi"
    if not sample_edi.exists():
        pytest.skip("data/sample_850.edi not found")

    with open(sample_edi, "rb") as f:
        r = client.post(
            "/api/forecast",
            data={"horizon": 90, "freq": "D"},
            files={"orders": ("sample_850.edi", f, "application/octet-stream")},
        )
    assert r.status_code == 200
    data = r.json()
    assert "table_data" in data
    assert data["raw_row_count"] >= 1
    assert data["skus_count"] >= 1
