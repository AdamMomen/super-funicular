"""FastAPI agent-ready API for CPG demand forecasting."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from api.schemas import AgentState, DataQuality, SkuState
from cpg_forecast.etl import run_etl
from cpg_forecast.forecast import forecast_all_skus
from cpg_forecast.inventory import compute_recommendations

app = FastAPI()


def _build_agent_state(recommendations, etl_result) -> AgentState:
    """Build agent state from pipeline results."""
    sku_states = []
    alerts = []

    for r in recommendations:
        sku_states.append(
            SkuState(
                sku=r.sku,
                forecast_90d=round(r.forecast_90d_total, 0),
                reorder_point=round(r.reorder_point, 0),
                current_inventory=r.current_inventory,
                recommendation=r.recommendation,
                reorder_qty=r.reorder_quantity,
                lead_time_days=r.lead_time_days,
            )
        )
        if r.recommendation == "ORDER_NOW":
            alerts.append(f"{r.sku} below reorder point")
        elif r.recommendation == "LOW_STOCK":
            alerts.append(f"{r.sku} low stock")

    data_quality = None
    if hasattr(etl_result, "rows_loaded"):
        data_quality = DataQuality(
            rows_loaded=etl_result.rows_loaded,
            rows_dropped_invalid=getattr(etl_result, "rows_dropped_invalid", 0),
            rows_dropped_duplicates=getattr(etl_result, "rows_dropped_duplicates", 0),
            skus_found=len(etl_result.skus),
        )

    return AgentState(
        skus=sku_states,
        alerts=alerts,
        last_updated=datetime.utcnow(),
        data_quality=data_quality,
    )


@app.get("/health")
def health():
    """Health check for Coolify."""
    return {"status": "ok"}


@app.get("/forecast")
def get_forecast_sample(
    sample: bool = True,
    horizon: int = 90,
    freq: str = "D",
):
    """Run forecast with sample data. Returns agent state JSON."""
    orders_path = Path("data/sample_orders.csv")
    config_path = Path("data/sample_config.json")
    if not orders_path.exists():
        return JSONResponse(
            status_code=404,
            content={"detail": "Sample data not found"},
        )
    config_path = config_path if config_path.exists() else None

    etl_result = run_etl(orders_path=orders_path, config_path=config_path, freq=freq)
    forecasts = forecast_all_skus(etl_result.aggregated, horizon_days=horizon)
    recommendations = compute_recommendations(forecasts, config_path=config_path)
    state = _build_agent_state(recommendations, etl_result)
    return state.model_dump()


@app.post("/forecast")
async def post_forecast(
    orders: UploadFile = File(...),
    config: UploadFile | None = File(None),
    horizon: int = Form(90),
    freq: str = Form("D"),
):
    """Run forecast with uploaded CSV. Returns agent state JSON."""
    if not orders.filename or not orders.filename.endswith(".csv"):
        return JSONResponse(
            status_code=400,
            content={"detail": "Orders file must be a CSV"},
        )

    try:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
            f.write(await orders.read())
            orders_path = Path(f.name)

        config_path = None
        if config and config.filename:
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
                f.write(await config.read())
                config_path = Path(f.name)

        etl_result = run_etl(orders_path=orders_path, config_path=config_path, freq=freq)
        forecasts = forecast_all_skus(etl_result.aggregated, horizon_days=horizon)
        recommendations = compute_recommendations(forecasts, config_path=config_path)
        state = _build_agent_state(recommendations, etl_result)
        return state.model_dump()
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
