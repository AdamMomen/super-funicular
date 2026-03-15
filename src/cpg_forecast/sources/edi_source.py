"""EDI X12 850 source adapter.

Load orders from X12 850 Purchase Order files. Retailer POs (850) are primary
demand signals for CPG brands. Segment mapping:
- BEG05: PO date
- PO102: quantity
- REF*VP or PO108/PO109: vendor part (SKU)
- N1: retailer (channel)
See docs/EDI_INTEGRATION.md for full mapping and VAN/flat-file options.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cpg_forecast.etl import clean_orders


def _parse_850_segments(content: str) -> list[tuple[str, list[str]]]:
    """Parse X12 content into (segment_id, elements) tuples.
    Detects delimiters from ISA segment. Handles * and ~ as default element/segment separators.
    """
    content = content.replace("\n", "").replace("\r", "").strip()
    if not content.startswith("ISA"):
        return []

    # ISA is fixed: first 3 chars = ISA, then element_sep at pos 3, segment_terminator at end of ISA
    elem_sep = content[3:4] if len(content) > 3 else "*"
    # Segment terminator: typically last char of first segment (after ~)
    first_seg_end = content.find("~")
    if first_seg_end >= 0:
        seg_term = "~"
    else:
        seg_term = "\n"
        content = content.replace("\n", "\r\n")

    segments: list[tuple[str, list[str]]] = []
    for raw in content.split(seg_term):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split(elem_sep)
        if parts:
            seg_id = parts[0].strip()
            elements = [p.strip() for p in parts[1:]]
            segments.append((seg_id, elements))
    return segments


def _parse_850_to_rows(path: Path) -> list[dict]:
    """Parse X12 850 file into order rows. Returns list of {order_date, sku, quantity, channel}."""
    text = path.read_text(encoding="utf-8", errors="replace")
    segments = _parse_850_segments(text)

    rows: list[dict] = []
    po_date = ""
    channel = "edi"

    for seg_id, elems in segments:
        if seg_id == "BEG":
            # BEG05 = date (YYYYMMDD), index 4 in elements (0-based)
            if len(elems) >= 5 and elems[4]:
                raw = elems[4]
                if len(raw) >= 8:
                    po_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        elif seg_id == "N1":
            # N101=qualifier, N102=name
            if len(elems) >= 2 and elems[0] in ("BT", "ST") and elems[1]:
                channel = f"edi:{elems[1]}"
        elif seg_id == "PO1":
            # PO102=quantity (index 1), PO108/109=VP/part (indices 5,6 in 0-based elements)
            qty_str = elems[1] if len(elems) > 1 else ""
            sku = ""
            if len(elems) >= 7 and elems[5] == "VP":
                sku = elems[6] or ""
            if not sku and len(elems) >= 7:
                sku = elems[6] or ""  # PO107 buyer part fallback
            if not sku and len(elems) >= 2:
                sku = elems[0] or ""  # PO101 line ID fallback
            try:
                qty = int(float(qty_str)) if qty_str else 0
            except (ValueError, TypeError):
                qty = 0
            if sku and qty > 0 and po_date:
                rows.append({
                    "order_date": po_date,
                    "sku": sku,
                    "quantity": qty,
                    "channel": channel,
                })

    return rows


class EdiSourceAdapter:
    """Load orders from X12 850 Purchase Order files."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load_orders(self) -> pd.DataFrame:
        """Parse 850 and return orders as DataFrame with order_date, sku, quantity, channel."""
        if not self.path.exists():
            raise FileNotFoundError(f"EDI file not found: {self.path}")

        rows = _parse_850_to_rows(self.path)
        if not rows:
            return clean_orders(pd.DataFrame(columns=["order_date", "sku", "quantity", "channel"]))

        df = pd.DataFrame(rows)
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
        df = df.dropna(subset=["order_date"])
        return clean_orders(df)

    def get_name(self) -> str:
        return f"edi:850:{self.path.name}"
