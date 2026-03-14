"""Pydantic schemas for agent state and API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SkuState(BaseModel):
    """Single-SKU state for agent consumption."""

    sku: str
    forecast_90d: float
    reorder_point: float
    current_inventory: float
    recommendation: str
    reorder_qty: float
    lead_time_days: int


class DataQuality(BaseModel):
    """Data quality metrics from ETL."""

    rows_loaded: int
    rows_dropped_invalid: int = 0
    rows_dropped_duplicates: int = 0
    skus_found: int


class AgentState(BaseModel):
    """Unified operational state for AI agent consumption."""

    skus: list[SkuState]
    alerts: list[str]
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    data_quality: DataQuality | None = None


class ChatRequest(BaseModel):
    """Request body for chat endpoints."""

    message: str
    session_id: str | None = None
    orders_base64: str | None = None
    config_base64: str | None = None


class OrderRow(BaseModel):
    """Single order row for forecast input."""

    order_date: str
    sku: str
    quantity: int
    channel: str | None = None


class ForecastJsonRequest(BaseModel):
    """Request body for JSON forecast endpoint."""

    orders: list[OrderRow]
    algorithm: Literal["holt_winters", "simple_mean", "naive", "rolling_ma", "exp_smoothing"] = "holt_winters"
    rolling_window: int | None = 14  # Only used when algorithm == "rolling_ma"
