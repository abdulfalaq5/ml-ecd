#!/usr/bin/env python3
"""Estimasi bending moment, bending stress, side force, dan hookload model drill string / casing dari survey + data rig.

INI ESTIMASI, BUKAN PENGUKURAN (lihat README.md). Inti perhitungan ada di backend: app/core/bending.py, katalog
komponen + preset per section di app/bending_catalog.json. Script ini hanya membaca input, memanggil modul itu, dan
menulis CSV / LAS / JSON. Jalankan lewat tools/bending/run.sh (di container backend).

Konfigurasi string, pilih salah satu:
    --runs runs.json     per section, "berlaku mulai hole depth X → preset Y" (depth-based seperti MW Rec 04)  ← disarankan
    --preset ID          satu preset katalog untuk seluruh data
    --string file.json   daftar komponen manual (format lama)

Contoh:
    python bending_estimate.py --list-catalog
    python bending_estimate.py --example-runs runs.json
    python bending_estimate.py --well "BDSI 18" --runs runs.json --calibrate --out hasil/
    python bending_estimate.py --well GW339 --preset CSG_7_RUN --from "2026-11-11 00:00" --to "2026-11-12 19:30" --setting-depth 5354
    python bending_estimate.py --survey rec07.las --rig rec01.las --mw rec04.las --preset BHA_8.5_STD --out hasil/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/app")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.core import bending as bd  # noqa: E402

EXAMPLE_RUNS = {
    "_catatan": ["Satu baris per run / section, diurutkan dari from_hole_md. Run berlaku saat hole depth tertinggi yang sudah "
                 "dicapai ≥ from_hole_md (sama seperti MW Rec 04), termasuk saat tripping keluar dari section itu.",
                 "preset = id di katalog (lihat --list-catalog). counts / lengths mengganti jumlah joint / panjang: kunci "
                 "= id item katalog, atau '#<urutan komponen mulai 1>' bila item yang sama dipakai dua kali (mis. liner).",
                 "shoe_md_ft = shoe casing yang SUDAH terpasang saat run itu (batas friction cased / open hole).",
                 "Untuk komponen di luar katalog, ganti 'preset' dengan 'components': [{name, od, id, length, weight_ppf, bha}, …]."],
    "well": "CONTOH",
    "mw_ppg": None,
    "runs": [
        {"from_hole_md": 0, "preset": "BHA_12.25_STD", "hole_size": 12.25, "shoe_md_ft": 350, "counts": {"DC_8.25": 6, "HWDP_5": 15}},
        {"from_hole_md": 3000, "preset": "BHA_8.5_STD", "hole_size": 8.5, "shoe_md_ft": 2990, "counts": {"DC_7": 6}},
    ],
}

TIME_COLS = [("BIT_DEPTH", "ft", "Bit depth (input)"), ("HKLD", "klb", "Hookload terukur (input)"),
             ("RUN_IDX", "-", "Nomor run/section yang dipakai (1, 2, …)"),
             ("DLS_BIT", "deg/100ft", "DLS di posisi bit (survey)"),
             ("BND_BHA_EST", "kft.lbf", "ESTIMASI bending moment maks di BHA / casing"),
             ("BND_STR_EST", "kft.lbf", "ESTIMASI bending moment maks di string"),
             ("BSTR_MAX_EST", "ksi", "ESTIMASI bending stress maks"),
             ("SF_MAX_EST", "klbf", "ESTIMASI side force maks per joint (pick-up)"),
             ("BEND_UTIL_MAX", "frac", "Bending / batas sambungan maks (1 = di batas)"),
             ("HKLD_EXP", "klb", "Hookload model sesuai mode (PU/SO/ROT)"),
             ("HKLD_RESID", "klb", "Hookload terukur - model")]


def write_las(df: pd.DataFrame, path: Path, well: str, cols: list[tuple[str, str, str]]):
    null = -999.25
    lines = ["~Version Information", " VERS.   2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0", " WRAP.   NO  : One line per depth step",
             "~Well Information", f" WELL.   {well} : WELL", f" NULL.   {null} : NULL VALUE",
             " COMM.   ESTIMASI bending/side force dari survey (bukan pengukuran downhole) : COMMENT",
             "~Curve Information", " TIME .        : Date time (UTC, ISO)"]
    lines += [f" {m:<13} .{u:<9}: {d}" for m, u, d in cols]
    lines.append("~A")
    vals = df[[m for m, _, _ in cols]].astype(float).fillna(null).round(4)
    ts = df.index.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    body = [f"{t} " + " ".join(f"{x:.4f}" for x in row) for t, row in zip(ts, vals.to_numpy())]
    path.write_text("\n".join(lines + body) + "\n")


# ------------------------------------------------------------------ input

def from_db(well_name: str):
    from sqlalchemy import select

    from app.core.data import load_mw, load_survey, load_time
    from app.db import SessionLocal
    from app.models import Well
    db = SessionLocal()
    w = db.scalar(select(Well).where(Well.name == well_name))
    if not w:
        raise SystemExit(f"sumur '{well_name}' tidak ada di database")
    sv = load_survey(db, w.id)
    rig = load_time(db, w.id, bucket_s=30, channels=["bit_depth", "hole_depth", "hookload", "rpm", "wob", "flow_in", "torque"])
    return sv, rig, load_mw(db, w.id), w.shoe_md


def from_files(survey: str, rigs: list[str], mw: str | None, tz: str):
    from app.ingest.parser import canonicalize, iter_files, parse_bytes

    def read(path):
        out = []
        for name, content in iter_files(path, Path(path).read_bytes()):
            try:
                out.append(canonicalize(parse_bytes(name, content), tz))
            except ValueError as e:              # file hanya header (mis. ekspor rentang tanggal yang salah)
                print(f"lewati {name}: {e}")
        return out

    sv = pd.concat([p.data for p in read(survey)])
    parts = [p.data for f in rigs for p in read(f) if p.basis == "time" and len(p.data)]
    rig = pd.DataFrame()
    if parts:
        rig = pd.concat(parts).dropna(subset=["ts"]).set_index("ts").sort_index()
        rig = rig[~rig.index.duplicated(keep="last")].select_dtypes("number").resample("30s").mean().dropna(how="all")
    mwdf = pd.concat([p.data for p in read(mw)]) if mw else pd.DataFrame(columns=["md", "mw"])
    return sv, rig, mwdf, None


def list_catalog(cat: dict):
    print("ITEM KATALOG")
    for k, it in cat["items"].items():
        lim = it.get("bend_limit_dls") or it.get("bend_limit_ksi")
        print(f"  {k:<16} {it.get('type', ''):<5} {it.get('name', ''):<38} OD {it['od']:<6} ID {it['id']:<7} "
              f"{it.get('weight_ppf', '')} ppf  batas sambungan: {lim if lim else '-'}")
    print("\nPRESET")
    for k, p in cat["presets"].items():
        parts = []
        for e in p["components"]:
            q = f"{e['count']}×" if e.get("count") else (f"{e['length']} ft " if e.get("length") else "sisa: ")
            parts.append(q + e["item"])
        print(f"  {k:<18} {p.get('kind', ''):<7} {p.get('name', '')}\n  {'':<18} {' + '.join(parts)}")


# ------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--catalog", help="file katalog (default: katalog bawaan aplikasi)")
    ap.add_argument("--list-catalog", action="store_true", help="tampilkan item & preset katalog lalu keluar")
    ap.add_argument("--example-runs", help="tulis contoh file runs (per section) lalu keluar")
    ap.add_argument("--runs", help="file runs per section (JSON) — disarankan")
    ap.add_argument("--preset", help="satu preset katalog untuk seluruh data")
    ap.add_argument("--string", help="daftar komponen manual (JSON format lama)")
    ap.add_argument("--well", help="nama sumur di database sistem")
    ap.add_argument("--survey", help="file Rec 07 (LAS/CSV)")
    ap.add_argument("--rig", nargs="*", default=[], help="file Rec 01 basis waktu (LAS/CSV/zip)")
    ap.add_argument("--mw", help="file Rec 04 (opsional; buoyancy)")
    ap.add_argument("--tz", default="Asia/Jakarta", help="zona waktu file rig dan --from/--to")
    ap.add_argument("--from", dest="t_from", help="awal periode data waktu (mis. '2026-11-12 08:00')")
    ap.add_argument("--to", dest="t_to", help="akhir periode data waktu")
    ap.add_argument("--setting-depth", type=float, help="kedalaman akhir ujung bawah string (ft MD) untuk cek batas sambungan "
                                                        "run terakhir; default = bit depth terdalam / TD survey")
    ap.add_argument("--shoe", type=float, help="shoe casing yang sudah terpasang (ft MD); menimpa nilai dari database")
    ap.add_argument("--step", type=float, default=50.0, help="grid kedalaman bit (ft)")
    ap.add_argument("--calibrate", action="store_true", help="setel friction factor + berat block per run dari hookload PU/SO")
    ap.add_argument("--out", default="bending_out", help="folder output")
    a = ap.parse_args(argv)

    cat = bd.load_catalog(a.catalog)
    if a.list_catalog:
        list_catalog(cat)
        return
    if a.example_runs:
        Path(a.example_runs).write_text(json.dumps(EXAMPLE_RUNS, indent=2, ensure_ascii=False))
        print(f"contoh runs ditulis: {a.example_runs}")
        return
    if sum(bool(x) for x in (a.runs, a.preset, a.string)) != 1 or not (a.well or a.survey):
        ap.error("pilih tepat satu dari --runs / --preset / --string, dan salah satu dari --well / --survey")

    if a.runs:
        spec = json.loads(Path(a.runs).read_text())
    elif a.preset:
        spec = {"runs": [{"from_hole_md": 0, "preset": a.preset}]}
    else:
        spec = json.loads(Path(a.string).read_text())
    try:
        runs = bd.runs_from_spec(spec, cat)
    except ValueError as e:
        raise SystemExit(f"konfigurasi string salah: {e}")

    sv, rig, mw, shoe_db = from_db(a.well) if a.well else from_files(a.survey, a.rig, a.mw, a.tz)
    for r in runs:
        if a.shoe:
            r.cfg["shoe_md_ft"] = a.shoe
        elif r.cfg.get("shoe_md_ft") is None and shoe_db:
            r.cfg["shoe_md_ft"] = shoe_db
    if len(rig) and (a.t_from or a.t_to):
        t0 = pd.Timestamp(a.t_from).tz_localize(a.tz) if a.t_from else rig.index.min()
        t1 = pd.Timestamp(a.t_to).tz_localize(a.tz) if a.t_to else rig.index.max()
        rig = rig[(rig.index >= t0) & (rig.index <= t1)]
        print(f"periode data waktu: {t0} s/d {t1} → {len(rig)} baris")

    try:
        res = bd.compute(sv, rig, mw, runs, step=a.step, do_calibrate=a.calibrate, setting_depth=a.setting_depth)
    except ValueError as e:
        raise SystemExit(str(e))

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = (a.well or spec.get("well") or Path(a.survey).stem).replace(" ", "_")
    s = res["survey"]
    s[["md", "inc", "azi", "dls_calc"] + (["dls"] if "dls" in s else [])].to_csv(out / f"{tag}_survey_dls.csv", index=False)
    res["profile"].to_csv(out / f"{tag}_bending_depth.csv", index=False, float_format="%.4f")
    print(f"profil kedalaman: {out / f'{tag}_bending_depth.csv'}  ({len(res['profile'])} titik, {len(runs)} run, tiap {a.step:g} ft)")
    if res["limits"] is not None:
        lim = res["limits"]
        lim.to_csv(out / f"{tag}_bending_limits.csv", index=False)
        print(f"cek batas sambungan: {out / f'{tag}_bending_limits.csv'} "
              f"({int((lim['status'] == 'LEWAT BATAS').sum())} interval lewat batas, {len(lim)} total ≥80%)")
    tc = res["time"]
    if tc is not None:
        tc["BIT_DEPTH"], tc["DLS_BIT"] = tc["bit_depth"], tc["dls_bit"]
        tc["HKLD"] = tc["hookload"] if "hookload" in tc else np.nan
        tc[[m for m, _, _ in TIME_COLS] + ["mode", "run"]].to_csv(out / f"{tag}_bending_time.csv", index_label="ts_utc",
                                                                   float_format="%.4f")
        write_las(tc, out / f"{tag}_bending_time.las", a.well or tag, TIME_COLS)
        print(f"channel waktu: {out / f'{tag}_bending_time.csv'} + .las  ({len(tc)} baris, 30 s)")
    else:
        print("tidak ada data Rec 01 basis waktu → hanya profil kedalaman")
    for w in res["warnings"]:
        print("PERINGATAN:", w)
    summary = {"well": a.well or a.survey, **res["summary"], "runs": res["runs"], "warnings": res["warnings"]}
    (out / f"{tag}_summary.json").write_text(json.dumps(summary, indent=2, default=str, ensure_ascii=False))
    for r in res["runs"]:
        c = r.get("calibration") or {}
        print(f"- {r['run']} (mulai {r['from_hole_md']:g} ft, sampai {r['setting_md_ft']:g} ft): bending BHA maks "
              f"{_f(r['bnd_bha_max_kftlbf'])} kft·lbf, stress {_f(r['bstr_max_ksi'])} ksi, side force {_f(r['sf_max_klbf_per_joint'])} klbf/joint"
              + (f", utilisasi sambungan maks {_f(r['bend_util_max'], 2)}" if r.get("bend_util_max") is not None else "")
              + (f", FF {c['friction_open']} / block {c['block_weight_klb']} klb (MAE {c['mae_klb']} klb)" if c.get("ok") else "")
              + (f", {r['time_rows']} baris waktu" if r.get("time_rows") else ""))
    print(f"ringkasan: {out / f'{tag}_summary.json'}")


def _f(v, n=1):
    return "-" if v is None else f"{v:.{n}f}"


if __name__ == "__main__":
    main()
