"""Config schema and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SkuConfig(BaseModel):
    """Per-SKU configuration."""

    lead_time_days: int = Field(default=14, ge=1, le=365)
    safety_stock_days: int = Field(default=7, ge=0, le=90)
    current_inventory: float = Field(default=0, ge=0)
    moq: float = Field(default=1, gt=0)


class ForecastConfig(BaseModel):
    """Forecast/inventory configuration schema."""

    default_lead_time_days: int = Field(default=14, ge=1, le=365)
    default_safety_stock_days: int = Field(default=7, ge=0, le=90)
    default_moq: float = Field(default=1, gt=0)
    skus: dict[str, SkuConfig] = Field(default_factory=dict)


def load_config(config_path: Path | None) -> dict[str, Any]:
    """Load and validate config JSON. Returns dict for backward compatibility."""
    defaults = ForecastConfig()
    if config_path is None or not config_path.exists():
        return defaults.model_dump()

    with open(config_path) as f:
        data = json.load(f)

    try:
        config = ForecastConfig(
            default_lead_time_days=data.get("default_lead_time_days", 14),
            default_safety_stock_days=data.get("default_safety_stock_days", 7),
            default_moq=data.get("default_moq", 1),
            skus={
                k: SkuConfig(**v) if isinstance(v, dict) else SkuConfig()
                for k, v in data.get("skus", {}).items()
            },
        )
        return config.model_dump()
    except Exception as e:
        raise ValueError(f"Invalid config: {e}") from e
