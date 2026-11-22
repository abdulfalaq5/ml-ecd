"""Uji modul estimasi bending / side force (app/core/bending.py) dengan geometri sintetis yang jawabannya diketahui."""
import math

import numpy as np
import pandas as pd
import pytest

from app.core import bending as bd


def survey(dls_per100: float, kop: float = 1000.0, td: float = 3000.0, step: float = 100.0) -> pd.DataFrame:
    """Vertikal sampai KOP, lalu build konstan `dls_per100` °/100 ft di azimuth 90°."""
    md = np.arange(0, td + step, step)
    inc = np.clip((md - kop) * dls_per100 / 100, 0, None)
    return pd.DataFrame({"md": md, "inc": inc, "azi": 90.0})


def one_run(items, **cfg):
    return bd.Run(0.0, "uji", bd.comps_from_list(items), {"friction": {"cased": 0.2, "open": 0.3}, **cfg})


DP5 = {"name": "DP 5", "od": 5.0, "id": 4.276, "weight_ppf": 22.6, "length": None, "bha": False}


def test_dls_min_curvature_matches_build_rate():
    sv = bd.prep_survey(survey(3.0))
    build = sv[(sv.md >= 1000) & (sv.md < 2900)]
    assert np.allclose(build["dls_calc"], 3.0, atol=1e-6)
    assert np.allclose(sv[sv.md < 1000]["dls_calc"], 0.0)


def test_bending_moment_equals_EI_kappa():
    hole = bd.Hole(bd.prep_survey(survey(6.0)))
    prof = bd.depth_profile(hole, one_run([DP5]), np.array([2500.0]), lambda md: np.nan)
    I = math.pi / 64 * (5 ** 4 - 4.276 ** 4)
    k = 6 * math.pi / 180 / 1200                      # rad/in
    assert prof["BND_STR_EST"].iloc[0] == pytest.approx(30e6 * I * k / 12000, rel=1e-6)    # ≈ 3,1 kft·lbf
    assert prof["BSTR_MAX_EST"].iloc[0] == pytest.approx(30e6 * k * 2.5 / 1000, rel=1e-6)  # ≈ 6,5 ksi


def test_vertical_hookload_equals_buoyed_weight_no_side_force():
    sv = pd.DataFrame({"md": [0, 5000], "inc": [0, 0], "azi": [0, 0]})
    hole = bd.Hole(bd.prep_survey(sv))
    prof = bd.depth_profile(hole, one_run([DP5]), np.array([3000.0]), lambda md: 10.0)
    w = 22.6 * 3000 * (1 - 10 / 65.5) / 1000
    for m in ("HKLD_PU", "HKLD_SO", "HKLD_ROT"):
        assert prof[m].iloc[0] == pytest.approx(w, rel=1e-6)
    assert prof["SF_MAX_EST"].iloc[0] == pytest.approx(0.0, abs=1e-9)


def test_friction_spreads_pickup_and_slackoff():
    hole = bd.Hole(bd.prep_survey(survey(3.0)))
    prof = bd.depth_profile(hole, one_run([DP5]), np.array([3000.0]), lambda md: 9.0)
    pu, so, rot = prof[["HKLD_PU", "HKLD_SO", "HKLD_ROT"]].iloc[0]
    assert pu > rot > so


def test_limit_check_and_utilisation():
    casing = {"name": "CSG 7", "od": 7.0, "id": 6.276, "weight_ppf": 26, "length": None, "bha": True, "bend_limit_dls": 4.0}
    hole = bd.Hole(bd.prep_survey(survey(5.0)))
    run = one_run([casing])
    lim = bd.limit_check(hole, run, setting_md=3000.0)
    assert set(lim["status"]) == {"LEWAT BATAS"} and lim["utilisasi"].max() == pytest.approx(1.25, rel=1e-6)
    assert lim["md_dari"].min() >= 1000                # hanya interval build yang ditandai
    prof = bd.depth_profile(hole, run, np.array([2500.0]), lambda md: np.nan)
    assert prof["BEND_UTIL_MAX"].iloc[0] == pytest.approx(1.25, rel=1e-6)
    # tanpa batas → tidak dicek
    assert bd.limit_check(hole, one_run([DP5]), 3000.0).empty


def test_catalog_presets_resolve_and_override():
    cat = bd.load_catalog()
    cfg, items = bd.resolve_preset(cat, "BHA_8.5_STD", counts={"DC_7": 9})
    dc = next(c for c in items if c["item"] == "DC_7")
    assert dc["length"] == 9 * 31 and dc["od"] == 7.0
    assert items[-1]["length"] is None and items[-1]["bha"] is False
    assert cfg["hole_size"] == 8.5
    # item dipakai dua kali (liner): override per urutan
    _, li = bd.resolve_preset(cat, "LNR_7_ON_DP5", lengths={"#2": 1200})
    assert [c["length"] for c in li[:2]] == [85, 1200]
    for pid in cat["presets"]:                        # semua preset bawaan valid
        bd.comps_from_list(bd.resolve_preset(cat, pid)[1])
    with pytest.raises(ValueError):
        bd.resolve_preset(cat, "TIDAK_ADA")


def test_runs_selected_by_hole_depth_reached():
    cat = bd.load_catalog()
    runs = bd.runs_from_spec({"runs": [{"from_hole_md": 2000, "preset": "BHA_8.5_STD"},
                                       {"from_hole_md": 0, "preset": "BHA_12.25_STD"}]}, cat)
    assert [r.from_md for r in runs] == [0.0, 2000.0]
    idx = pd.date_range("2026-11-01", periods=6, freq="30s", tz="UTC")
    # trip keluar setelah section 8-1/2 dibor: hole depth tetap 2500 → run ke-2 walau bit naik ke 500 ft
    rig = pd.DataFrame({"hole_depth": [1950, 1990, 2010, 2040, 2040, 2040], "bit_depth": [1950, 1990, 2010, 2040, 1200, 500]},
                       index=idx)
    assert list(bd.assign_runs(rig, runs)) == [0, 0, 1, 1, 1, 1]


def test_legacy_string_format_and_validation():
    runs = bd.runs_from_spec({"name": "lama", "components": [DP5]})
    assert len(runs) == 1 and runs[0].from_md == 0
    with pytest.raises(ValueError):
        bd.comps_from_list([{"name": "x", "od": 5, "id": 6, "length": 10}, DP5])
    with pytest.raises(ValueError):
        bd.comps_from_list([{**DP5, "length": None}, DP5])   # hanya komponen terakhir boleh tanpa panjang


def test_compute_end_to_end_two_runs():
    cat = bd.load_catalog()
    runs = bd.runs_from_spec({"runs": [{"from_hole_md": 0, "preset": "BHA_12.25_STD", "shoe_md_ft": 300},
                                       {"from_hole_md": 1800, "preset": "BHA_8.5_STD", "shoe_md_ft": 1790}]}, cat)
    idx = pd.date_range("2026-11-01", periods=200, freq="30s", tz="UTC")
    bit = np.r_[np.linspace(100, 1700, 100), np.linspace(1800, 2600, 100)]
    rig = pd.DataFrame({"bit_depth": bit, "hole_depth": bit + 10, "hookload": 150.0, "rpm": 0.0}, index=idx)
    res = bd.compute(survey(3.0), rig, pd.DataFrame({"md": [0], "mw": [9.0]}), runs, step=100)
    assert set(res["time"]["run"]) == {runs[0].name, runs[1].name}
    assert res["time"]["BND_BHA_EST"].notna().any()
    assert len(res["runs"]) == 2 and res["runs"][1]["setting_md_ft"] >= 1800
