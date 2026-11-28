"""Bukti kuantitatif per deteksi: aktual vs harapan, selisih, konteks, pengulangan di kedalaman."""
import numpy as np

from app.anomaly import detectors as D
from app.anomaly import evidence as E
from tests.test_packoff_potential import _frame


def test_packoff_facts_actual_vs_expected():
    d = _frame(800.0)
    rng = np.random.default_rng(0)
    d["spp"] = d["spp"] + rng.normal(0, 15, len(d))      # derau supaya MAD konteks > 0
    po = [x for x in D.run(d)["detections"] if x["detector"] == "packoff"]
    assert po
    f = next(x for x in po[0]["facts"] if x["k"] == "spp")
    assert f["ref"] == "same_flow" and abs(f["exp"] - 2200) < 60 and f["d"] > 600 and f["dp"] > 25
    assert f["pct"] >= 99 and f["z"] > 10                  # jauh di atas 6 jam (data) sebelumnya
    assert "SPP" in po[0]["summary"] and "harapan pada flow sama" in po[0]["summary"]
    assert po[0]["po_alpha"] == D.DEFAULTS["po_transmission"]


def test_no_meaningless_percent_or_zero_facts():
    f = E._fact("wob", 3.3, "klb", 0.7, "baseline", 1)
    assert "dp" not in f and f["d"] == 2.6               # baseline < 2 klb: tanpa persentase
    assert E._fact("spp", 2400, "psi", 2000, "baseline", 0)["dp"] == 20


def test_repeats_same_depth():
    mk = lambda h, md: {"detector": "overpull", "start": f"2026-11-18T{h:02d}:00:00+00:00", "md": md}
    dets = [mk(1, 5300.0), mk(5, 5350.0), mk(9, 6000.0), mk(12, 5320.0)]
    r = E.repeats(dets, dets[-1])
    assert r == {"n_24h": 3, "n_depth": 2, "depth_ft": 100.0}
