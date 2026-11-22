"""Studi kasus rathole (H1–H3): validasi ECD ⓥ saat ECD terukur masih ada (fase 1), lalu pantau zona rathole
setelah casing di-set lebih awal (fase 2) dengan ECD ⓥ + tren parameter permukaan + indikasi per zona.

Semua angka dihitung dari data sumur yang sudah di-ingest; tidak ada asumsi operasi yang ditebak."""
from __future__ import annotations

import json

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..ml.pipeline import active_model, labeled, predict_frame, well_frame
from ..models import Event, Well
from .analysis import compute, f, series
from .data import active_ppfg, time_range
from .features import PUMPS_ON_STATES

ZONES = {"rathole": "Rathole", "atas_shoe": "Di atas shoe (cased)", "bawah_rathole": "Di bawah rathole"}
_cache: dict = {}


def _ts(s) -> pd.Timestamp | None:
    return pd.Timestamp(s).tz_convert("UTC") if s and pd.Timestamp(s).tzinfo else (pd.Timestamp(s).tz_localize("UTC") if s else None)


def _day(idx: pd.DatetimeIndex) -> pd.Index:
    return idx.tz_convert(get_settings().display_tz).strftime("%Y-%m-%d")


def _err_metrics(d: pd.DataFrame) -> dict:
    e = d["ecd_pred"] - d["ecd"]
    return {"n": int(len(d)), "mae": f(e.abs().mean(), 3), "bias": f(e.mean(), 3), "p90_abs": f(e.abs().quantile(.9), 3),
            "coverage_pct": f(100 * d["ecd"].between(d["ecd_lo"], d["ecd_hi"]).mean(), 1),
            "ecd_minus_mw_med": f((d["ecd"] - d["mw"]).median(), 3),
            "mae_mw_raw": f((d["mw"] - d["ecd"]).abs().mean(), 3)}


def analyze(db: Session, well: Well) -> dict:
    r = well.rathole
    if not r:
        return {"enabled": False, "well": well.name,
                "message": "Zona rathole belum diisi. Isi di Data & Upload → Edit sumur (top MD, base MD, sejak)."}
    rec = active_model(db)
    lo, hi = time_range(db, well.id)
    key = (well.id, rec.id if rec else None, str(hi), json.dumps(r, sort_keys=True))
    if key in _cache:
        return _cache[key]
    since = _ts(r.get("since"))
    top, base = float(r["top_md"]), float(r["base_md"])
    out: dict = {"enabled": True, "well": well.name, "section": well.section, "shoe_md": well.shoe_md,
                 "rathole": {**r, "length_ft": round(base - top, 1)},
                 "data_start": lo.isoformat() if lo else None, "data_end": hi.isoformat() if hi else None,
                 "model": None, "phase1": None, "phase2": None, "zone_table": [], "caveats": []}
    if rec:
        role = "blind" if well.name in (rec.blind_wells or []) else ("train" if well.name in (rec.train_wells or []) else "tidak dipakai")
        out["model"] = {"name": f"ecd-{rec.algo} v{rec.version}", "status": rec.status, "well_role_in_model": role}
    df = well_frame(db, well)
    if df.empty:
        out["caveats"].append("Belum ada data time untuk sumur ini.")
        return out
    p = predict_frame(rec, df)

    # ---------- Fase 1: ECD terukur tersedia (sebelum zona rathole berlaku) ----------
    lab = labeled(p)
    lab = lab[lab["ecd_pred"].notna()]
    if since is not None:
        lab = lab[lab.index < since]
    if len(lab):
        ph1 = {"t0": lab.index.min().isoformat(), "t1": lab.index.max().isoformat(), **_err_metrics(lab)}
        inz = lab[lab["bit_depth"].between(top, base)]
        ph1["in_rathole_depth"] = _err_metrics(inz) if len(inz) >= 10 else None
        ph1["per_state"] = {s: _err_metrics(g) for s, g in lab.groupby("state") if len(g) >= 20}
        daily = lab.groupby(_day(lab.index)).agg(n=("ecd", "size"), ecd=("ecd", "median"), ecd_pred=("ecd_pred", "median"),
                                                  mw=("mw", "median"), bit_max=("bit_depth", "max"))
        daily["mae"] = lab.assign(e=(lab["ecd_pred"] - lab["ecd"]).abs()).groupby(_day(lab.index))["e"].mean()
        ph1["daily"] = [{"date": d, **{k: f(v, 3 if k in ("mae",) else 2) for k, v in row.items()}} for d, row in daily.iterrows()]
        step = max(1, len(lab) // 800)
        ph1["series"] = series(lab.iloc[::step], ["ecd", "ecd_pred", "ecd_lo", "ecd_hi", "mw", "bit_depth"])
        out["phase1"] = ph1

    # ---------- Fase 2: setelah casing di-set (tanpa ECD terukur) ----------
    if since is not None and hi is not None and since < hi:
        c = compute(db, well, since.to_pydatetime(), hi, points=1500)
        if not c.get("empty"):
            d2 = c["df_full"]
            step_s = c["calc_bucket_s"]
            pumps = d2["state"].isin(PUMPS_ON_STATES)
            inr = d2["bit_depth"].between(top, base)
            day = _day(d2.index)
            rows = []
            dets = pd.DataFrame(c["detections"])
            if len(dets):
                dets["day"] = _day(pd.DatetimeIndex(pd.to_datetime(dets["start"], utc=True)))
            for dd, g in d2.groupby(day):
                gp = g[g["state"].isin(PUMPS_ON_STATES)]
                gr = gp[gp["bit_depth"].between(top, base)]
                rot = gp[gp["rpm"] > 5] if "rpm" in gp else gp.iloc[0:0]
                dz = dets[dets["day"] == dd] if len(dets) else dets
                rows.append({
                    "date": dd, "minutes": round(len(g) * step_s / 60), "pump_minutes": round(len(gp) * step_s / 60),
                    "rathole_pump_minutes": round(len(gr) * step_s / 60),
                    "bit_min": f(g["bit_depth"].min(), 0), "bit_max": f(g["bit_depth"].max(), 0),
                    "flow_med": f(gp["flow_in"].median(), 0), "spp_med": f(gp["spp"].median(), 0),
                    "spp_rathole_med": f(gr["spp"].median(), 0) if len(gr) else None,
                    "spp_per_100gpm": f((gp["spp"] / gp["flow_in"] * 100).median(), 0) if len(gp) else None,
                    "torque_med": f(rot["torque"].median(), 2) if len(rot) else None,
                    "hookload_med": f(gp["hookload"].median(), 1),
                    "ecd_pred_med": f(gp["ecd_pred"].median(), 2), "ecd_pred_max": f(gp["ecd_pred"].max(), 2),
                    "mw": f(g["mw"].median(), 2),
                    "ind_rathole": int((dz["zone"] == "rathole").sum()) if len(dz) else 0,
                    "ind_atas_shoe": int((dz["zone"] == "atas_shoe").sum()) if len(dz) else 0,
                })
            view = c["df"]
            ph2 = {"t0": since.isoformat(), "t1": hi.isoformat(), "calc_bucket_s": step_s,
                   "pump_minutes": round(int(pumps.sum()) * step_s / 60),
                   "rathole_pump_minutes": round(int((pumps & inr).sum()) * step_s / 60),
                   "ecd_pred_med": f(d2.loc[pumps, "ecd_pred"].median(), 2),
                   "ecd_pred_max": f(d2.loc[pumps, "ecd_pred"].max(), 2),
                   "ood_pct": f(100 * d2.loc[pumps, "ood"].mean(), 1) if pumps.any() else None,
                   "daily": rows,
                   "series": series(view, ["bit_depth", "spp", "flow_in", "torque", "hookload", "ecd_pred", "ecd_lo", "ecd_hi", "mw"])}
            if len(dets):
                tab = dets[dets["zone"].notna()].groupby(["label", "zone"]).size().unstack(fill_value=0)
                for z in ZONES:
                    if z not in tab:
                        tab[z] = 0
                out["zone_table"] = [{"label": lb, **{z: int(row[z]) for z in ZONES}} for lb, row in tab.iterrows()]
                ph2["detections"] = [{k: x.get(k) for k in ("start", "level", "label", "md", "zone")}
                                     for x in c["detections"] if x.get("zone")][-200:]
            out["phase2"] = ph2

    # ---------- Event terkait ----------
    out["events"] = [{"onset": e.onset.isoformat(), "end": e.end.isoformat() if e.end else None, "md": e.md,
                      "level": e.level, "category": e.category, "review": e.review_status, "detail": e.detail,
                      "evidence": e.evidence, "source": e.source}
                     for e in db.scalars(select(Event).where(Event.well_id == well.id).order_by(Event.onset))]

    # ---------- Catatan kejujuran ----------
    cv = out["caveats"]
    if out["model"] and out["model"]["well_role_in_model"] == "train":
        cv.append("Sumur ini ikut training model aktif → akurasi fase 1 terlalu optimistis (in-sample).")
    elif out["model"] and out["model"]["well_role_in_model"] == "blind":
        cv.append("Sumur ini sumur blind model aktif → akurasi fase 1 adalah uji jujur (tidak pernah dilihat model).")
    if out["phase2"]:
        cv.append("Ukuran lubang belum menjadi input model. Di section lebih kecil (mis. 6-1/8\") rugi gesek annulus "
                  "lebih besar, sehingga ECD ⓥ fase 2 kemungkinan di bawah ECD aktual. Perlu data run section kecil ber-PWD.")
        if out["phase2"].get("ood_pct") and out["phase2"]["ood_pct"] > 10:
            cv.append(f"{out['phase2']['ood_pct']}% titik fase 2 di luar rentang data training (OOD).")
    ver, _ = active_ppfg(db, well.id)
    if not ver:
        cv.append("PPFG sumur ini belum di-approve → margin terhadap FG / batas bawah belum dihitung.")
    cv.append("MW diambil dari Rec 04; cocokkan dengan MW di laporan harian.")
    cv.append("Ambang detektor belum dikalibrasi Drilling Eng + HSE: jumlah indikasi bersifat indikatif.")
    if len(_cache) > 32:
        _cache.clear()
    _cache[key] = out
    return out
