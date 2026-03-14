# CPG Demand Forecast

A minimal demand forecasting module for consumer packaged goods (CPG) brands. Upload your historical order data, get a 90-day demand forecast and inventory reorder recommendations—no spreadsheets required.

## What this does

For CPG founders and ops teams: this tool ingests your order history (CSV), applies a time-series model, and outputs:

- **90-day demand forecast** per SKU
- **Reorder recommendations** with lead times, safety stock, and MOQ awareness
- **Visual summary** (HTML report with interactive charts)

Designed to demonstrate the data pipeline thinking required for unified operational visibility—the foundation that an AI agent can act on.

## Quick start

```bash
# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# Run with sample data
cpg-forecast data/sample_orders.csv --config data/sample_config.json -o output/report.html

# Or output JSON only
cpg-forecast data/sample_orders.csv --config data/sample_config.json -f json -o output/recommendations.json
```

Open `output/report.html` in a browser to see the forecast charts and recommendation table.

## Input format

### Orders CSV

| Column       | Type              | Required | Description              |
| ------------ | ----------------- | -------- | ------------------------ |
| `order_date` | date (YYYY-MM-DD) | Yes      | Order placement date     |
| `sku`        | string            | Yes      | Product SKU identifier   |
| `quantity`   | integer           | Yes      | Units ordered            |
| `channel`    | string            | No       | DTC, retail, wholesale   |
| `customer_id`| string            | No       | For future segmentation  |

Example:

```csv
order_date,sku,quantity,channel
2024-01-15,SKU-001,120,DTC
2024-01-16,SKU-001,45,retail
2024-01-17,SKU-002,200,wholesale
```

### Config JSON (optional)

Provides lead times, safety stock, current inventory, and MOQs per SKU:

```json
{
  "default_lead_time_days": 14,
  "default_safety_stock_days": 7,
  "default_moq": 1,
  "skus": {
    "SKU-001": {
      "lead_time_days": 14,
      "safety_stock_days": 7,
      "current_inventory": 50,
      "moq": 100
    }
  }
}
```

## Output

- **HTML report**: Summary table + Plotly charts (history + 90-day forecast per SKU)
- **JSON**: Array of recommendations with `sku`, `forecast_90d_total`, `reorder_point`, `reorder_quantity`, `recommendation` (ORDER_NOW | LOW_STOCK | OK)

## Technical details

### ETL pipeline

1. **Load** — Parse CSV, validate required columns, coerce dates and quantities
2. **Clean** — Normalize SKUs, filter invalid quantities, drop duplicates
3. **Aggregate** — Group by (sku, date), resample to daily/weekly, fill gaps with 0

### Forecasting model

- **Holt-Winters exponential smoothing** (statsmodels) with additive trend and weekly seasonality when sufficient data (≥30 points)
- **Fallback**: Simple moving average for sparse data
- Model choice is defendable for CPG: demand often has trend + weekly patterns (e.g., DTC weekend spikes)

### Inventory logic

- **Reorder point** = lead time demand + safety stock
- **Safety stock** = z × σ × √(lead_time) when std available, else days × daily_avg
- **Reorder quantity** = max(MOQ, ceil(shortfall / MOQ) × MOQ) when below reorder point
- Service level: 95% (z ≈ 1.65)

### Limitations

- Single-SKU modeling; no multi-SKU correlation or cannibalization
- No promotion or explicit seasonality flags in this demo
- Assumes stationary lead times; real CPG has variable supplier lead times
- For production: consider Prophet for holiday effects, or ensemble methods

### Extension points

- Channel-level forecasts (DTC vs retail vs wholesale)
- Multi-warehouse support
- Configurable seasonality (monthly, quarterly)
- Integration hooks for Shopify API, EDI feeds, email ingestion

## How this maps to Corvera

Corvera’s product is an AI-powered operations platform for CPG brands. The core challenge is **data fragmentation**: supplier confirmations in email, inventory in Airtable, sales in Shopify exports—all glued together by an overworked ops hire.

This demo shows the first step: a pipeline that ingests order data, cleans and aggregates it, and produces a unified operational picture. The same ETL and data model could extend to:

- **Shopify API** — Pull orders directly instead of CSV exports
- **EDI feeds** — Retailer order and shipment data
- **Email ingestion** — Supplier confirmations, PO acknowledgments
- **Accounting systems** — Invoice and payment data

The output—forecasts and reorder recommendations—is the state an AI agent would act on: triggering POs, sending alerts, or coordinating with logistics. The data integration layer is where the product either wins or loses.

See [docs/EXTENSION.md](docs/EXTENSION.md) for a deeper technical roadmap.

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Web app (Streamlit)

```bash
pip install -e .
streamlit run app.py
```

Open http://localhost:8501. Upload a CSV (and optional config JSON), or use the bundled sample data.

## Deployment (Coolify)

1. **New Application** in Coolify → **Dockerfile** (build from repo)
2. Set **Base Directory** if the Dockerfile is not in the repo root
3. In **Network** settings, set **Port** to `8501`
4. Build and deploy

The app listens on port 8501. Coolify will proxy traffic to it.

Optional: Set up GitHub Actions for CI/CD—build the image, push to GHCR, then trigger Coolify’s deployment webhook.

## License

MIT
