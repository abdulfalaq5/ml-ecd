"""Kalibrasi ECD ⓥ ke PWD terakhir + smoothing (tanpa database)."""
import numpy as np
import pandas as pd

from app.ml.pipeline import CAL_TAU_H, _smooth_pumps_on, calibration_offset


def frame(n=600, ecd_until=None, bias=0.3, hole=8.5):
    idx = pd.date_range("2026-11-20", periods=n, freq="30s", tz="UTC")
    d = pd.DataFrame(index=idx)
    d["state"] = "DRILL_ROT"
    d["flow_in"], d["spp"], d["mw"] = 450.0, 2000.0, 10.0
    d["bit_depth"] = d["hole_depth"] = 5000.0
    d["hole_size"] = hole
    model = pd.Series(10.5, index=idx)
    d["ecd"] = model + bias
    if ecd_until is not None:
        d.loc[d.index[ecd_until]:, "ecd"] = np.nan
    return d, model


def test_offset_tracks_measured_bias_and_decays_after_pwd_lost():
    d, model = frame(n=2000, ecd_until=200, bias=0.3)
    off, age = calibration_offset(d, model)
    assert abs(off.iloc[199] - 0.3) < 1e-6 and age.iloc[199] == 0
    i6 = 199 + int(CAL_TAU_H * 120)                       # 6 jam sesudah label terakhir (30 dtk/sampel)
    if i6 < len(d):
        assert abs(off.iloc[i6] - 0.3 * np.exp(-1)) < 0.01
    assert (off.diff().iloc[201:] <= 1e-12).all()          # hanya meluruh, tidak tumbuh tanpa PWD


def test_offset_is_causal():
    d, model = frame(n=400, bias=0.0)
    d.loc[d.index[300]:, "ecd"] = 11.5                     # PWD naik 1 ppg mulai sampel 300
    off, _ = calibration_offset(d, model)
    assert (off.iloc[:300].abs() < 1e-9).all()             # tidak ada look-ahead


def test_no_offset_across_hole_size_change():
    d, model = frame(n=400, ecd_until=200, bias=0.4)
    d.loc[d.index[250]:, "hole_size"] = 6.125              # section baru: bias section lama tidak berlaku
    off, _ = calibration_offset(d, model)
    assert off.iloc[240] > 0.3 and (off.iloc[250:] == 0).all()


def test_no_measured_ecd_no_offset():
    d, model = frame(n=100)
    d["ecd"] = np.nan
    off, age = calibration_offset(d, model)
    assert (off == 0).all() and age.isna().all()


def test_smoothing_causal_and_does_not_cross_pumps_off():
    idx = pd.date_range("2026-11-20", periods=12, freq="30s", tz="UTC")
    s = pd.Series([10, 10, 12, 10, 10, np.nan, np.nan, 11, 11, 11, 11, 11], index=idx, dtype=float)
    pumps = pd.Series([True] * 5 + [False] * 2 + [True] * 5, index=idx)
    out = _smooth_pumps_on(s, pumps)
    assert out.iloc[2] == 10                               # spike 1 sampel diredam (median 10,10,12)
    assert out.iloc[7] == 11                               # segmen baru tidak membawa nilai segmen lama
