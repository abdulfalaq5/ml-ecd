"""MW berbasis waktu (DDR) digabung dengan MW per kedalaman (Rec 04)."""
import numpy as np
import pandas as pd

from app.core.data import apply_mw_changes


def _idx(n, start="2026-08-06 12:00"):
    return pd.date_range(pd.Timestamp(start, tz="Asia/Jakarta").tz_convert("UTC"), periods=n, freq="1h")


def test_no_changes_identical():
    s = pd.Series([10.2, 10.2, 8.7], index=_idx(3))
    pd.testing.assert_series_equal(apply_mw_changes(s, None), s)
    pd.testing.assert_series_equal(apply_mw_changes(s, pd.DataFrame(columns=["ts", "mw"])), s)


def test_displacement_at_shoe_then_depth_table_takes_over():
    # BEKA-254: Rec 04 10,2 sampai bit menembus 3724 ft (jam ke-5), RDIF 8,7 sudah di lubang sejak jam ke-2,
    # lalu MW per kedalaman naik ke 8,8 (jam ke-7) -> 8,8 menang
    s = pd.Series([10.2, 10.2, 10.2, 10.2, 10.2, 8.7, 8.7, 8.8, 8.8], index=_idx(9))
    ch = pd.DataFrame({"ts": [s.index[2]], "mw": [8.7]})
    out = apply_mw_changes(s, ch)
    assert out.tolist() == [10.2, 10.2, 8.7, 8.7, 8.7, 8.7, 8.7, 8.8, 8.8]


def test_successive_time_changes_with_constant_depth_mw():
    # GW339: Rec 04 tetap 10,3 (lumpur 8-1/2"); lumpur baru 9,0 -> 9,5 -> 10,0 berbasis waktu
    s = pd.Series(np.full(8, 10.3), index=_idx(8, "2026-11-16 10:00"))
    T = lambda h: pd.Timestamp(h, tz="Asia/Jakarta")
    ch = pd.DataFrame({"ts": [T("2026-11-16 12:00"), T("2026-11-16 14:30"), T("2026-11-16 16:00")],
                       "mw": [9.0, 9.5, 10.0]})
    out = apply_mw_changes(s, ch)
    assert out.tolist() == [10.3, 10.3, 9.0, 9.0, 9.0, 9.5, 10.0, 10.0]


def test_nan_depth_mw_filled_by_change():
    s = pd.Series([np.nan, np.nan, np.nan], index=_idx(3))
    out = apply_mw_changes(s, pd.DataFrame({"ts": [s.index[1]], "mw": [9.0]}))
    assert np.isnan(out.iloc[0]) and out.iloc[1:].tolist() == [9.0, 9.0]


def test_reset_hole_depth_does_not_cancel_ddr_change():
    # GW339: hole tercapai 5.651 -> reset ke 5.357 (shoe); bit melintasi ulang Rec 04 10,2 -> 10,3 (lubang lama)
    idx = _idx(6, "2026-11-16 10:00")
    s = pd.Series([10.3, 10.3, 10.2, 10.3, 10.3, 10.3], index=idx)
    hole = pd.Series([5651, 5651, 5357, 5360, 5400, 5660], index=idx, dtype=float)
    ch = pd.DataFrame({"ts": [idx[1]], "mw": [9.0]})
    assert apply_mw_changes(s, ch, hole).tolist() == [10.3, 9.0, 9.0, 9.0, 9.0, 9.0]
    # tanpa hole_reached perilaku lama (perubahan nilai apa pun menang)
    assert apply_mw_changes(s, ch).tolist() == [10.3, 9.0, 10.2, 10.3, 10.3, 10.3]
