"""FastAPI agent-ready API for CPG demand forecasting."""

from __future__ import annotations

import base64
import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

import pandas as pd

from api.schemas import AgentState, ChatRequest, DataQuality, ForecastJsonRequest, SkuState
from cpg_forecast.agent import AgentContext, run_agent_turn, run_agent_turn_stream
from cpg_forecast.etl import run_etl
from cpg_forecast.forecast import forecast_all_skus
from cpg_forecast.sources.edi_source import EdiSourceAdapter
from cpg_forecast.inventory import compute_recommendations
from cpg_forecast.llm import is_configured
from cpg_forecast.viz import plot_all_skus, plot_charts_by_sku

load_dotenv()

app = FastAPI()

# Mount API routes under /api for frontend compatibility
api = FastAPI()
app.mount("/api", api)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"], # TODO: revisit
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store: session_id -> AgentContext
_sessions: dict[str, AgentContext] = {}


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


@api.get("/health")
def health():
    """Health check for Coolify."""
    return {"status": "ok"}


@api.get("/forecast/sample-orders")
def get_sample_orders():
    """Return sample orders as JSON for editable table."""
    orders_path = Path("data/sample_orders.csv")
    if not orders_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Sample data not found"})
    df = pd.read_csv(orders_path)
    rows = []
    for _, r in df.iterrows():
        d = r.get("order_date", "")
        rows.append({
            "order_date": str(d)[:10] if pd.notna(d) else "",
            "sku": str(r.get("sku", "")),
            "quantity": int(float(r.get("quantity", 0))),
            "channel": str(r.get("channel", "")) if pd.notna(r.get("channel")) else "",
        })
    return {"orders": rows}


@api.get("/forecast/sample-edi")
def get_sample_edi():
    """Return sample EDI 850 content as plain text for copy/paste."""
    path = Path("data/sample_850.edi")
    if not path.exists():
        return JSONResponse(status_code=404, content={"detail": "Sample EDI not found"})
    return Response(content=path.read_text(), media_type="text/plain")


@api.get("/forecast")
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
    fig = plot_all_skus(forecasts, etl_result.aggregated)
    chart_json = json.loads(fig.to_json())
    table_data = [
        {
            "sku": r.sku,
            "forecast_90d": round(r.forecast_90d_total, 0),
            "daily_avg": round(r.daily_avg, 1),
            "reorder_point": round(r.reorder_point, 0),
            "reorder_qty": r.reorder_quantity,
            "current_inv": r.current_inventory,
            "recommendation": r.recommendation,
            "days_to_stockout": round(r.days_until_stockout, 1) if r.days_until_stockout else None,
        }
        for r in recommendations
    ]
    result = state.model_dump()
    result["chart_json"] = chart_json
    result["table_data"] = table_data
    result["raw_row_count"] = etl_result.raw_row_count
    result["skus_count"] = len(etl_result.skus)
    return result


def _is_edi_file(filename: str) -> bool:
    """Check if filename indicates an EDI file."""
    if not filename:
        return False
    lower = filename.lower()
    return lower.endswith(".edi") or lower.endswith(".x12") or lower.endswith(".850")


@api.post("/forecast")
async def post_forecast(
    orders: UploadFile = File(...),
    config: UploadFile | None = File(None),
    horizon: int = Form(90),
    freq: str = Form("D"),
):
    """Run forecast with uploaded CSV or EDI 850. Returns agent state JSON."""
    if not orders.filename:
        return JSONResponse(
            status_code=400,
            content={"detail": "Orders file is required"},
        )
    is_edi = _is_edi_file(orders.filename)
    if not is_edi and not orders.filename.lower().endswith(".csv"):
        return JSONResponse(
            status_code=400,
            content={"detail": "Orders file must be CSV (.csv) or EDI 850 (.edi, .x12)"},
        )

    try:
        suffix = ".edi" if is_edi else ".csv"
        with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as f:
            f.write(await orders.read())
            orders_path = Path(f.name)

        config_path = None
        if config and config.filename:
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
                f.write(await config.read())
                config_path = Path(f.name)

        if is_edi:
            source = EdiSourceAdapter(orders_path)
            etl_result = run_etl(source=source, config_path=config_path, freq=freq)
        else:
            etl_result = run_etl(orders_path=orders_path, config_path=config_path, freq=freq)
        forecasts = forecast_all_skus(etl_result.aggregated, horizon_days=horizon)
        recommendations = compute_recommendations(forecasts, config_path=config_path)
        state = _build_agent_state(recommendations, etl_result)
        fig = plot_all_skus(forecasts, etl_result.aggregated)
        chart_json = json.loads(fig.to_json())
        charts_by_sku = plot_charts_by_sku(forecasts, etl_result.aggregated)
        table_data = [
            {
                "sku": r.sku,
                "forecast_90d": round(r.forecast_90d_total, 0),
                "daily_avg": round(r.daily_avg, 1),
                "reorder_point": round(r.reorder_point, 0),
                "reorder_qty": r.reorder_quantity,
                "current_inv": r.current_inventory,
                "recommendation": r.recommendation,
                "days_to_stockout": round(r.days_until_stockout, 1) if r.days_until_stockout else None,
            }
            for r in recommendations
        ]
        result = state.model_dump()
        result["chart_json"] = chart_json
        result["charts_by_sku"] = charts_by_sku
        result["table_data"] = table_data
        result["raw_row_count"] = etl_result.raw_row_count
        result["skus_count"] = len(etl_result.skus)
        return result
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


@api.post("/forecast/json")
async def post_forecast_json(req: ForecastJsonRequest):
    """Run forecast with JSON orders (from editable table)."""
    if not req.orders:
        return JSONResponse(status_code=400, content={"detail": "At least one order required"})
    try:
        rows = [
            {"order_date": o.order_date, "sku": o.sku, "quantity": o.quantity, "channel": o.channel or ""}
            for o in req.orders
        ]
        df = pd.DataFrame(rows)
        etl_result = run_etl(orders_df=df, config_path=None, freq="D")
        rolling_window = req.rolling_window if req.rolling_window is not None else 14
        forecasts = forecast_all_skus(
            etl_result.aggregated,
            horizon_days=90,
            algorithm=req.algorithm,
            rolling_window=rolling_window,
        )
        config_path = Path("data/sample_config.json") if Path("data/sample_config.json").exists() else None
        recommendations = compute_recommendations(forecasts, config_path=config_path)
        state = _build_agent_state(recommendations, etl_result)
        charts_by_sku = plot_charts_by_sku(forecasts, etl_result.aggregated)
        table_data = [
            {
                "sku": r.sku,
                "forecast_90d": round(r.forecast_90d_total, 0),
                "daily_avg": round(r.daily_avg, 1),
                "reorder_point": round(r.reorder_point, 0),
                "reorder_qty": r.reorder_quantity,
                "current_inv": r.current_inventory,
                "recommendation": r.recommendation,
                "days_to_stockout": round(r.days_until_stockout, 1) if r.days_until_stockout else None,
            }
            for r in recommendations
        ]
        result = state.model_dump()
        result["charts_by_sku"] = charts_by_sku
        result["table_data"] = table_data
        result["raw_row_count"] = etl_result.raw_row_count
        result["skus_count"] = len(etl_result.skus)
        result["algorithm_used"] = req.algorithm
        model_used = next((r.model_used for r in forecasts.values()), req.algorithm)
        result["model_used"] = model_used
        result["fallback"] = model_used != req.algorithm  # True when HW fell back to simple mean
        return result
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


@api.get("/chat/configured")
def chat_configured():
    """Check if chat/agent is configured (Cloudflare credentials)."""
    return {"configured": is_configured()}


@api.post("/chat")
async def post_chat(req: ChatRequest):
    """Non-streaming chat. Returns response and optional chart JSON."""
    if not is_configured():
        return JSONResponse(
            status_code=503,
            content={"detail": "Chat not configured. Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN."},
        )

    session_id = req.session_id or str(uuid.uuid4())
    context = _sessions.get(session_id)
    if context is None:
        context = AgentContext()
        _sessions[session_id] = context

    if req.orders_base64:
        try:
            context.uploaded_orders_bytes = base64.b64decode(req.orders_base64)
        except Exception:
            pass
    if req.config_base64:
        try:
            context.uploaded_config_bytes = base64.b64decode(req.config_base64)
        except Exception:
            pass

    try:
        response_text, last_chart = run_agent_turn(req.message, context, freq="D")
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e), "session_id": session_id},
        )

    chart_json = None
    if last_chart is not None:
        chart_json = json.loads(last_chart.to_json())

    return {
        "response": response_text,
        "chart_json": chart_json,
        "session_id": session_id,
    }


def _sse_format(event: str, data: dict) -> str:
    """Format SSE message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@api.post("/chat/stream")
async def post_chat_stream(req: ChatRequest):
    """Streaming chat via SSE."""
    if not is_configured():
        return JSONResponse(
            status_code=503,
            content={"detail": "Chat not configured. Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN."},
        )

    session_id = req.session_id or str(uuid.uuid4())
    context = _sessions.get(session_id)
    if context is None:
        context = AgentContext()
        _sessions[session_id] = context

    if req.orders_base64:
        try:
            context.uploaded_orders_bytes = base64.b64decode(req.orders_base64)
        except Exception:
            pass
    if req.config_base64:
        try:
            context.uploaded_config_bytes = base64.b64decode(req.config_base64)
        except Exception:
            pass

    def generate():
        try:
            yield _sse_format("session", {"session_id": session_id})
            for event_type, data in run_agent_turn_stream(req.message, context, freq="D"):
                yield _sse_format(event_type, data)
        except Exception as e:
            yield _sse_format("error", {"message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Serve frontend static files (when frontend/dist exists, e.g. in Docker)
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def serve_spa(path: str):
        if path.startswith("api"):
            raise HTTPException(status_code=404)
        return FileResponse(_frontend_dist / "index.html")
