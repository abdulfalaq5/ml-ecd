"""Uji data section per sumur (app/core/sections.py)."""
import pytest

from app.core import sections as sec

ROWS = [{"from_md": 1500, "hole_size": 8.5, "shoe_md": 1495, "pv": 18, "yp": 20},
        {"from_md": 0, "hole_size": 12.25, "preset": "BHA_12.25_STD"}]


def test_clean_sorts_and_fills():
    out = sec.clean_sections(ROWS)
    assert [r["from_md"] for r in out] == [0, 1500]
    assert out[0]["preset"] == "BHA_12.25_STD" and out[0]["pv"] is None and out[1]["casing_id"] is None
    assert sec.clean_sections([]) == [] and sec.clean_sections(None) == []


@pytest.mark.parametrize("bad", [
    [{"from_md": 0}],                                                  # ukuran lubang wajib
    [{"from_md": 0, "hole_size": 8.5, "pv": 15}],                      # PV tanpa YP
    [{"from_md": 0, "hole_size": 8.5, "preset": "TIDAK_ADA"}],
    [{"from_md": 100, "hole_size": 8.5}, {"from_md": 100, "hole_size": 6.125}],
    [{"from_md": 1000, "hole_size": 8.5, "shoe_md": 3000}],            # shoe di bawah awal section
    [{"from_md": 0, "hole_size": "x"}],
])
def test_clean_rejects(bad):
    with pytest.raises(ValueError):
        sec.clean_sections(bad)


def test_section_at_hole_depth():
    rows = sec.clean_sections(ROWS)
    assert sec.section_at(rows, 800)["hole_size"] == 12.25
    assert sec.section_at(rows, 1500)["hole_size"] == 8.5
    assert sec.section_at(rows, None) is None and sec.section_at([], 500) is None
    assert sec.section_at(sec.clean_sections([{"from_md": 500, "hole_size": 8.5}]), 100) is None


def test_add_features_hole_size_from_sections():
    import numpy as np
    import pandas as pd
    from app.core.features import add_features
    idx = pd.date_range("2026-11-01", periods=6, freq="30s", tz="UTC")
    hole = [1400.0, 1499.0, 1501.0, 1600.0, 1300.0, 1700.0]       # 1300 = bit/hole turun (trip), lubang tetap 8,5"
    df = pd.DataFrame({"flow_in": 500.0, "bit_depth": hole, "hole_depth": hole}, index=idx)
    mw = pd.DataFrame({"md": [0.0], "mw": [9.0]})
    sv = pd.DataFrame(columns=["md", "tvd", "inc", "azi", "dls"])
    out = add_features(df, mw, sv, sec.clean_sections(ROWS))
    assert list(out["hole_size"]) == [12.25, 12.25, 8.5, 8.5, 8.5, 8.5]
    assert add_features(df, mw, sv)["hole_size"].isna().all()
