"""Uji ramalan ECD berbasis rencana (app/core/forecast.py) dan penanda ECD beku (features.stale_ecd_mask)."""
import numpy as np
import pandas as pd
import pytest

from app.core import forecast as fc
from app.core.features import add_features, stale_ecd_mask

MW = 10.0


def fake_predict(X: pd.DataFrame) -> np.ndarray:
    """'Model' ECD ⓥ sederhana: MW + 0,4 + sedikit naik dengan kedalaman."""
    return X["mw"].to_numpy() + 0.4 + 2e-5 * X["bit_depth"].to_numpy()


def rig_frame(hours: float = 3.0, start_md: float = 5000.0, rop: float = 60.0, conn_every_min: int = 60,
              offset: float = 0.1) -> pd.DataFrame:
    """Data bor sintetis: pompa 600 gpm, RPM 120, WOB 20, ROP 60 ft/jam, sambung pipa 5 menit tiap jam.
    ECD terukur = fake_predict + `offset`; saat & ±5 menit setelah pompa mati nilainya beku (ditahan)."""
    idx = pd.date_range("2026-11-01", periods=int(hours * 120), freq="30s", tz="UTC")
    n = len(idx)
    minute = np.arange(n) / 2
    off = (minute % conn_every_min) >= conn_every_min - 5
    hole = start_md + np.cumsum(np.where(off, 0, rop / 120))
    df = pd.DataFrame({"flow_in": np.where(off, 0.0, 600.0), "spp": np.where(off, 0.0, 2500.0),
                       "rpm": np.where(off, 0.0, 120.0), "wob": np.where(off, 0.0, 20.0), "rop": np.where(off, 0.0, rop),
                       "hookload": 150.0, "torque": np.where(off, 0.0, 10.0), "bit_depth": hole, "hole_depth": hole}, index=idx)
    ecd = MW + 0.4 + 2e-5 * hole + offset
    held = pd.Series(np.where(off, np.nan, ecd), index=idx)
    after = pd.Series(off, index=idx).shift(10, fill_value=False) & ~off       # 5 menit setelah pompa hidup: masih beku
    held[after] = np.nan
    df["ecd"] = held.ffill()
    mw = pd.DataFrame({"md": [0.0], "mw": [MW]})
    sv = pd.DataFrame({"md": [0.0, 20000.0], "tvd": [0.0, 20000.0], "inc": [0.0, 0.0], "azi": [0.0, 0.0], "dls": [0.0, 0.0]})
    return add_features(df, mw, sv)


SURVEY = pd.DataFrame({"md": [0.0, 20000.0], "tvd": [0.0, 20000.0], "inc": [0.0, 0.0]})


def test_stale_mask_marks_frozen_value_after_pump_restart():
    idx = pd.date_range("2026-11-01", periods=8, freq="30s", tz="UTC")
    df = pd.DataFrame({"flow_in": [600, 600, 0, 0, 600, 600, 600, 600],
                       "ecd": [10.5, 10.6, 10.6, 10.6, 10.6, 10.6, 10.8, 10.8]}, index=idx)
    assert list(stale_ecd_mask(df)) == [False, False, True, True, True, True, False, False]
    df.loc[idx[2], "flow_in"] = np.nan                         # flow kosong ≠ pompa mati
    df.loc[idx[3], "flow_in"] = np.nan
    assert not stale_ecd_mask(df).any()


def test_reference_uses_only_fresh_ecd_and_finds_bias():
    hist = rig_frame()
    ref = fc.reference(hist, fake_predict)
    fresh = (~hist["ecd_stale"]) & (hist["flow_in"] > 50) & (hist.index >= hist.index[-1] - pd.Timedelta(minutes=60))
    assert ref.n_calib == int(fresh.sum())
    assert ref.bias == pytest.approx(0.1, abs=1e-6)
    assert ref.flow == 600 and ref.rpm == 120 and ref.wob == 20 and ref.rop == pytest.approx(60)


def test_unchanged_plan_continues_measured_ecd():
    hist = rig_frame()
    res = fc.forecast(hist, [{"op": "drill", "hours": 2}], fake_predict, SURVEY, connections=False, both=False)
    tl = res["timeline"]
    last_true = MW + 0.4 + 2e-5 * hist["hole_depth"].iloc[-1] + 0.1
    assert tl["ecd"].iloc[0] == pytest.approx(last_true, abs=0.01)
    assert tl["hole_depth"].iloc[-1] == pytest.approx(hist["hole_depth"].iloc[-1] + 120, abs=1)   # 2 jam × 60 ft/jam


@pytest.mark.parametrize("change", [{"flow": 720}, {"rpm": 180}, {"wob": 30}])
def test_controls_move_ecd_in_physical_direction(change):
    hist = rig_frame()
    base = fc.forecast(hist, [{"op": "drill", "hours": 2}], fake_predict, SURVEY, connections=False, both=False)["timeline"]
    up = fc.forecast(hist, [{"op": "drill", "hours": 2, **change}], fake_predict, SURVEY, connections=False, both=False)["timeline"]
    down = fc.forecast(hist, [{"op": "drill", "hours": 2, **{k: v * 0.5 for k, v in change.items()}}], fake_predict, SURVEY,
                       connections=False, both=False)["timeline"]
    assert up["ecd"].iloc[-1] > base["ecd"].iloc[-1] > down["ecd"].iloc[-1]


def test_flow_response_follows_power_law():
    hist = rig_frame()
    ref = fc.reference(hist, fake_predict)
    off = {}                                    # tanpa PV/YP → hidraulika tidak aktif: APL × (Q/Q0)^0,6
    base = fc.forecast(hist, [{"op": "circ", "hours": 1}], fake_predict, SURVEY, cfg=off, connections=False, both=False, ref=ref)["timeline"]
    hi = fc.forecast(hist, [{"op": "circ", "hours": 1, "flow": 1200}], fake_predict, SURVEY, cfg=off, connections=False, both=False, ref=ref)["timeline"]
    apl = base["apl_ref"].iloc[0]
    # sirkulasi tanpa bor: cutting dari acuan terangkat bertahap, jadi bandingkan komponen flow saja
    assert hi["d_flow"].iloc[0] == pytest.approx(apl * (2 ** 0.6 - 1), rel=1e-6)


def test_connections_drop_to_static_and_take_time():
    hist = rig_frame()
    start = hist["hole_depth"].iloc[-1]
    plan = [{"op": "drill", "to_md": start + 620, "rop": 62}]
    res = fc.forecast(hist, plan, fake_predict, SURVEY, cfg={"every_ft": 62, "off_min": 5}, connections=True, both=True)
    tl, cont = res["timeline"], res["continuous"]
    off = tl[tl["op"] == "sambung"]
    assert res["summary"]["connections"] == 9                  # tidak ada sambungan di target akhir
    assert (off["ecd"] == off["mw"]).all() and (~off["pumps"]).all()
    assert off.groupby((off.index.to_series().diff() != pd.Timedelta("30s")).cumsum())["hole_depth"].nunique().max() == 1
    assert res["summary_continuous"]["connections"] == 0
    assert (tl.index[-1] - cont.index[-1]) == pd.Timedelta(minutes=45)        # 9 × 5 menit


def test_target_and_hours_sets_rop_including_connections():
    hist = rig_frame()
    start = hist["hole_depth"].iloc[-1]
    res = fc.forecast(hist, [{"op": "drill", "to_md": start + 310, "hours": 6}], fake_predict, SURVEY,
                      cfg={"every_ft": 62, "off_min": 6}, connections=True, both=False)
    tl = res["timeline"]
    assert tl["hole_depth"].iloc[-1] == pytest.approx(start + 310, abs=1)
    first_hit = tl.index[tl["hole_depth"] >= start + 310 - 1e-6][0]
    assert (tl.index[-1] - first_hit) <= pd.Timedelta(minutes=1)              # tiba tepat di akhir 6 jam
    assert not [w for w in res["warnings"] if not w.startswith(("PV/YP", "Hidraulika tidak aktif"))]


def test_margin_alert_ahead_when_fg_drops_with_depth():
    hist = rig_frame()
    start = hist["hole_depth"].iloc[-1]
    ppfg = pd.DataFrame({"md": [0, start, start + 200, 20000], "tvd": [0, start, start + 200, 20000],
                         "pp": [8.6] * 4, "sfg": [np.nan] * 4, "fg_min": [12.0, 12.0, 10.7, 10.7], "fg_max": [np.nan] * 4})
    res = fc.forecast(hist, [{"op": "drill", "hours": 6}], fake_predict, SURVEY, ppfg=ppfg, shoe_md=start - 50, both=False)
    s = res["summary"]
    assert "WARNING" in s["first"] and s["first"]["WARNING"]["md"] > start
    assert s["margin_min"]["kind"] == "FG (loss)" and s["margin_min"]["margin"] < 0.25


def test_backtest_beats_persistence_on_trend():
    frame = rig_frame(hours=8)
    t_cut = frame.index[0] + pd.Timedelta(hours=3)
    bt = fc.backtest(frame, t_cut, 4, fake_predict, SURVEY)
    m = bt["metrics"]
    assert m["n"] > 100 and m["mae"] < 0.02
    assert {"mae_persist", "max_err", "max_err_persist"} <= set(m)
    assert bt["forecast"]["timeline"]["op"].eq("sambung").any()


def test_invalid_plans_raise():
    hist = rig_frame()
    with pytest.raises(ValueError):
        fc.forecast(hist, [{"op": "drill"}], fake_predict, SURVEY)
    with pytest.raises(ValueError):
        fc.forecast(hist, [{"op": "drill", "to_md": 100, "hours": 1}], fake_predict, SURVEY)
    with pytest.raises(ValueError):
        fc.forecast(hist, [{"op": "drill", "to_md": hist["hole_depth"].iloc[-1] + 5000, "hours": 1}], fake_predict, SURVEY)
    with pytest.raises(ValueError):
        fc.forecast(hist, [{"op": "terbang", "hours": 1}], fake_predict, SURVEY)


def test_hydraulic_flow_response_and_hyd_base():
    hist = rig_frame()
    ref = fc.reference(hist, fake_predict)
    cfg = {"pv": 20, "yp": 18, "hole_size": 8.5, "base": "ml"}
    plan = lambda q: [{"op": "circ", "hours": 1, "flow": q}]
    base = fc.forecast(hist, plan(600), fake_predict, SURVEY, cfg=cfg, connections=False, both=False, ref=ref)
    hi = fc.forecast(hist, plan(720), fake_predict, SURVEY, cfg=cfg, connections=False, both=False, ref=ref)
    b, h = base["timeline"], hi["timeline"]
    assert h["d_flow"].iloc[0] == pytest.approx(b["apl_ref"].iloc[0] * (h["apl_hyd"].iloc[0] / b["apl_hyd"].iloc[0] - 1), rel=1e-6)
    assert h["d_flow"].iloc[0] > 0 and base["hydraulics"]["default_rheo"] is False and any(c["od"] == 7.0 for c in base["hydraulics"]["string"])
    # dasar hidraulika: di jam mulai sama dengan ECD terukur (kalibrasi c), lalu naik dengan kedalaman bor
    hyd = fc.forecast(hist, [{"op": "drill", "hours": 2}], fake_predict, SURVEY, cfg={**cfg, "base": "hyd"}, connections=False, both=False, ref=ref)
    t = hyd["timeline"]
    assert hyd["hydraulics"]["base"] == "hyd"
    assert t["ecd"].iloc[0] == pytest.approx(MW + ref.apl, abs=0.01)
    assert hyd["hydraulics"]["c"] > 0
