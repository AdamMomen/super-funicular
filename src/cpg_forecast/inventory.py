"""Inventory recommendation logic: reorder points and quantities."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cpg_forecast.forecast import ForecastResult

logger = logging.getLogger(__name__)

# Service level 95% -> z ≈ 1.65
Z_95 = 1.65


@dataclass
class InventoryRecommendation:
    """Single-SKU inventory recommendation."""

    sku: str
    forecast_90d_total: float
    daily_avg: float
    reorder_point: float
    reorder_quantity: float
    current_inventory: float
    recommendation: str  # "ORDER_NOW" | "OK" | "LOW_STOCK"
    days_until_stockout: float | None


def _load_config(config_path: Path | None) -> dict[str, Any]:
    """Load config JSON with defaults."""
    defaults = {
        "default_lead_time_days": 14,
        "default_safety_stock_days": 7,
        "default_moq": 1,
        "skus": {},
    }
    if config_path is None or not config_path.exists():
        return defaults

    with open(config_path) as f:
        data = json.load(f)
    return {**defaults, **data}


def _get_sku_config(config: dict[str, Any], sku: str) -> dict[str, Any]:
    """Get config for a SKU, merging with defaults."""
    defaults = {
        "lead_time_days": config.get("default_lead_time_days", 14),
        "safety_stock_days": config.get("default_safety_stock_days", 7),
        "current_inventory": 0,
        "moq": config.get("default_moq", 1),
    }
    sku_config = config.get("skus", {}).get(sku, {})
    return {**defaults, **sku_config}


def compute_reorder_point(
    forecast: ForecastResult,
    lead_time_days: int,
    safety_days: int,
    use_std: bool = True,
) -> float:
    """Compute reorder point: lead time demand + safety stock.

    Args:
        forecast: Forecast result with daily_avg and optional forecast_std.
        lead_time_days: Supplier lead time in days.
        safety_days: Safety stock buffer in days of demand.
        use_std: If True and forecast_std available, use z * std for safety stock.

    Returns:
        Reorder point (units).
    """
    lead_time_demand = forecast.daily_avg * lead_time_days

    if use_std and forecast.forecast_std is not None and forecast.forecast_std > 0:
        # Safety stock = z * std * sqrt(lead_time) for lead time demand variability
        safety_stock = Z_95 * forecast.forecast_std * math.sqrt(lead_time_days)
    else:
        safety_stock = forecast.daily_avg * safety_days

    return lead_time_demand + safety_stock


def compute_recommendations(
    forecasts: dict[str, ForecastResult],
    config_path: Path | None = None,
) -> list[InventoryRecommendation]:
    """Compute inventory recommendations for all forecasted SKUs.

    Args:
        forecasts: Dict from forecast_all_skus.
        config_path: Path to config JSON with lead times, MOQs, current inventory.

    Returns:
        List of InventoryRecommendation, one per SKU.
    """
    config = _load_config(config_path)
    recommendations: list[InventoryRecommendation] = []

    for sku, forecast in forecasts.items():
        sku_cfg = _get_sku_config(config, sku)
        lead_time_days = int(sku_cfg["lead_time_days"])
        safety_days = int(sku_cfg["safety_stock_days"])
        current_inv = float(sku_cfg["current_inventory"])
        moq = float(sku_cfg["moq"])

        reorder_point = compute_reorder_point(
            forecast, lead_time_days, safety_days
        )

        # Days until stockout
        if forecast.daily_avg > 0:
            days_until_stockout = current_inv / forecast.daily_avg
        else:
            days_until_stockout = None

        # Reorder quantity when below reorder point
        if current_inv < reorder_point:
            shortfall = reorder_point - current_inv
            # Round up to MOQ
            reorder_qty = max(moq, math.ceil(shortfall / moq) * moq)
            reorder_qty = int(reorder_qty)
            rec = "ORDER_NOW"
        elif days_until_stockout is not None and days_until_stockout < lead_time_days:
            reorder_qty = max(moq, int(reorder_point - current_inv))
            rec = "LOW_STOCK"
        else:
            reorder_qty = 0
            rec = "OK"

        recommendations.append(
            InventoryRecommendation(
                sku=sku,
                forecast_90d_total=forecast.forecast_90d_total,
                daily_avg=forecast.daily_avg,
                reorder_point=reorder_point,
                reorder_quantity=reorder_qty,
                current_inventory=current_inv,
                recommendation=rec,
                days_until_stockout=days_until_stockout,
            )
        )

    return recommendations
