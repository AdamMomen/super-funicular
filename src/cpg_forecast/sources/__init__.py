"""Source adapters for multi-source order ingestion."""

from cpg_forecast.sources.base import SourceAdapter
from cpg_forecast.sources.csv_source import CsvSourceAdapter
from cpg_forecast.sources.edi_source import EdiSourceAdapter
from cpg_forecast.sources.shopify_source import ShopifySourceAdapter

__all__ = ["SourceAdapter", "CsvSourceAdapter", "EdiSourceAdapter", "ShopifySourceAdapter"]
