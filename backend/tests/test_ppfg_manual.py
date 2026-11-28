"""Input PPFG manual per interval MD."""
import numpy as np
import pandas as pd
import pytest

from app.core.data import interp
from app.core.ppfg_input import clean_intervals, intervals_to_points


def test_intervals_step_and_constant():
    iv = clean_intervals([{"md_top": 3000, "md_bottom": 5000, "pp": 8.6, "sfg": 9.2, "fg_min": 13.0, "fg_max": 14.0},
                          {"md_top": 0, "md_bottom": 3000, "pp": 8.4, "fg_min": 12.5, "formation": "Sihapas"},
                          {"md_top": "", "md_bottom": ""}])
    assert [r["md_top"] for r in iv] == [0, 3000]          # diurutkan, baris kosong dibuang
    p = pd.DataFrame(intervals_to_points(iv))
    fg = interp(np.array([1500.0, 2999.0, 3000.0, 4000.0]), p["md"], p["fg_min"])
    assert fg.tolist() == pytest.approx([12.5, 12.5, 13.0, 13.0], abs=0.01)   # bertingkat di 3000 ft


def test_tvd_from_survey():
    sv = pd.DataFrame({"md": [0.0, 4000.0], "tvd": [0.0, 3000.0]})
    pts = intervals_to_points(clean_intervals([{"md_top": 2000, "md_bottom": 5000, "fg_min": 13}]), sv)
    assert pts[0]["tvd"] == 1500.0 and "tvd" not in pts[1]   # di luar rentang survey -> kosong


@pytest.mark.parametrize("row,msg", [
    ({"md_top": 100, "md_bottom": 50, "fg_min": 13}, "lebih dalam"),
    ({"md_top": 0, "md_bottom": 50, "fg_min": 30}, "di luar rentang"),
    ({"md_top": 0, "md_bottom": 50, "fg_min": 14, "fg_max": 13}, "lebih besar dari FG max"),
    ({"md_top": 0, "md_bottom": 50, "pp": 9, "fg_min": 8.5}, "tidak lebih besar dari PP"),
    ({"md_top": 0, "md_bottom": 50}, "minimal satu nilai"),
])
def test_validation(row, msg):
    with pytest.raises(ValueError, match=msg):
        clean_intervals([row])


def test_overlap():
    with pytest.raises(ValueError, match="tumpang tindih"):
        clean_intervals([{"md_top": 0, "md_bottom": 3000, "fg_min": 13}, {"md_top": 2500, "md_bottom": 4000, "fg_min": 13}])
