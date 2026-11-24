import numpy as np
import pandas as pd

from app.core.features import hole_reached_robust


def _s(vals, step_s=30, start="2026-10-28 10:00"):
    idx = pd.date_range(start, periods=len(vals), freq=f"{step_s}s", tz="UTC")
    return pd.Series(vals, index=idx, dtype=float)


def test_spike_tunggal_diabaikan():
    # pola GW339 29 Okt: 635 → 3634 → 959 → 684 → 635
    r = hole_reached_robust(_s([635, 635, 3634, 959, 684, 635, 635]))
    assert r.max() < 700


def test_spike_sesudah_data_kosong_lama_diabaikan():
    a = _s([635, 635], start="2026-10-28 10:00")
    b = _s([3634, 959, 684, 635], start="2026-10-29 09:29")
    assert hole_reached_robust(pd.concat([a, b])).max() < 700


def test_pengeboran_normal_tanpa_lag():
    v = np.arange(1000, 1100, 2.0)  # 2 ft / 30 dtk
    r = hole_reached_robust(_s(v))
    assert np.allclose(r.to_numpy(), v)


def test_lompatan_nyata_diterima_setelah_konfirmasi():
    v = [1000] * 5 + [2500] * 12  # data lanjut di kedalaman baru dan bertahan
    r = hole_reached_robust(_s(v))
    assert r.iloc[-1] == 2500 and r.iloc[6] == 1000


def test_sustained_stable_drop_resets_reached_depth():
    """Koreksi depth / sidetrack (GW339 16 Nov: 9.909 → 5.357 ft) di-reset; trip (hole ikut bit) dan angka 0 tidak."""
    idx = pd.date_range("2026-11-16", periods=6 * 60, freq="1min", tz="UTC")
    v = np.r_[np.full(60, 9909.0), np.full(300, 5357.0)]
    r = hole_reached_robust(pd.Series(v, index=idx))
    assert r.iloc[60 + 119] == 9909 and r.iloc[-1] == 5357                # ≥ 2 jam stabil di bawah → reset
    trip = np.r_[np.full(60, 4828.0), np.linspace(1600, 4400, 200), np.full(100, 4828.0)]   # hole ikut bit saat trip
    assert hole_reached_robust(pd.Series(trip, index=idx)).min() == 4828
    zero = np.r_[np.full(60, 3357.0), np.zeros(300)]
    assert hole_reached_robust(pd.Series(zero, index=idx)).min() == 3357
