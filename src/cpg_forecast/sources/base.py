"""Base protocol for order data source adapters."""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class SourceAdapter(Protocol):
    """Protocol for order data sources. Enables CSV, Shopify, EDI, etc."""

    def load_orders(self) -> pd.DataFrame:
        """Load and return orders as DataFrame with columns: order_date, sku, quantity.

        Optional: channel, customer_id.
        """
        ...

    def get_name(self) -> str:
        """Return source identifier for logging."""
        ...
