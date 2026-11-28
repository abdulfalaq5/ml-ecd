"""Offset sensor PWD (section) + pita ECD potensial saat pack-off."""
import numpy as np
import pandas as pd

from app.anomaly import detectors as D
from app.core.sections import clean_sections, section_value_series


def test_pwd_offset_section_field_and_default():
    secs = clean_sections([{"from_md": 0, "hole_size": 12.25}, {"from_md": 3000, "hole_size": 8.5, "pwd_offset_ft": 62}])
    idx = pd.date_range("2026-11-20", periods=3, freq="1h", tz="UTC")
    hole = pd.Series([1000.0, 3000.0, 3500.0], index=idx)
    assert section_value_series(secs, hole, "pwd_offset_ft", 40.0).tolist() == [40.0, 62.0, 62.0]


def test_pwd_offset_validated():
    import pytest
    with pytest.raises(ValueError):
        clean_sections([{"from_md": 0, "hole_size": 8.5, "pwd_offset_ft": 999}])


def _frame(spike_psi=800.0):
    n = 240
    idx = pd.date_range("2026-11-17 10:00", periods=n, freq="30s", tz="UTC")
    d = pd.DataFrame(index=idx)
    d["state"] = "REAM"
    d["flow_in"] = 450.0
    d["spp"] = 2200.0
    d.loc[d.index[200:], "spp"] = 2200.0 + spike_psi          # SPP naik di flow sama
    d["torque"], d["rpm"], d["hookload"], d["wob"], d["block_vel"] = 5.0, 60.0, 100.0, 2.0, 0.0
    d["bit_depth"] = d["hole_depth"] = 5400.0
    d["tvd_bit"] = 4000.0
    d["ecd_pred"] = 10.1
    d["fg_bit"] = 13.4
    return d


def test_packoff_potential_matches_spp_excess():
    d = _frame(800.0)
    out = D.run(d)
    po = out["packoff_potential"]
    full = 800.0 / (0.052 * 4000.0)                              # ≈ 3,85 ppg
    assert abs(po["spp_excess"].iloc[-1] - 800.0) < 1.0
    assert abs(po["ecd_po_hi"].iloc[-1] - (10.1 + full)) < 0.01   # batas atas ≈ 13,95 (> FG 13,4)
    assert abs(po["ecd_po"].iloc[-1] - (10.1 + 0.2 * full)) < 0.01  # estimasi α 0,2 ≈ 10,87
    assert po["ecd_po"].iloc[:190].isna().all()                  # hanya saat pack-off aktif
    ep = [e for e in out["detections"] if e["detector"] == "packoff"]
    assert ep and "MELEBIHI FG" not in ep[0]["po_note"] and "batas atas" in ep[0]["po_note"]
    out = D.run(d, {"po_transmission": 1.0})
    assert "MELEBIHI FG" in [e for e in out["detections"] if e["detector"] == "packoff"][0]["po_note"]


def test_no_band_without_packoff():
    out = D.run(_frame(0.0))
    assert out["packoff_potential"]["ecd_po"].isna().all()
