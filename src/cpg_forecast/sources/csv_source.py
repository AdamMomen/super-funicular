"""CSV file source adapter."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cpg_forecast.etl import clean_orders, load_orders


class CsvSourceAdapter:
    """Load orders from a CSV file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load_orders(self) -> pd.DataFrame:
        """Load and clean orders from CSV."""
        df = load_orders(self.path)
        return clean_orders(df)

    def get_name(self) -> str:
        return f"csv:{self.path.name}"
