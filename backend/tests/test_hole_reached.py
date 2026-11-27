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


def _ser(vals, step_s=60):
    idx = pd.date_range("2026-09-30", periods=len(vals), freq=f"{step_s}s", tz="UTC")
    return pd.Series(np.asarray(vals, dtype=float), index=idx)


def test_new_hole_needs_bit_on_bottom_and_pumps():
    """BLSO-717: hole 1.026 → 3.633 saat bit di 754 ft; BEKA-255: hole & bit naik dengan pompa mati → ditolak."""
    n = 30
    hole = _ser([1026] * 5 + [3633] * (n - 5))
    bit = _ser([760] * n)
    flow = _ser([300] * n)
    r = hole_reached_robust(hole, bit=bit, flow=flow)
    assert r.max() == 1026                                   # tanpa aturan bit: terkonfirmasi sesudah 10 sampel
    assert hole_reached_robust(hole).max() == 3633
    up = _ser(np.linspace(3061, 3300, n))                    # "pengeboran" 240 ft/30 mnt dengan pompa mati
    r = hole_reached_robust(up, bit=up, flow=_ser([0] * n))
    assert r.max() == 3061
    r = hole_reached_robust(up, bit=up, flow=_ser([550] * n))   # pompa hidup, bit di dasar → lubang baru sah
    assert r.iloc[-1] == 3300


def test_return_to_previous_depth_after_false_reset_not_blocked_by_bit():
    """BDSI 21 7 Nov: setelah reset palsu, hole kembali ke kedalaman lama saat bit masih dangkal → tetap diterima."""
    hole = _ser([3328] * 10 + [779] * 150 + [3328] * 20)           # 2,5 jam rendah & stabil → reset ke 779
    bit = _ser([3300] * 10 + [36] * 170)
    flow = _ser([0] * 180)
    r = hole_reached_robust(hole, bit=bit, flow=flow)
    assert r.iloc[159] == 779 and r.iloc[-1] == 3328


def test_depth_shift_without_data_gap_not_confirmed():
    """GW339 15 Nov: hole & bit 'shifting' 5.652 → 9.909 ft dengan pompa hidup, tanpa jeda data → tetap 5.652.
    Data yang lanjut sesudah jeda panjang di kedalaman lebih dalam tetap diterima lewat konfirmasi."""
    hole = _ser([5652] * 10 + [9909] * 40)
    flow = _ser([300] * 50)
    r = hole_reached_robust(hole, bit=hole, flow=flow)
    assert r.max() == 5652
    idx = hole.index[:10].append(hole.index[10:] + pd.Timedelta(hours=12))   # jeda 12 jam lalu data lanjut
    gap = pd.Series(hole.to_numpy(), index=idx)
    r2 = hole_reached_robust(gap, bit=gap, flow=pd.Series(300.0, index=idx))
    assert r2.iloc[-1] == 9909
