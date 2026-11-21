"""Uji logika ML & alert dengan data sintetis (tanpa database)."""
import numpy as np
import pandas as pd
import pytest

from app.core.alerts import DEFAULT_THRESHOLDS, classify
from app.core.features import FEATURES
from app.ml.pipeline import MWOnly, TreeModel, labeled, metrics, persistence


def synth(n=3000, mw=(9.0, 9.6), seed=0, well="W"):
    """ECD = MW + APL(flow, tvd) + noise: pola fisik sederhana yang harus bisa dipelajari lintas sumur."""
    r = np.random.default_rng(seed)
    idx = pd.date_range("2026-11-01", periods=n, freq="30s", tz="UTC")
    d = pd.DataFrame(index=idx)
    d["mw"] = r.uniform(*mw, n)
    d["flow_in"] = r.uniform(300, 900, n)
    d["tvd_bit"] = r.uniform(1000, 6000, n)
    d["bit_depth"] = d["tvd_bit"] * 1.05
    d["hole_depth"] = d["bit_depth"] + r.uniform(0, 30, n)
    d["spp"] = 0.002 * d["flow_in"] ** 2 + 0.05 * d["tvd_bit"]
    for c in ("rpm", "wob", "rop", "hookload", "torque", "off_bottom", "block_vel", "t_pumps_on", "inc_bit"):
        d[c] = r.uniform(0, 1, n)
    d["ecd"] = d["mw"] + 0.0006 * d["flow_in"] + 0.00002 * d["tvd_bit"] + r.normal(0, 0.02, n)
    d["state"] = "DRILL_ROT"
    d["well"] = well
    return d


def test_features_are_surface_only():
    """ECD/ANP/PWD tidak boleh menjadi fitur (konfigurasi surface-only, proposal Bab 5.5)."""
    assert not {"ecd", "anp", "ecd_pred", "pwd"} & set(FEATURES)


@pytest.mark.parametrize("algo", ["rf", "xgb", "lgbm"])
def test_tree_extrapolates_to_unseen_mw(algo):
    """Target ΔECD: sumur dengan MW di luar rentang training tetap terprediksi (pohon tidak bisa ekstrapolasi
    ECD absolut). Dengan target ECD langsung, error ≈ selisih MW (~1 ppg)."""
    tr, te = synth(mw=(9.0, 9.6)), synth(mw=(10.4, 10.8), seed=1)
    m = TreeModel(algo).fit(tr[FEATURES], tr["ecd"])
    mae = np.abs(m.predict(te[FEATURES]) - te["ecd"]).mean()
    assert mae < 0.1, mae


def test_missing_mw_gives_no_prediction():
    tr = synth()
    te = synth(n=50, seed=2)
    te.loc[te.index[:10], "mw"] = np.nan
    for m in (TreeModel("lgbm").fit(tr[FEATURES], tr["ecd"]), MWOnly().fit(tr[FEATURES], tr["ecd"])):
        p = m.predict(te[FEATURES])
        assert np.isnan(p[:10]).all() and np.isfinite(p[10:]).all()


def test_labeled_filters():
    d = synth(n=100)
    d.loc[d.index[0], "state"] = "STATIC"          # pompa mati
    d.loc[d.index[1], "mw"] = np.nan               # tanpa MW
    d.loc[d.index[2], "ecd"] = 25.0                # ECD tidak fisik
    d.loc[d.index[3], "bit_depth"] = 105888.0      # glitch bit depth
    d.loc[d.index[4], "flow_in"] = np.nan
    lab = labeled(d)
    assert len(lab) == 95 and not set(d.index[:5]) & set(lab.index)
    assert len(labeled(d, need_mw=False)) == 96


def test_persistence_ignores_gaps():
    d = synth(n=10)
    d.index = d.index[:5].append(d.index[5:] + pd.Timedelta(hours=2))  # gap 2 jam
    m = persistence(d, 30)
    assert m["n"] == 8  # 9 pasangan - 1 pasangan melintasi gap


def test_metrics_basic():
    m = metrics(np.array([10.0, 10.2]), np.array([10.1, 10.2]))
    assert m["n"] == 2 and abs(m["mae"] - 0.05) < 1e-9 and m["within_tol"] == 1.0


def _frame(n=20):
    idx = pd.date_range("2026-11-01", periods=n, freq="30s", tz="UTC")
    return pd.DataFrame({"ecd": np.nan, "ecd_pred": np.nan, "mw": 9.5, "state": "DRILL_ROT",
                         "margin_up_bit": np.nan, "margin_up_oh": np.nan, "fg_bit": np.nan, "fg_oh": np.nan,
                         "lower_bit": np.nan}, index=idx)


def test_unavailable_when_pumping_without_ecd_reference():
    d = _frame()
    d.loc[d.index[:5], "state"] = "STATIC"
    out = classify(d, DEFAULT_THRESHOLDS)
    assert (out["level"].iloc[5:] == "UNAVAILABLE").all()
    assert (out["level"].iloc[:5] == "NORMAL").all()  # pompa mati: ECD tidak relevan


def test_detection_overrides_unavailable():
    d = _frame()
    det = [{"start": d.index[3].isoformat(), "end": d.index[6].isoformat(), "level": "ADVISORY", "label": "uji"}]
    out = classify(d, DEFAULT_THRESHOLDS, det)
    assert out["level"].iloc[4] == "ADVISORY"


def test_margin_levels():
    d = _frame()
    d["ecd_pred"] = 10.0
    d["margin_up_bit"] = 0.0
    d["fg_bit"] = np.r_[np.full(10, 10.6), np.full(10, 9.9)]   # margin 0.6 -> NORMAL, -0.1 -> CRITICAL
    d["fg_oh"] = d["fg_bit"]
    d["lower_bit"] = 8.0
    out = classify(d, DEFAULT_THRESHOLDS)
    assert out["level"].iloc[2] == "NORMAL" and out["level"].iloc[-1] == "CRITICAL"


def _rig(n=400, fo=2.0):
    idx = pd.date_range("2026-11-01", periods=n, freq="30s", tz="UTC")
    d = pd.DataFrame({"state": "DRILL_ROT", "flow_in": 600.0, "spp": 1500.0, "torque": 5.0, "rpm": 60.0,
                      "hookload": 150.0, "wob": 10.0, "block_vel": 0.0, "off_bottom": 0.0, "bit_depth": 5000.0,
                      "flow_out_pct": fo, "active_pit": 500.0}, index=idx)
    return d


def test_loss_ignores_noisy_low_flowout():
    from app.anomaly import detectors
    d = _rig(fo=2.0)
    d.loc[d.index[300:], "flow_out_pct"] = 1.0  # 2 % -> 1 %: noise paddle, bukan loss
    assert not [x for x in detectors.run(d)["detections"] if x["detector"] == "loss"]


def test_loss_single_vs_corroborated():
    from app.anomaly import detectors
    d = _rig(fo=40.0)
    d.loc[d.index[300:], "flow_out_pct"] = 25.0
    one = [x for x in detectors.run(d)["detections"] if x["detector"] == "loss"]
    assert one and max(x["level"] for x in one) == "ADVISORY"
    d.loc[d.index[300:], "active_pit"] = np.linspace(500, 460, 100)  # 8 bbl / 10 mnt
    two = [x for x in detectors.run(d)["detections"] if x["detector"] == "loss"]
    assert any(x["level"] == "WARNING" for x in two)


def test_detectors_survive_coarse_buckets():
    """Bucket kasar (mis. 7 menit) tidak boleh membuat rolling crash (bug tampilan 7 hari)."""
    from app.anomaly import detectors
    d = _rig(n=60)
    d.index = pd.date_range("2026-11-01", periods=60, freq="420s", tz="UTC")
    d["ecd_pred"] = 10.0
    d["ecd"] = np.nan
    d["t_pumps_on"] = 60.0
    d["mw"] = 9.5
    detectors.run(d)
