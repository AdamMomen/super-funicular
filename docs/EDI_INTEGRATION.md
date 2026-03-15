# EDI X12 850 Integration

This document describes how X12 850 Purchase Order (PO) files integrate with the CPG demand forecasting pipeline.

## Why 850?

Retailer POs are **committed demand**—the primary signal for CPG brands selling into retail. When Walmart, Target, or a regional distributor sends an 850, they're telling you exactly what they've ordered. That's demand you can forecast against.

The X12 850 is the standard EDI transaction for Purchase Orders. CPG brands receive 850s via:

- **VANs** (Value-Added Networks): SPS Commerce, TrueCommerce, OpenText—translate and route EDI between trading partners
- **Direct EDI**: AS2, SFTP, or API from larger retailers
- **Flat files**: Many VANs and middleware export 850 data to CSV/Excel for brands that don't parse EDI natively

## Segment Mapping

We map X12 850 segments to our canonical order schema:

| X12 Segment | Element | Our Field | Notes |
|-------------|---------|-----------|-------|
| BEG | BEG05 | `order_date` | PO date, format YYYYMMDD → YYYY-MM-DD |
| PO1 | PO102 | `quantity` | Quantity ordered |
| PO1 | PO108/PO109 (REF*VP) | `sku` | Vendor part number (preferred) |
| PO1 | PO106/PO107 | `sku` | Buyer part number (fallback) |
| PO1 | PO101 | `sku` | Line ID (last resort) |
| N1 | N102 | `channel` | Retailer name (BT=bill-to, ST=ship-to) |
| DTM | DTM02 (qual 002) | `order_date` | Line-level requested delivery (optional) |

When REF*VP (vendor part) is present in the PO1 loop, we use it as the SKU. Otherwise we fall back to buyer part number or line ID.

## How Brands Get EDI Data

In practice, many mid-market CPG brands receive EDI in one of these forms:

1. **Raw 850 files** — Dropped to SFTP, emailed, or pulled from a VAN mailbox
2. **Flat file exports** — CSV/Excel from SPS Commerce, TrueCommerce, or similar, with columns like `po_date`, `sku`, `quantity`, `retailer_id`
3. **API/webhook** — Some VANs offer REST APIs or webhooks that push normalized PO data

The "EDI-ready" CSV format—columns `order_date`, `sku`, `quantity`, `channel`—is a zero-code path: export from your VAN or middleware, upload to this tool. No EDI parsing required.

## Integration Options

| Option | Description | Status |
|--------|-------------|--------|
| **File upload** | User uploads .edi or .x12 file via API or web app | Implemented |
| **SFTP drop** | Poll an SFTP directory for new 850 files | Future |
| **VAN webhook** | Receive 850 payloads via HTTP | Future |

We start with file upload. Same pipeline as CSV: `EdiSourceAdapter` → `run_etl` → forecast → recommendations.

## Fit with the Demo

The ETL layer uses a **SourceAdapter** protocol. CSV, EDI, and Shopify (stub) all implement `load_orders()` → DataFrame with `order_date`, `sku`, `quantity`, `channel`. The forecasting and inventory logic operate on this unified view.

```
EDI 850 file → EdiSourceAdapter → run_etl → forecast_all_skus → compute_recommendations
```

No changes to the forecast model or inventory logic. EDI is just another source.

## Sample Data

Free X12 850 samples are available from:

- [Babelway](https://www.babelway.com/edi-transaction-code/edi-850/) — Copyable 4010 sample
- [Stedi](https://www.stedi.com/edi/x12-004010/850) — Spec and examples
- [EDI2XML](https://www.edi2xml.com/edi-850-purchase-order/) — Sample with segment breakdown

The repo includes `data/sample_850.edi` (Babelway format) for tests and manual demos. We use a built-in X12 segment parser (no external EDI library dependency).
