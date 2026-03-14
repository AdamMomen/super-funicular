"""CLI entrypoint for CPG demand forecasting pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from cpg_forecast.etl import run_etl
from cpg_forecast.forecast import forecast_all_skus
from cpg_forecast.inventory import compute_recommendations
from cpg_forecast.viz import generate_report

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the full pipeline from CSV to report."""
    parser = argparse.ArgumentParser(
        description="CPG Demand Forecast: ingest order CSV, forecast 90-day demand, output inventory recommendations.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to historical orders CSV",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        help="Path to config JSON (lead times, MOQs, current inventory)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("output/report.html"),
        help="Output path for HTML report (default: output/report.html)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["html", "json"],
        default="html",
        help="Output format: html (report with charts) or json (recommendations only)",
    )
    parser.add_argument(
        "--freq",
        choices=["D", "W"],
        default="D",
        help="Aggregation frequency: D (daily) or W (weekly)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=90,
        help="Forecast horizon in days (default: 90)",
    )

    args = parser.parse_args()

    if not args.input.exists():
        logger.error("Input file not found: %s", args.input)
        sys.exit(1)

    logger.info("Running ETL on %s", args.input)
    etl_result = run_etl(args.input, config_path=args.config, freq=args.freq)
    logger.info("Aggregated %d rows into %d SKUs", etl_result.raw_row_count, len(etl_result.skus))

    logger.info("Forecasting %d-day horizon", args.horizon)
    forecasts = forecast_all_skus(etl_result.aggregated, horizon_days=args.horizon)

    logger.info("Computing inventory recommendations")
    recommendations = compute_recommendations(forecasts, config_path=args.config)

    if args.format == "json":
        output_data = [
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
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
        logger.info("Wrote JSON to %s", args.output)
    else:
        generate_report(
            recommendations,
            forecasts,
            etl_result.aggregated,
            args.output,
        )
        logger.info("Wrote HTML report to %s", args.output)


if __name__ == "__main__":
    main()
