"""Tests for EDI X12 850 source adapter."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from cpg_forecast.etl import run_etl
from cpg_forecast.sources.edi_source import EdiSourceAdapter, _parse_850_segments, _parse_850_to_rows


def test_parse_850_segments():
    """Parse X12 content into segment tuples."""
    content = "ISA*00* *00* *01*123*ZZ*ABC*161206*2115*U*00401*1*0*P*:~GS*PO*1*ABC*20161206*2115*1*X*004010~ST*850*0001~BEG*00*DS*PO1**20161206~PO1*1*10*EA*8.90**VP*SKU-001~SE*5*0001~GE*1*1~IEA*1*1~"
    segments = _parse_850_segments(content)
    seg_ids = [s[0] for s in segments]
    assert "BEG" in seg_ids
    assert "PO1" in seg_ids
    po1 = next(s for s in segments if s[0] == "PO1")
    elems = po1[1]
    assert elems[1] == "10"  # quantity (PO102)
    assert elems[5] == "VP"  # vendor part qualifier (PO108)
    assert elems[6] == "SKU-001"  # vendor part number (PO109)


def test_parse_850_to_rows():
    """Extract order rows from 850 content."""
    content = """ISA*00*          *00*          *01*085767000      *ZZ*Company        *161206*2115*U*00401*000005007*0*P*:~
GS*PO*085767338*Company*20161206*2115*5007*X*004010~
ST*850*0001~
BEG*00*DS*5907867**20161206~
N1*BT*RetailerX*92*123~
PO1*1*5*EA*8.90**VP*SKU-001~
PO1*2*3*EA*4.50**VP*SKU-002~
SE*22*0001~
GE*1*5007~
IEA*1*000005007~"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".edi", delete=False) as f:
        f.write(content)
        path = Path(f.name)
    try:
        rows = _parse_850_to_rows(path)
        assert len(rows) == 2
        assert rows[0]["order_date"] == "2016-12-06"
        assert rows[0]["sku"] == "SKU-001"
        assert rows[0]["quantity"] == 5
        assert "RetailerX" in rows[0]["channel"]
        assert rows[1]["sku"] == "SKU-002"
        assert rows[1]["quantity"] == 3
    finally:
        path.unlink(missing_ok=True)


def test_edi_source_adapter_sample_850():
    """EdiSourceAdapter parses sample_850.edi correctly."""
    sample_path = Path(__file__).parent.parent / "data" / "sample_850.edi"
    if not sample_path.exists():
        pytest.skip("data/sample_850.edi not found")

    adapter = EdiSourceAdapter(sample_path)
    df = adapter.load_orders()

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["order_date", "sku", "quantity", "channel"]
    assert len(df) >= 1
    assert df["sku"].iloc[0] == "32230538"
    assert df["quantity"].iloc[0] == 1
    assert adapter.get_name().startswith("edi:850:")


def test_run_etl_with_edi_source():
    """run_etl accepts EdiSourceAdapter and produces aggregated data."""
    sample_path = Path(__file__).parent.parent / "data" / "sample_850.edi"
    if not sample_path.exists():
        pytest.skip("data/sample_850.edi not found")

    source = EdiSourceAdapter(sample_path)
    result = run_etl(source=source, freq="D")

    assert result.raw_row_count >= 1
    assert len(result.skus) >= 1
    assert "32230538" in result.skus
    assert "aggregated" in dir(result)
