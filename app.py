"""Streamlit app for CPG demand forecasting."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from cpg_forecast.etl import run_etl
from cpg_forecast.forecast import forecast_all_skus
from cpg_forecast.inventory import compute_recommendations
from cpg_forecast.viz import plot_forecast

st.set_page_config(
    page_title="CPG Demand Forecast",
    page_icon="📊",
    layout="wide",
)

st.title("CPG Demand Forecast")
st.caption("Upload your order history, get a 90-day forecast and reorder recommendations.")

# Sidebar
with st.sidebar:
    st.header("Settings")
    horizon_days = st.number_input(
        "Forecast horizon (days)",
        min_value=30,
        max_value=180,
        value=90,
        step=7,
    )
    freq = st.radio("Aggregation frequency", ["D", "W"], format_func=lambda x: "Daily" if x == "D" else "Weekly")
    st.divider()
    st.header("Sample data")
    use_sample = st.checkbox("Run with sample data", value=False)

# File upload or sample
orders_file = None
config_file = None

if use_sample:
    sample_orders = Path("data/sample_orders.csv")
    sample_config = Path("data/sample_config.json")
    if sample_orders.exists() and sample_config.exists():
        orders_file = sample_orders
        config_file = sample_config
        st.info("Using bundled sample data. Click **Run forecast** below.")
    else:
        st.error("Sample data not found. Upload your own files.")
else:
    col1, col2 = st.columns(2)
    with col1:
        uploaded_orders = st.file_uploader(
            "Orders CSV (required)",
            type=["csv"],
            help="Columns: order_date, sku, quantity. Optional: channel, customer_id",
        )
    with col2:
        uploaded_config = st.file_uploader(
            "Config JSON (optional)",
            type=["json"],
            help="Lead times, MOQs, current inventory per SKU",
        )

    if uploaded_orders:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
            f.write(uploaded_orders.getvalue())
            orders_file = Path(f.name)

    if uploaded_config:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
            f.write(uploaded_config.getvalue())
            config_file = Path(f.name)

# Run button
run = st.button("Run forecast", type="primary")

if run:
    if orders_file is None or (not use_sample and not uploaded_orders):
        st.error("Please upload an orders CSV or use sample data.")
    else:
        config_path = config_file if config_file and config_file.exists() else None

        with st.spinner("Running ETL, forecasting, and computing recommendations..."):
            try:
                etl_result = run_etl(orders_path=orders_file, config_path=config_path, freq=freq)
                forecasts = forecast_all_skus(etl_result.aggregated, horizon_days=horizon_days)
                recommendations = compute_recommendations(forecasts, config_path=config_path)
            except Exception as e:
                st.error(f"Pipeline failed: {e}")
                st.exception(e)
                st.stop()

        st.success(f"Aggregated {etl_result.raw_row_count} rows into {len(etl_result.skus)} SKUs.")

        # Summary table
        st.subheader("Inventory recommendations")
        table_data = [
            {
                "SKU": r.sku,
                "90-day forecast": round(r.forecast_90d_total, 0),
                "Daily avg": round(r.daily_avg, 1),
                "Reorder point": round(r.reorder_point, 0),
                "Reorder qty": r.reorder_quantity,
                "Current inv": r.current_inventory,
                "Recommendation": r.recommendation,
                "Days to stockout": round(r.days_until_stockout, 1) if r.days_until_stockout is not None else "-",
            }
            for r in recommendations
        ]
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Per-SKU charts
        st.subheader("Forecast by SKU")
        for sku in etl_result.skus:
            forecast = forecasts[sku]
            history = etl_result.aggregated.get(sku, forecast.history)
            fig = plot_forecast(history, forecast, sku)
            st.plotly_chart(fig, use_container_width=True)

        # JSON download
        json_data = [
            {
                "sku": r.sku,
                "forecast_90d_total": round(r.forecast_90d_total, 2),
                "daily_avg": round(r.daily_avg, 2),
                "reorder_point": round(r.reorder_point, 2),
                "reorder_quantity": r.reorder_quantity,
                "current_inventory": r.current_inventory,
                "recommendation": r.recommendation,
                "days_until_stockout": round(r.days_until_stockout, 2) if r.days_until_stockout else None,
            }
            for r in recommendations
        ]
        st.download_button(
            label="Download recommendations (JSON)",
            data=json.dumps(json_data, indent=2),
            file_name="recommendations.json",
            mime="application/json",
        )
