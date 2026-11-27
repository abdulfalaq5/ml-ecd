"""Uji trip performance (app/core/trips.py) dengan trip sintetis: in-slip & out-of-slip yang diketahui."""
import numpy as np
import pandas as pd
import pytest

from app.core import trips as tp

BLOCK, STRING = 20.0, 120.0


def synth_trip(direction="TIH", n_stands=20, in_s=180, out_s=90, step=2, start_md=3000.0, hole=8000.0, stand_ft=93.0,
               stop_after=None, stop_s=1800):
    """Trip sintetis: tiap stand = in-slip `in_s` detik (bit diam, hookload = block) lalu out-of-slip `out_s` detik
    (bit bergerak satu stand, hookload = berat string)."""
    t, hk, bit = [], [], []
    now, md = 0.0, start_md
    sgn = 1 if direction == "TIH" else -1
    for k in range(n_stands):
        dur_in = stop_s if stop_after is not None and k == stop_after else in_s
        for _ in range(int(dur_in / step)):
            t.append(now); hk.append(BLOCK + np.random.default_rng(len(t)).normal(0, 1)); bit.append(md); now += step
        m = int(out_s / step)
        for j in range(m):
            t.append(now); hk.append(STRING); bit.append(md + sgn * stand_ft * (j + 1) / m); now += step
        md += sgn * stand_ft
    idx = pd.Timestamp("2026-11-01", tz="UTC") + pd.to_timedelta(t, unit="s")
    return pd.DataFrame({"hookload": hk, "bit_depth": bit, "hole_depth": hole, "flow_in": 0.0}, index=idx)


@pytest.mark.parametrize("direction", ["TIH", "TOH"])
def test_medians_match_known_slip_times(direction):
    r = tp.analyze(synth_trip(direction))
    s = r["summary"][direction]
    assert s["in_med"] == pytest.approx(3.0, abs=0.1) and s["out_med"] == pytest.approx(1.5, abs=0.1)
    assert s["trips"] == 1 and r["trips"][0]["dir"] == direction
    assert r["block_klb"] == pytest.approx(BLOCK, abs=3)
    # stand pertama tidak punya in-slip sebelumnya? ada (trip diawali in-slip), jadi semua stand terhitung
    assert s["n_out"] == 20 and s["n_in"] == 20


def test_long_stop_not_in_median_and_counted():
    r = tp.analyze(synth_trip(stop_after=10, stop_s=1800))
    s, trp = r["summary"]["TIH"], r["trips"][0]
    assert s["in_med"] == pytest.approx(3.0, abs=0.1) and s["n_in"] == 19
    assert trp["stops"] == 1 and trp["stands"] == 20


def test_trip_rates_and_depth():
    r = tp.analyze(synth_trip(n_stands=20))
    trp = r["trips"][0]
    assert trp["md_from"] == 3000 and trp["md_to"] == pytest.approx(3000 + 20 * 93, abs=1)
    assert trp["stands_per_h"] == pytest.approx(20 / (20 * 270 / 3600), rel=0.05)    # siklus 270 dtk
    assert trp["ft_per_h_moving"] == pytest.approx(93 / (90 / 3600), rel=0.05)


def test_near_bottom_and_coarse_data_excluded():
    r = tp.analyze(synth_trip(hole=3050.0))          # bit < 100 ft dari dasar sepanjang trip → bukan trip
    assert not r["summary"]
    coarse = synth_trip().iloc[::40]                  # ±80 detik/sampel (seperti rig LAS PDSI 53.2)
    r = tp.analyze(coarse)
    assert not r["summary"] and "terlalu kasar" in r["warnings"][0]


def test_cycle_jph_and_targets():
    r = tp.analyze(synth_trip(n_stands=20, stand_ft=62.0), shoe_md=3600.0,
                   targets={"gross_ft_h": 525, "stand": {"cased": {"jph": 15, "in_min": 2.5, "move_min": 1.0}}})
    st = pd.DataFrame(r["stands"])
    # siklus out-of-slip → out-of-slip = in 180 + out 90 dtk → 13,3 stand/jam; stand terakhir tanpa siklus
    assert st["cycle_min"].dropna().median() == pytest.approx(4.5, abs=0.1) and st["cycle_min"].isna().sum() == 1
    k = r["kpi"]["TIH"]
    assert set(k) == {"all", "cased", "open"}
    c = k["cased"]
    assert c["jph_med"] == pytest.approx(13.3, abs=0.3) and c["target"]["jph"] == 15 and c["target"]["manual"]["jph"]
    assert c["vs"]["jph"] < 0 and c["vs"]["in_min"] == pytest.approx(20, abs=3)
    assert c["gross_ft_h"] == pytest.approx(62 / (270 / 3600), rel=0.05)
    # open hole tanpa target manual → dibandingkan dengan P75/P25 data sendiri
    o = k["open"]
    assert not o["target"]["manual"]["jph"] and o["target"]["jph"] == o["jph_p75_data"]
    assert set(st["crew"]) <= {"AM", "PM"}


def test_slow_moving_flags_drag_and_joint_mode():
    r = tp.analyze(synth_trip(n_stands=12, out_s=300, stand_ft=40.0), unit="joint",
                   targets={"gross_ft_h": 525, "joint": {"open": {"move_min": 1.0, "in_min": 3.0}}}, shoe_md=1000.0)
    k = r["kpi"]["TIH"]["open"]
    assert k["n"] == 12 and any("drag" in n for n in k["notes"]) and any("kondisi lubang" in n for n in k["notes"])
    assert not tp.analyze(synth_trip(n_stands=12, stand_ft=40.0))["summary"]   # mode stand: 40 ft bukan stand


def test_deviation_fills_missing_dls(monkeypatch):
    from types import SimpleNamespace
    from app.routers import trips as rt
    sv = pd.DataFrame({"md": [0, 1000, 2000], "tvd": [0, 1000, None], "inc": [0, 0, 30], "azi": [0, 0, 0], "dls": [None, None, None]})
    monkeypatch.setattr(rt, "_well", lambda db, wid: SimpleNamespace(id=1, name="X", shoe_md=1500.0, sections=[]))
    monkeypatch.setattr(rt, "load_survey", lambda db, wid: sv)
    r = rt.deviation(1, db=None, _=None)
    assert r["dls_computed"] and r["survey"][-1]["dls"] == pytest.approx(3.0, abs=1e-6)
    assert r["survey"][-1]["tvd"] == pytest.approx(1000 + 1000 / (np.pi / 6) * 0.5, abs=0.1)
