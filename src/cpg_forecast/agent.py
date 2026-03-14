"""Custom agent with function-calling tools for CPG demand forecasting."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cpg_forecast.etl import run_etl
from cpg_forecast.forecast import ForecastResult, forecast_all_skus
from cpg_forecast.inventory import InventoryRecommendation, compute_recommendations
from cpg_forecast.llm import chat
from cpg_forecast.viz import plot_forecast

if TYPE_CHECKING:
    import pandas as pd
    from plotly import graph_objects as go

TOOLS: list[dict[str, Any]] = [
    {
        "name": "run_forecast",
        "description": "Run the demand forecast pipeline. Use sample data or uploaded CSV. Call this when the user wants to run a forecast, analyze data, or get inventory recommendations.",
        "parameters": {
            "type": "object",
            "properties": {
                "use_sample": {
                    "type": "boolean",
                    "description": "If true, use bundled sample data. If false, use the user's uploaded file (must be uploaded first).",
                },
                "horizon_days": {
                    "type": "integer",
                    "description": "Forecast horizon in days (default 90).",
                    "default": 90,
                },
            },
            "required": ["use_sample"],
        },
    },
    {
        "name": "get_inventory_summary",
        "description": "Get the current inventory summary and recommendations. Returns SKU-level data: forecast, reorder point, current inventory, recommendation. Call this after a forecast has been run.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_forecast_chart",
        "description": "Display a forecast chart for a specific SKU. Call this when the user wants to see a chart or visualization for a SKU. A forecast must have been run first.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "The SKU identifier (e.g. SKU-001).",
                },
            },
            "required": ["sku"],
        },
    },
]

SYSTEM_PROMPT = """You are an assistant for CPG demand forecasting. You help users run forecasts, view inventory recommendations, and display charts.

You have access to tools:
- run_forecast: Run the pipeline (sample data or user's uploaded file)
- get_inventory_summary: Get current recommendations after a forecast
- get_forecast_chart: Show a chart for a specific SKU

Be concise. When you run a forecast, summarize the results. When showing a chart, confirm the SKU. If the user asks for something that requires a forecast first, run it."""


@dataclass
class AgentContext:
    """Mutable context for agent tool execution."""

    recommendations: list[InventoryRecommendation] = field(default_factory=list)
    forecasts: dict[str, ForecastResult] = field(default_factory=dict)
    aggregated: dict[str, "pd.Series"] = field(default_factory=dict)
    etl_result: Any = None
    uploaded_orders_bytes: bytes | None = None
    uploaded_config_bytes: bytes | None = None
    last_chart: "go.Figure | None" = None
    messages: list[dict[str, Any]] = field(default_factory=list)


def _build_agent_state_summary(
    recommendations: list[InventoryRecommendation],
    etl_result: Any,
) -> str:
    """Build a text summary of agent state for the LLM."""
    lines = []
    for r in recommendations:
        lines.append(
            f"- {r.sku}: forecast_90d={round(r.forecast_90d_total, 0)}, "
            f"reorder_point={round(r.reorder_point, 0)}, "
            f"current_inv={r.current_inventory}, "
            f"recommendation={r.recommendation}, "
            f"reorder_qty={r.reorder_quantity}"
        )
    alerts = [
        f"{r.sku} below reorder point"
        for r in recommendations
        if r.recommendation == "ORDER_NOW"
    ] + [
        f"{r.sku} low stock"
        for r in recommendations
        if r.recommendation == "LOW_STOCK"
    ]
    summary = f"SKUs: {len(recommendations)}\n" + "\n".join(lines)
    if alerts:
        summary += f"\nAlerts: {', '.join(alerts)}"
    if etl_result and hasattr(etl_result, "rows_loaded"):
        summary += (
            f"\nData quality: {etl_result.rows_loaded} rows loaded, "
            f"{getattr(etl_result, 'rows_dropped_invalid', 0)} invalid dropped, "
            f"{getattr(etl_result, 'rows_dropped_duplicates', 0)} duplicates dropped"
        )
    return summary


def _execute_tool(
    name: str,
    arguments: dict[str, Any],
    context: AgentContext,
    freq: str = "D",
) -> str:
    """Execute a tool and return result string."""
    if name == "run_forecast":
        use_sample = arguments.get("use_sample", True)
        horizon_days = int(arguments.get("horizon_days", 90))

        if use_sample:
            orders_path = Path("data/sample_orders.csv")
            config_path = Path("data/sample_config.json")
            if not orders_path.exists():
                return "Sample data not found. Please upload your own CSV."
            config_path = config_path if config_path.exists() else None
        else:
            if not context.uploaded_orders_bytes:
                return "No file uploaded. Please upload an orders CSV first."
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".csv", delete=False
            ) as f:
                f.write(context.uploaded_orders_bytes)
                orders_path = Path(f.name)
            config_path = None
            if context.uploaded_config_bytes:
                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".json", delete=False
                ) as f:
                    f.write(context.uploaded_config_bytes)
                    config_path = Path(f.name)

        try:
            etl_result = run_etl(
                orders_path=orders_path,
                config_path=config_path,
                freq=freq,
            )
            forecasts = forecast_all_skus(
                etl_result.aggregated, horizon_days=horizon_days
            )
            recommendations = compute_recommendations(
                forecasts, config_path=config_path
            )
        except Exception as e:
            return f"Forecast failed: {e}"

        context.etl_result = etl_result
        context.forecasts = forecasts
        context.aggregated = etl_result.aggregated
        context.recommendations = recommendations
        context.last_chart = None

        return _build_agent_state_summary(recommendations, etl_result)

    elif name == "get_inventory_summary":
        if not context.recommendations:
            return "No forecast has been run yet. Run a forecast first."
        return _build_agent_state_summary(
            context.recommendations, context.etl_result
        )

    elif name == "get_forecast_chart":
        sku = arguments.get("sku", "").strip()
        if not sku:
            return "Please specify a SKU."
        if sku not in context.forecasts:
            available = ", ".join(context.forecasts.keys()) or "none"
            return f"SKU '{sku}' not found. Available: {available}"
        forecast = context.forecasts[sku]
        history = context.aggregated.get(sku, forecast.history)
        fig = plot_forecast(history, forecast, sku)
        context.last_chart = fig
        return f"Chart ready for {sku}."

    return f"Unknown tool: {name}"


def run_agent_turn(
    user_message: str,
    context: AgentContext,
    *,
    freq: str = "D",
) -> tuple[str, Any]:
    """Run one agent turn: process user message, execute tools, return final response.

    Args:
        user_message: User's chat message.
        context: Agent context (mutated in place).
        freq: Aggregation frequency for ETL.

    Returns:
        Tuple of (final_response_text, last_chart or None).
    """
    if context.messages:
        messages = context.messages + [{"role": "user", "content": user_message}]
    else:
        messages = [
            {"role": "user", "content": f"{SYSTEM_PROMPT}\n\nUser: {user_message}"},
        ]

    max_iterations = 10
    for _ in range(max_iterations):
        result = chat(messages, TOOLS)

        tool_calls = result.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("arguments", {})
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}
                tool_result = _execute_tool(tool_name, tool_args, context, freq)
                messages.append(
                    {"role": "assistant", "content": json.dumps(tc)}
                )
                messages.append({"role": "tool", "content": tool_result})
        else:
            response_text = result.get("response", "")
            context.messages = messages + [
                {"role": "assistant", "content": response_text},
            ]
            return response_text, context.last_chart

    return "Maximum iterations reached.", context.last_chart
