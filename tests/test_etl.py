"""Tests for ETL pipeline."""

from pathlib import Path

import pandas as pd
import pytest

from cpg_forecast.etl import (
    aggregate_demand,
    clean_orders,
    load_orders,
    run_etl,
)


def test_load_orders_valid(tmp_path: Path) -> None:
    """Load valid CSV."""
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_date,sku,quantity,channel\n"
        "2024-01-15,SKU-001,120,DTC\n"
        "2024-01-16,SKU-001,45,retail\n"
    )
    df = load_orders(csv_path)
    assert len(df) == 2
    assert list(df.columns) == ["order_date", "sku", "quantity", "channel"]
    assert df["quantity"].iloc[0] == 120


def test_load_orders_missing_columns(tmp_path: Path) -> None:
    """Raise on missing required columns."""
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text("order_date,quantity\n2024-01-15,10\n")
    with pytest.raises(ValueError, match="Missing required columns"):
        load_orders(csv_path)


def test_load_orders_file_not_found() -> None:
    """Raise on missing file."""
    with pytest.raises(FileNotFoundError, match="not found"):
        load_orders(Path("/nonexistent/orders.csv"))


def test_clean_orders_normalizes_sku() -> None:
    """Normalize SKU strings."""
    df = pd.DataFrame({
        "order_date": pd.to_datetime(["2024-01-15", "2024-01-16"]),
        "sku": ["  SKU-001  ", "SKU-001"],
        "quantity": [10, 20],
    })
    cleaned = clean_orders(df)
    assert cleaned["sku"].iloc[0] == "SKU-001"
    assert len(cleaned) == 2


def test_clean_orders_filters_invalid_quantity() -> None:
    """Drop non-positive quantities."""
    df = pd.DataFrame({
        "order_date": pd.to_datetime(["2024-01-15", "2024-01-16", "2024-01-17"]),
        "sku": ["SKU-001", "SKU-001", "SKU-001"],
        "quantity": [10, 0, -5],
    })
    cleaned = clean_orders(df)
    assert len(cleaned) == 1
    assert cleaned["quantity"].iloc[0] == 10


def test_aggregate_demand_daily() -> None:
    """Aggregate to daily demand per SKU."""
    df = pd.DataFrame({
        "order_date": pd.to_datetime(
            ["2024-01-15", "2024-01-15", "2024-01-16", "2024-01-16"]
        ),
        "sku": ["SKU-001", "SKU-001", "SKU-001", "SKU-002"],
        "quantity": [10, 20, 15, 50],
    })
    result = aggregate_demand(df, freq="D")
    assert "SKU-001" in result
    assert "SKU-002" in result
    # SKU-001 on 2024-01-15: 10 + 20 = 30
    sku1 = result["SKU-001"]
    assert sku1.loc[pd.Timestamp("2024-01-15")] == 30
    assert sku1.loc[pd.Timestamp("2024-01-16")] == 15


def test_run_etl_integration(tmp_path: Path) -> None:
    """Full ETL pipeline."""
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_date,sku,quantity,channel\n"
        "2024-01-15,SKU-001,100,DTC\n"
        "2024-01-16,SKU-001,50,retail\n"
        "2024-01-17,SKU-002,200,wholesale\n"
    )
    result = run_etl(orders_path=csv_path, freq="D")
    assert result.raw_row_count == 3
    assert set(result.skus) == {"SKU-001", "SKU-002"}
    assert len(result.aggregated["SKU-001"]) >= 2
    assert result.aggregated["SKU-001"].sum() == 150  # 100 + 50
