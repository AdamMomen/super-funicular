"""Visualization: Plotly charts and HTML report generation."""

from __future__ import annotations

import base64
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from cpg_forecast.forecast import ForecastResult
from cpg_forecast.inventory import InventoryRecommendation


def plot_forecast(
    history: pd.Series,
    forecast: ForecastResult,
    sku: str,
    *,
    showlegend_history: bool = True,
    showlegend_forecast: bool = True,
) -> go.Figure:
    """Create Plotly figure: history + 90-day forecast.

    Args:
        history: Historical demand series.
        forecast: Forecast result with forecast series.
        sku: SKU label.
        showlegend_history: Whether to show historical trace in legend.
        showlegend_forecast: Whether to show forecast trace in legend.

    Returns:
        Plotly Figure.
    """
    fig = go.Figure()

    # History
    fig.add_trace(
        go.Scatter(
            x=history.index,
            y=history.values,
            mode="lines+markers",
            name="Historical demand",
            legendgroup="historical",
            showlegend=showlegend_history,
            line=dict(color="#2563eb", width=2),
            marker=dict(size=4),
        )
    )

    # Forecast
    fig.add_trace(
        go.Scatter(
            x=forecast.forecast.index,
            y=forecast.forecast.values,
            mode="lines",
            name="90-day forecast",
            legendgroup="forecast",
            showlegend=showlegend_forecast,
            line=dict(color="#dc2626", width=2, dash="dash"),
        )
    )

    fig.update_layout(
        title=f"Demand forecast: {sku}",
        xaxis_title="Date",
        yaxis_title="Units",
        hovermode="x unified",
        template="plotly_white",
        height=400,
        margin=dict(l=60, r=40, t=60, b=60),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    )

    return fig


def _fig_to_json_safe(fig: go.Figure) -> dict:
    """Convert figure to JSON-serializable dict with plain arrays (no bdata)."""
    d = fig.to_dict()
    # Recursively convert numpy arrays and bdata dicts to plain lists
    def _convert(obj):
        if isinstance(obj, dict):
            if "bdata" in obj and "dtype" in obj:
                buf = base64.b64decode(obj["bdata"])
                arr = np.frombuffer(buf, dtype=obj.get("dtype", "float64"))
                if "shape" in obj:
                    arr = arr.reshape(obj["shape"])
                return arr.tolist()
            return {k: _convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_convert(x) for x in obj]
        if hasattr(obj, "tolist"):
            return obj.tolist()
        return obj

    return _convert(d)


def plot_charts_by_sku(
    forecasts: dict[str, ForecastResult],
    aggregated: dict[str, pd.Series],
) -> dict[str, dict]:
    """Create one chart per SKU. Returns dict of SKU -> Plotly figure as JSON-serializable dict."""
    result: dict[str, dict] = {}
    for sku in forecasts:
        forecast = forecasts[sku]
        history = aggregated.get(sku, forecast.history)
        fig = plot_forecast(history, forecast, sku)
        result[sku] = _fig_to_json_safe(fig)
    return result


def plot_all_skus(
    forecasts: dict[str, ForecastResult],
    aggregated: dict[str, pd.Series],
) -> go.Figure:
    """Create subplot grid with one chart per SKU.

    Args:
        forecasts: Dict from forecast_all_skus.
        aggregated: Dict from ETL (for history).

    Returns:
        Plotly Figure with subplots.
    """
    skus = list(forecasts.keys())
    n = len(skus)
    if n == 0:
        return go.Figure()

    fig = make_subplots(
        rows=n,
        cols=1,
        subplot_titles=[f"SKU: {s}" for s in skus],
        vertical_spacing=0.08,
        row_heights=[1] * n,
    )

    for i, sku in enumerate(skus):
        forecast = forecasts[sku]
        history = aggregated.get(sku, forecast.history)
        # Only show legend for first SKU; legendgroup groups traces so one entry per type
        subfig = plot_forecast(
            history,
            forecast,
            sku,
            showlegend_history=(i == 0),
            showlegend_forecast=(i == 0),
        )
        for trace in subfig.data:
            fig.add_trace(trace, row=i + 1, col=1)

    fig.update_layout(
        title_text="90-day demand forecast by SKU",
        height=400 * n,
        showlegend=True,
        template="plotly_white",
    )
    fig.update_xaxes(matches="x")

    return fig


def generate_report(
    recommendations: list[InventoryRecommendation],
    forecasts: dict[str, ForecastResult],
    aggregated: dict[str, pd.Series],
    output_path: Path,
) -> None:
    """Generate HTML report with charts and recommendation table.

    Args:
        recommendations: From compute_recommendations.
        forecasts: From forecast_all_skus.
        aggregated: From ETL.
        output_path: Path to write HTML file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Summary table
    table_data = [
        {
            "SKU": r.sku,
            "90-day forecast": round(r.forecast_90d_total, 0),
            "Daily avg": round(r.daily_avg, 1),
            "Reorder point": round(r.reorder_point, 0),
            "Reorder qty": r.reorder_quantity,
            "Current inv": r.current_inventory,
            "Recommendation": r.recommendation,
            "Days to stockout": round(r.days_until_stockout, 1) if r.days_until_stockout else "-",
        }
        for r in recommendations
    ]
    df = pd.DataFrame(table_data)

    # Build HTML
    fig = plot_all_skus(forecasts, aggregated)
    charts_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    table_html = df.to_html(index=False, classes="table", border=0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CPG Demand Forecast — 90-day Inventory Recommendations</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 1200px; margin: 0 auto; padding: 2rem; }}
        h1 {{ color: #1e293b; margin-bottom: 0.5rem; }}
        .subtitle {{ color: #64748b; margin-bottom: 2rem; }}
        table {{ width: 100%; border-collapse: collapse; margin: 2rem 0; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f8fafc; font-weight: 600; color: #475569; }}
        .ORDER_NOW {{ color: #dc2626; font-weight: 600; }}
        .LOW_STOCK {{ color: #d97706; font-weight: 600; }}
        .OK {{ color: #16a34a; }}
    </style>
</head>
<body>
    <h1>CPG Demand Forecast</h1>
    <p class="subtitle">90-day inventory recommendations based on historical order data</p>

    <h2>Summary</h2>
    {table_html}

    <h2>Forecast by SKU</h2>
    {charts_html}
</body>
</html>
"""

    output_path.write_text(html, encoding="utf-8")
