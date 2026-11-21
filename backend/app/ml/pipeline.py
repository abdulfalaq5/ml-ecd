"""Dataset, training & inferensi nowcast ECD (docs Bab 5.5–5.7, 7).

- Label: ECD terukur Rec 02 (7–20 ppg), pompa hidup. Tanpa label -> hanya inferensi (ECD ⓥ).
- Validasi grouped per sumur: leave-one-well-out (diagnostik) + sumur blind tetap (laporan).
- Eksperimen: A baseline (MW-only, persistence), B RF, C XGBoost, D LightGBM. E LSTM & F hybrid: belum (butuh
  data time-series stabil & baseline hidraulik A14).
"""
from __future__ import annotations

import logging
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..models import MLModel, Well
from ..core.data import load_mw, load_survey, load_time
from ..core.features import CLEANOUT_STATES, FEATURES, PUMPS_ON_STATES, add_features

log = logging.getLogger("ml")
ALGOS = ["mw_only", "rf", "xgb", "lgbm"]
ALGO_LABEL = {"mw_only": "A · Baseline MW-only", "persistence": "A · Persistence", "rf": "B · Random Forest",
              "xgb": "C · XGBoost", "lgbm": "D · LightGBM"}


# ------------------------------------------------------------------ dataset

def well_frame(db: Session, well: Well, bucket_s: int | None = None) -> pd.DataFrame:
    s = get_settings()
    df = load_time(db, well.id, bucket_s=bucket_s or s.resample_s)
    if df.empty:
        return df
    df = add_features(df, load_mw(db, well.id), load_survey(db, well.id))
    df["well"] = well.name
    return df


def labeled(df: pd.DataFrame, need_mw: bool = True) -> pd.DataFrame:
    """Baris berlabel: ECD terukur valid, pompa hidup, flow & SPP ada. MW wajib (ECD = MW + APL):
    MW yang diimputasi median akan mengajari model hal yang salah."""
    if df.empty or "ecd" not in df:
        return df.iloc[0:0]
    m = df["ecd"].between(7, 20) & df["state"].isin(PUMPS_ON_STATES) & df["flow_in"].notna() & df["spp"].notna()
    if need_mw:
        m &= df["mw"].between(7, 20)
    # buang glitch fisik (mis. bit depth 105.888 ft di BDSI 21): bit tidak mungkin jauh di bawah hole depth
    bit, hole = df["bit_depth"], df.get("hole_depth", df["bit_depth"])
    m &= bit.between(0, 40000) & ~(bit > hole + 100)
    return df[m]


def persistence(frame: pd.DataFrame, step_s: int) -> dict:
    """Baseline A persistence: ECD(t) = ECD terukur sebelumnya (hanya bila tepat 1 bucket sebelumnya)."""
    parts = []
    for _, d in frame.groupby("well"):
        prev = d["ecd"].shift(1)
        gap = d.index.to_series().diff().dt.total_seconds()
        ok = prev.notna() & (gap <= step_s * 1.01)
        parts.append(pd.DataFrame({"y": d["ecd"][ok], "p": prev[ok]}))
    if not parts:
        return {"n": 0}
    a = pd.concat(parts)
    return metrics(a["y"].to_numpy(), a["p"].to_numpy())


def _make(algo: str):
    """Hyperparameter sengaja diregularisasi: dengan sedikit sumur, model yang terlalu fleksibel menghafal
    karakter per sumur (uji LOWO 21 Nov 2026: RF default MAE 0,36 vs teregularisasi 0,24 ppg)."""
    if algo == "rf":
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(n_estimators=150, min_samples_leaf=50, max_features=0.5, n_jobs=-1, random_state=42)
    if algo == "xgb":
        from xgboost import XGBRegressor
        return XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.6,
                            min_child_weight=50, reg_lambda=5, n_jobs=-1, random_state=42)
    if algo == "lgbm":
        from lightgbm import LGBMRegressor
        return LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=500, subsample=0.8,
                             subsample_freq=1, colsample_bytree=0.6, reg_lambda=5, random_state=42, verbose=-1)
    raise ValueError(algo)


class MWOnly:
    """Baseline A: ECD = a + b·MW (linear). MW kosong -> prediksi kosong (tidak ditebak)."""

    def fit(self, X, y):
        from sklearn.linear_model import LinearRegression
        self.m = LinearRegression().fit(X[["mw"]].astype(float), y)
        return self

    def predict(self, X):
        mw = X[["mw"]].astype(float)
        out = np.full(len(mw), np.nan)
        ok = mw["mw"].notna().to_numpy()
        if ok.any():
            out[ok] = self.m.predict(mw[ok])
        return out


class TreeModel:
    """Model pohon untuk ΔECD = ECD − MW (bagian hidraulik/APL), lalu ECD = MW + Δ.

    MW tetap fitur, tetapi pohon tidak perlu mempelajari ECD absolut (pohon tidak bisa ekstrapolasi ke MW
    sumur lain). Imputasi median dari data training saja (tanpa leakage). MW kosong -> prediksi kosong.
    """
    target = "delta_mw"

    def __init__(self, algo):
        self.algo = algo

    def fit(self, X, y):
        X = X.astype(float)
        self.med = X.median(numeric_only=True)
        self.m = _make(self.algo).fit(X.fillna(self.med), y - X["mw"])
        return self

    def predict(self, X):
        X = X.astype(float)
        return self.m.predict(X.fillna(self.med)) + X["mw"].to_numpy()


def build(algo: str):
    return MWOnly() if algo == "mw_only" else TreeModel(algo)


# ------------------------------------------------------------------ metrik

def metrics(y: np.ndarray, p: np.ndarray, tol: float = 0.1) -> dict:
    e = p - y
    ae = np.abs(e)
    if len(y) == 0:
        return {"n": 0}
    ss = float(((y - y.mean()) ** 2).sum())
    return {"n": int(len(y)), "mae": float(ae.mean()), "rmse": float(np.sqrt((e ** 2).mean())),
            "r2": float(1 - (e ** 2).sum() / ss) if ss > 0 else None,
            "p90": float(np.quantile(ae, 0.9)), "p95": float(np.quantile(ae, 0.95)), "bias": float(e.mean()),
            "within_tol": float((ae <= tol).mean())}


def grouped_bootstrap_ci(frame: pd.DataFrame, n: int = 200, seed: int = 0) -> list[float] | None:
    wells = frame["well"].unique()
    if len(wells) < 2:
        return None
    rng = np.random.default_rng(seed)
    g = {w: frame[frame.well == w] for w in wells}
    vals = []
    for _ in range(n):
        pick = rng.choice(wells, size=len(wells), replace=True)
        d = pd.concat([g[w] for w in pick])
        vals.append(float(np.abs(d["pred"] - d["ecd"]).mean()))
    return [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))]


def per_state(frame: pd.DataFrame) -> dict:
    out = {}
    for st, d in frame.groupby("state"):
        if len(d) >= 20:
            out[st] = metrics(d["ecd"].to_numpy(), d["pred"].to_numpy())
    cl = frame[frame.state.isin(CLEANOUT_STATES)]
    out["CLEANOUT"] = metrics(cl["ecd"].to_numpy(), cl["pred"].to_numpy()) if len(cl) >= 20 else {"n": int(len(cl))}
    return out


# ------------------------------------------------------------------ training

def train_job(model_id: int, algo: str, blind: list[str], train: list[str], lowo: bool) -> None:
    db = SessionLocal()
    rec = db.get(MLModel, model_id)
    logs: list[str] = []

    def say(m):
        logs.append(f"{datetime.now(timezone.utc):%H:%M:%S} {m}")
        rec.log = "\n".join(logs)
        db.commit()

    try:
        say("memuat data sumur …")
        frames = {}
        for w in db.scalars(select(Well).where(Well.name.in_(train + blind))):
            full = well_frame(db, w)
            d = labeled(full)
            no_mw = len(labeled(full, need_mw=False)) - len(d)
            say(f"{w.name}: {len(d)} baris berlabel" + (f" ({no_mw} baris ber-ECD dibuang: MW Rec 04 tidak ada)" if no_mw else ""))
            if len(d):
                frames[w.name] = d
            del full
        tr_names = [w for w in train if w in frames]
        bl_names = [w for w in blind if w in frames]
        if not tr_names:
            raise RuntimeError("tidak ada sumur training dengan label ECD valid")
        data = pd.concat([frames[w] for w in tr_names])
        res: dict = {"algo": algo, "train_rows": int(len(data)), "experiments": {}}

        algos = [algo] if algo != "all" else ALGOS
        finals: dict = {}
        cv = None
        for a in algos:
            exp: dict = {"label": ALGO_LABEL[a]}
            if lowo and len(tr_names) >= 2:
                say(f"{a}: leave-one-well-out …")
                parts = []
                for w in tr_names:
                    trn = data[data.well != w]
                    tst = frames[w].copy()
                    m = build(a).fit(trn[FEATURES], trn["ecd"])
                    tst["pred"] = m.predict(tst[FEATURES])
                    parts.append(tst)
                cv = pd.concat(parts)
                exp["lowo"] = metrics(cv["ecd"].to_numpy(), cv["pred"].to_numpy())
                exp["lowo_per_well"] = {w: metrics(d["ecd"].to_numpy(), d["pred"].to_numpy()) for w, d in cv.groupby("well")}
                exp["lowo_ci_mae"] = grouped_bootstrap_ci(cv)
            say(f"{a}: fit final + uji blind …")
            final = build(a).fit(data[FEATURES], data["ecd"])
            finals[a] = final
            bref = None
            if bl_names:
                bref = pd.concat([frames[w] for w in bl_names]).copy()
                bref["pred"] = final.predict(bref[FEATURES])
                exp["blind"] = metrics(bref["ecd"].to_numpy(), bref["pred"].to_numpy())
                exp["blind_per_well"] = {w: metrics(d["ecd"].to_numpy(), d["pred"].to_numpy()) for w, d in bref.groupby("well")}
                exp["per_state"] = per_state(bref)
            if cv is not None:
                exp["per_state_lowo"] = per_state(cv)
                if bref is None:
                    exp["per_state"] = exp["per_state_lowo"]
            # interval prediksi: residual LOWO (banyak sumur) lebih representatif daripada 1 sumur blind
            ref = cv if cv is not None else bref
            if ref is not None:
                r = ref["pred"] - ref["ecd"]
                exp["residual_q"] = {st: [float(d.quantile(0.05)), float(d.quantile(0.95))]
                                     for st, d in r.groupby(ref["state"]) if len(d) >= 20}
                exp["residual_q"]["ALL"] = [float(r.quantile(0.05)), float(r.quantile(0.95))]
                exp["interval_source"] = "lowo" if cv is not None else "blind"
            res["experiments"][a] = exp
            cv = None

        # persistence memakai ECD terukur sebelumnya -> pembanding saja, tidak tersedia di run tanpa PWD
        step = get_settings().resample_s
        pers = {"label": ALGO_LABEL["persistence"], "lowo": persistence(data, step)}
        if bl_names:
            pers["blind"] = persistence(pd.concat([frames[w] for w in bl_names]), step)
        res["experiments"]["persistence"] = pers

        def score(k):
            # pilih model dari LOWO (validasi); blind = data uji -> hanya dilaporkan, tidak untuk memilih
            e = res["experiments"][k]
            return (e.get("lowo") or e.get("blind") or {}).get("mae") or 9e9

        if algo == "all" and all(score(k) >= 9e9 for k in algos):
            say("PERINGATAN: tidak ada LOWO (butuh ≥2 sumur train) maupun blind → tidak ada metrik; pilih algoritma manual")
        a = min(algos, key=score) if algo == "all" else algo
        final, exp = finals[a], res["experiments"][a]
        res["chosen"] = a
        res["selection"] = "lowo" if (res["experiments"][a].get("lowo") or {}).get("mae") is not None else "blind"
        q = data[FEATURES].quantile([0.01, 0.99])
        rec.feature_ranges = {f: [None if pd.isna(q.loc[0.01, f]) else float(q.loc[0.01, f]),
                                  None if pd.isna(q.loc[0.99, f]) else float(q.loc[0.99, f])] for f in FEATURES}
        rec.residual_q = exp.get("residual_q", {"ALL": [-0.3, 0.3]})
        imp = getattr(getattr(final, "m", None), "feature_importances_", None)
        if imp is not None:
            tot = float(np.sum(imp)) or 1.0
            rec.importance = dict(sorted({f: float(v) / tot for f, v in zip(FEATURES, imp)}.items(), key=lambda t: -t[1]))
        path = Path(get_settings().model_dir) / f"{rec.name}_v{rec.version}_{a}.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": final, "features": FEATURES, "algo": a, "target": getattr(final, "target", "ecd")}, path)
        rec.algo = a
        rec.artifact_path = str(path)
        rec.metrics = res
        rec.features = FEATURES
        rec.train_wells = tr_names
        rec.blind_wells = bl_names
        rec.status = "candidate"
        rec.gates = {**(rec.gates or {}), "qc": False, "blind": bool(bl_names)}
        say(f"selesai: algo terpilih {a}")
    except Exception as e:  # noqa: BLE001
        rec.status = "failed"
        say(f"GAGAL: {e}\n{traceback.format_exc()[-1500:]}")
    finally:
        db.commit()
        db.close()


def start_training(db: Session, algo: str, train: list[str], blind: list[str], lowo: bool, user: str) -> MLModel:
    ver = (db.scalar(select(func.max(MLModel.version)).where(MLModel.name == "ecd")) or 0) + 1
    rec = MLModel(name="ecd", version=ver, algo=algo, status="training", train_wells=train, blind_wells=blind,
                  created_by=user, gates={})
    db.add(rec)
    db.commit()
    threading.Thread(target=train_job, args=(rec.id, algo, blind, train, lowo), daemon=True).start()
    return rec


# ------------------------------------------------------------------ inferensi

_cache: dict[str, dict] = {}


def active_model(db: Session) -> MLModel | None:
    for st in ("production", "shadow"):
        m = db.scalar(select(MLModel).where(MLModel.status == st).order_by(MLModel.promoted_at.desc().nullslast()))
        if m:
            return m
    return db.scalar(select(MLModel).where(MLModel.status == "candidate").order_by(MLModel.id.desc()))


def _load(rec: MLModel) -> dict | None:
    if not rec.artifact_path or not Path(rec.artifact_path).exists():
        return None
    if rec.artifact_path not in _cache:
        _cache[rec.artifact_path] = joblib.load(rec.artifact_path)
    return _cache[rec.artifact_path]


def predict_frame(rec: MLModel | None, df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan ecd_pred, ecd_lo, ecd_hi, ood, confidence. Pompa mati -> ECD ⓥ disuppress (NaN)."""
    out = df.copy()
    for c in ("ecd_pred", "ecd_lo", "ecd_hi"):
        out[c] = np.nan
    out["ood"] = False
    out["missing_feat"] = 0
    if rec is None or df.empty:
        return out
    art = _load(rec)
    if not art:
        return out
    X = out[art["features"]]
    pumps = out["state"].isin(PUMPS_ON_STATES)
    if pumps.any():
        out.loc[pumps, "ecd_pred"] = art["model"].predict(X[pumps])
    rq = rec.residual_q or {}
    allq = rq.get("ALL", [-0.3, 0.3])
    lo = out["state"].map(lambda s: rq.get(s, allq)[0]).astype(float)
    hi = out["state"].map(lambda s: rq.get(s, allq)[1]).astype(float)
    # interval prediksi dari residual blind: ECD_true ≈ pred − res
    out["ecd_lo"] = out["ecd_pred"] - hi
    out["ecd_hi"] = out["ecd_pred"] - lo
    rng = rec.feature_ranges or {}
    ood = pd.Series(False, index=out.index)
    for f, (a, b) in rng.items():
        if a is None or b is None or f not in out:
            continue
        span = (b - a) or 1.0
        ood |= (out[f] < a - 0.1 * span) | (out[f] > b + 0.1 * span)
    out["ood"] = ood & pumps
    out["missing_feat"] = X[["flow_in", "spp", "hookload", "rpm", "bit_depth", "mw"]].isna().sum(axis=1)
    return out
