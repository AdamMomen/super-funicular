"""ETL pipeline: load, clean, and aggregate historical order data."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import pandas as pd

if TYPE_CHECKING:
    from cpg_forecast.sources.base import SourceAdapter

REQUIRED_COLUMNS = {"order_date", "sku", "quantity"}
OPTIONAL_COLUMNS = {"channel", "customer_id"}

logger = logging.getLogger(__name__)


def load_orders(path: Path) -> pd.DataFrame:
    """Load order data from CSV.

    Args:
        path: Path to CSV file.

    Returns:
        DataFrame with order_date, sku, quantity (and optional channel, customer_id).

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If required columns are missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"Orders file not found: {path}")

    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower()

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Expected: {REQUIRED_COLUMNS}")

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    invalid_dates = df["order_date"].isna().sum()
    if invalid_dates > 0:
        logger.warning("Dropping %d rows with invalid order_date", invalid_dates)
        df = df.dropna(subset=["order_date"])

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    invalid_qty = df["quantity"].isna().sum()
    if invalid_qty > 0:
        logger.warning("Dropping %d rows with invalid quantity", invalid_qty)
        df = df.dropna(subset=["quantity"])

    return df


def clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Clean order data: normalize SKUs, filter invalid quantities.

    Args:
        df: Raw order DataFrame from load_orders.

    Returns:
        Cleaned DataFrame.
    """
    df = df.copy()

    # Normalize SKU: strip whitespace, drop empty
    df["sku"] = df["sku"].astype(str).str.strip()
    df = df[df["sku"].str.len() > 0]

    # Quantity must be positive
    df = df[df["quantity"] > 0]
    df["quantity"] = df["quantity"].astype(int)

    # Drop duplicates (same order_date, sku, quantity - conservative)
    df = df.drop_duplicates(subset=["order_date", "sku", "quantity"], keep="first")

    return df.reset_index(drop=True)


def aggregate_demand(
    df: pd.DataFrame,
    freq: Literal["D", "W"] = "D",
) -> dict[str, pd.Series]:
    """Aggregate orders into time series per SKU.

    Args:
        df: Cleaned order DataFrame.
        freq: Resample frequency - "D" for daily, "W" for weekly.

    Returns:
        Dict mapping sku -> pd.Series with DatetimeIndex and demand values.
        Gaps are filled with 0.
    """
    df = df.copy()
    df = df.groupby(["order_date", "sku"])["quantity"].sum().reset_index()

    result: dict[str, pd.Series] = {}
    skus = df["sku"].unique()

    for sku in skus:
        sku_df = df[df["sku"] == sku].copy()
        sku_df = sku_df.set_index("order_date").sort_index()
        sku_df = sku_df["quantity"]

        # Resample to ensure continuous date range
        if freq == "D":
            series = sku_df.resample("D").sum()
        else:
            series = sku_df.resample("W").sum()

        # Fill gaps with 0
        series = series.fillna(0)

        result[str(sku)] = series

    return result


def run_etl(
    orders_path: Path | None = None,
    orders_df: pd.DataFrame | None = None,
    source: "SourceAdapter | None" = None,
    config_path: Path | None = None,
    freq: Literal["D", "W"] = "D",
) -> "ETLResult":
    """Run full ETL pipeline: load, clean, aggregate.

    Args:
        orders_path: Path to orders CSV (use when source and orders_df are None).
        orders_df: DataFrame with order_date, sku, quantity (optional channel).
        source: Source adapter for orders (use when orders_path and orders_df are None).
        config_path: Optional path to config JSON (for future use).
        freq: Aggregation frequency.

    Returns:
        ETLResult with aggregated time series per SKU.
    """
    rows_loaded = 0
    rows_dropped_invalid = 0
    rows_dropped_duplicates = 0

    if source is not None:
        df = source.load_orders()
        rows_loaded = len(df)
    elif orders_df is not None:
        df_raw = orders_df.copy()
        df_raw.columns = df_raw.columns.str.strip().str.lower()
        if "channel" not in df_raw.columns:
            df_raw["channel"] = ""
        df_raw["order_date"] = pd.to_datetime(df_raw["order_date"], errors="coerce")
        df_raw = df_raw.dropna(subset=["order_date"])
        df_raw["quantity"] = pd.to_numeric(df_raw["quantity"], errors="coerce")
        df_raw = df_raw.dropna(subset=["quantity"])
        df_raw["quantity"] = df_raw["quantity"].astype(int)
        rows_loaded = len(df_raw)
        df = clean_orders(df_raw)
        rows_after = len(df)
        dup_count = df_raw.duplicated(subset=["order_date", "sku", "quantity"]).sum()
        rows_dropped_duplicates = int(dup_count)
        rows_dropped_invalid = max(0, rows_loaded - rows_after - rows_dropped_duplicates)
    elif orders_path is not None:
        df_raw = load_orders(orders_path)
        rows_loaded = len(df_raw)
        df = clean_orders(df_raw)
        rows_after = len(df)
        dup_count = df_raw.duplicated(subset=["order_date", "sku", "quantity"]).sum()
        rows_dropped_duplicates = int(dup_count)
        rows_dropped_invalid = max(0, rows_loaded - rows_after - rows_dropped_duplicates)
    else:
        raise ValueError("Provide orders_path, orders_df, or source")

    aggregated = aggregate_demand(df, freq=freq)

    return ETLResult(
        raw_row_count=len(df),
        skus=list(aggregated.keys()),
        aggregated=aggregated,
        rows_loaded=rows_loaded,
        rows_dropped_invalid=rows_dropped_invalid,
        rows_dropped_duplicates=rows_dropped_duplicates,
    )


class ETLResult:
    """Result of ETL pipeline."""

    def __init__(
        self,
        raw_row_count: int,
        skus: list[str],
        aggregated: dict[str, pd.Series],
        rows_loaded: int = 0,
        rows_dropped_invalid: int = 0,
        rows_dropped_duplicates: int = 0,
    ) -> None:
        self.raw_row_count = raw_row_count
        self.skus = skus
        self.aggregated = aggregated
        self.rows_loaded = rows_loaded or raw_row_count
        self.rows_dropped_invalid = rows_dropped_invalid
        self.rows_dropped_duplicates = rows_dropped_duplicates
