"""Tests for source adapters."""

from pathlib import Path

import pytest

from cpg_forecast.etl import run_etl
from cpg_forecast.sources import CsvSourceAdapter, ShopifySourceAdapter


def test_csv_source_adapter(tmp_path: Path) -> None:
    """CsvSourceAdapter loads and cleans orders."""
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_date,sku,quantity,channel\n"
        "2024-01-15,SKU-001,100,DTC\n"
        "2024-01-16,SKU-001,50,retail\n"
    )
    adapter = CsvSourceAdapter(csv_path)
    df = adapter.load_orders()
    assert len(df) == 2
    assert adapter.get_name() == "csv:orders.csv"


def test_run_etl_with_source(tmp_path: Path) -> None:
    """run_etl works with CsvSourceAdapter."""
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "order_date,sku,quantity\n"
        "2024-01-15,SKU-001,10\n"
        "2024-01-16,SKU-001,20\n"
    )
    adapter = CsvSourceAdapter(csv_path)
    result = run_etl(source=adapter, freq="D")
    assert set(result.skus) == {"SKU-001"}
    assert result.aggregated["SKU-001"].sum() == 30


def test_shopify_source_adapter_stub() -> None:
    """ShopifySourceAdapter raises NotImplementedError."""
    adapter = ShopifySourceAdapter("mystore.myshopify.com")
    with pytest.raises(NotImplementedError, match="Connect Shopify API"):
        adapter.load_orders()
    assert adapter.get_name() == "shopify:mystore.myshopify.com"
