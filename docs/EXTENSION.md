# Extension Roadmap: From Demo to Corvera-Style Production

This document outlines how the minimal demand forecasting demo could extend into a full Corvera-style agentic operations platform.

## Current state

The demo implements:

- **ETL**: CSV → clean → aggregate → time series per SKU (with `SourceAdapter` for extensibility)
- **Forecast**: Holt-Winters (or moving average fallback) → 90-day demand
- **Inventory**: Reorder point, safety stock, MOQ-aware recommendations
- **Output**: HTML report + JSON + **Agent API** (`GET/POST /forecast` returns structured state)

## Data integration extensions

### 1. Multi-source ingestion

| Source            | Integration approach                    | Data extracted                    |
| ----------------- | --------------------------------------- | -------------------------------- |
| **Shopify API**   | OAuth + REST/GraphQL                    | Orders, inventory, products      |
| **EDI (X12 850)** | File drop or SFTP + parser              | POs, ASNs, invoices              |
| **Email**         | IMAP + LLM extraction or templates     | Supplier confirmations, lead times|
| **Airtable**      | REST API                                | Inventory snapshots, SKU metadata|
| **QuickBooks/Xero** | OAuth + API                           | Invoices, payments               |

### 2. Unified schema

A canonical operational model that all sources map into:

```
Order: order_id, source, order_date, sku, quantity, channel, customer_id, ...
InventorySnapshot: sku, warehouse, quantity, snapshot_date, source
SupplierPO: po_id, sku, quantity, order_date, expected_date, status, ...
```

The ETL layer becomes a set of **source adapters** that normalize into this schema. The forecasting and inventory logic operate on the unified view.

### 3. Incremental and real-time

- **Batch**: Nightly sync from Shopify, EDI files, Airtable
- **Streaming**: Webhooks for new orders, inventory changes
- **Idempotency**: Dedupe by (source, external_id), handle late-arriving data

## Agentic extensions

### 4. Agent-ready state

The forecast and recommendations become **structured state** an LLM agent can reason over:

```json
{
  "skus": [
    {
      "sku": "SKU-001",
      "forecast_90d": 1200,
      "reorder_point": 180,
      "current_inventory": 50,
      "recommendation": "ORDER_NOW",
      "reorder_qty": 200,
      "lead_time_days": 14
    }
  ],
  "alerts": ["SKU-001 below reorder point", "SKU-003 out of stock"],
  "last_updated": "2024-03-14T12:00:00Z"
}
```

The agent receives this state and can:

- Draft POs for approval
- Send alerts to ops
- Answer questions ("When will we run out of SKU-001?")
- Coordinate with logistics for inbound shipments

### 5. Reliability and correctness

For agentic systems, **garbage-in-garbage-out** is critical. The pipeline must:

- **Validate** inputs (schema, ranges, referential integrity)
- **Log** data quality metrics (missing values, outliers, staleness)
- **Version** forecasts and recommendations (audit trail)
- **Handle failures** gracefully (retry, dead-letter, alerting)

### 6. Multi-warehouse and channel

- Forecast by (sku, warehouse) or (sku, channel)
- Cross-warehouse transfer recommendations
- Channel-specific demand (DTC vs retail vs wholesale) with different seasonality

## Modeling extensions

### 7. Richer forecasting

- **Prophet**: Holiday effects, trend changes, regressors (promo flags, marketing spend)
- **Ensemble**: Combine Holt-Winters, Prophet, naive
- **Cannibalization**: New SKU launch affects incumbent demand
- **External signals**: Weather, events, competitor activity

### 8. Promotions and seasonality

- Configurable promo windows (start, end, uplift %)
- Monthly/quarterly seasonality for seasonal CPG
- Retailer-specific calendars (e.g., Walmart reset dates)

## Implementation priority

For a production Corvera-style system:

1. **Unified schema + source adapters** — Foundation for all other work
2. **Shopify + one EDI source** — Covers most mid-market CPG
3. **Agent state API** — Expose forecasts/recommendations as JSON for agent consumption
4. **Data quality and observability** — Logging, metrics, alerting
5. **Prophet or ensemble** — Better forecast accuracy for production

The demo’s clean separation (ETL | forecast | inventory | viz) makes each of these extensions a modular addition rather than a rewrite.
