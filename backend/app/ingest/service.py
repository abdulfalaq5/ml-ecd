"""Ingest: parse -> kanonik -> QC -> simpan (COPY) + catat lineage di ingest_files."""
from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import engine
from ..models import CHANNELS, AuditLog, IngestFile, MudWeight, PPFGRow, PPFGVersion, Survey, Well
from .parser import EmptyFile, ParsedTable, canonicalize, iter_files, mnemonics, parse_bytes

log = logging.getLogger("ingest")

REQUIRED_RIG = ["bit_depth", "hole_depth", "hookload", "spp", "flow_in", "rpm", "torque", "wob", "rop"]
CRITICAL_RIG = ["bit_depth", "hole_depth", "flow_in"]          # tanpa ini file time-based hampir tidak berguna
LABEL = {"bit_depth": "bit depth", "hole_depth": "hole depth", "flow_in": "flow in", "hookload": "hookload", "spp": "SPP",
         "rpm": "RPM", "torque": "torque", "wob": "WOB", "rop": "ROP", "ecd": "ECD terukur", "mud_dens_in": "mud density in",
         "block_pos": "block position", "active_pit": "active pit", "flow_out_pct": "flow out %", "trip_tank": "trip tank",
         "gain_loss": "gain/loss", "anp": "annular pressure", "actc": "activity code"}


def _copy_upsert(table: str, key_cols: list[str], df: pd.DataFrame, mode: str) -> int:
    """COPY ke tabel temp lalu INSERT .. ON CONFLICT (append: DO NOTHING, replace: DO UPDATE)."""
    if df.empty:
        return 0
    cols = list(df.columns)
    buf = io.StringIO()
    out = df.copy()
    for c in cols:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d %H:%M:%S.%f+00")
    out.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    collist = ", ".join(cols)
    upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in key_cols)
    conflict = "DO NOTHING" if mode == "append" or not upd else f"DO UPDATE SET {upd}"
    raw = engine.raw_connection()
    try:
        pg = raw.driver_connection
        with pg.cursor() as cur:
            cur.execute(f"CREATE TEMP TABLE tmp_ingest (LIKE {table} INCLUDING DEFAULTS) ON COMMIT DROP")
            with cur.copy(f"COPY tmp_ingest ({collist}) FROM STDIN WITH (FORMAT csv, NULL '')") as cp:
                while chunk := buf.read(1 << 20):
                    cp.write(chunk)
            cur.execute(f"INSERT INTO {table} ({collist}) SELECT {collist} FROM tmp_ingest "
                        f"ON CONFLICT ({', '.join(key_cols)}) {conflict}")
            n = cur.rowcount
        pg.commit()
        return n
    finally:
        raw.close()


def qc_checks(pt: ParsedTable, well: Well) -> list[dict]:
    df = pt.data
    out: list[dict] = []

    def add(level, title, txt):
        out.append({"level": level, "title": title, "text": txt})

    for lvl, title, txt in pt.notes:
        add(lvl, title, txt)
    if pt.record in (1, 2):
        present = [c for c in REQUIRED_RIG if c in df and df[c].notna().any()]
        miss = [c for c in REQUIRED_RIG if c not in present]
        if pt.record == 1:
            crit = [c for c in CRITICAL_RIG if c not in present]
            if crit:
                add("error", "Kanal kunci tidak terbaca",
                    f"{', '.join(LABEL.get(c, c) for c in crit)} tidak ditemukan → hole depth / state operasi / ECD ⓥ tidak bisa "
                    "dihitung. Kemungkinan nama kanal belum dikenal (lihat 'Tag tidak dipetakan'); kirim contoh file ke admin.")
            if miss:
                add("warn", "Fitur wajib model", "tidak tersedia/kosong: " + ", ".join(miss))
            else:
                add("ok", "Fitur wajib model", "semua tersedia: " + ", ".join(present))
            read = [f"{LABEL.get(k, k)} ← {v}" for k, v in pt.mapped.items()]
            add("info", "Kanal terbaca", "; ".join(read) if read else "tidak ada")
            if pt.basis == "time" and "ts" in df and len(df):
                now = pd.Timestamp.now(tz="UTC")
                if df["ts"].max() > now + pd.Timedelta(minutes=30):
                    add("warn", "Waktu di masa depan",
                        f"data sampai {df['ts'].max().tz_convert(get_settings().display_tz):%Y-%m-%d %H:%M} WIB (lebih dari sekarang). "
                        "Kemungkinan zona waktu file salah: upload ulang dengan pilihan zona waktu yang benar (mode replace).")
        if "actc" in df and df["actc"].notna().any() and (df["actc"].fillna(0) == 0).all():
            add("warn", "ACTC = 0 di seluruh file", "operating state diturunkan dari flow, RPM, bit vs hole depth, block")
        for c in ("active_pit", "gain_loss", "flow_out_pct"):
            if pt.record == 1 and (c not in df or df[c].isna().all()):
                add("warn", f"{c} kosong", "deteksi loss/influx terbatas untuk file ini")
        if pt.basis == "time" and len(df) > 2:
            dt = df["ts"].diff().dt.total_seconds().dropna()
            med = float(dt.median()) if len(dt) else 0
            gaps = dt[dt > 300]
            add("ok" if gaps.empty else "warn", "Sampling & gap",
                f"median {med:.0f} dtk; gap > 5 mnt: {len(gaps)}" + (f" (terpanjang {gaps.max() / 60:.0f} mnt)" if len(gaps) else ""))
        rng = mnemonics()["ranges"]
        for c, (lo, hi) in rng.items():
            if c in df:
                v = df[c].dropna()
                bad = int(((v < lo) | (v > hi)).sum())
                if bad:
                    add("warn", f"Outlier {c}", f"{bad} titik di luar {lo}–{hi} (di-flag, tidak dibuang)")
        if pt.record == 2:
            n = int(df["ecd"].notna().sum()) if "ecd" in df else 0
            add("ok" if n else "warn", "Label ECD", f"{n} titik ECD valid" if n else "ECD kosong → hanya ECD prediksi ⓥ untuk run ini")
    if pt.record == 3:
        add("ok", "PPFG", f"{len(df)} baris; kolom: " + ", ".join(k for k in ("pp", "sfg", "fg_min", "fg_max") if k in df))
        if "formation" not in df or df["formation"].isna().all():
            add("warn", "FORMATION kosong", "menunggu formation tops")
    if pt.record == 4:
        add("ok" if len(df) else "warn", "Mud weight", f"{len(df)} baris MW > 0")
    if pt.record == 7:
        add("ok" if len(df) else "warn", "Survey", f"{len(df)} stasiun")
    wid = pt.raw["WID"].dropna().astype(str).str.strip() if "WID" in pt.raw else pd.Series(dtype=str)
    wid = wid[~wid.isin({"", "-999.25", "nan"})]
    if len(wid):
        w = wid.mode().iloc[0]
        if w not in (well.aliases or []) and w != well.name:
            add("warn", "WID berbeda", f"WID file = {w}; disimpan ke sumur {well.name} (alias ditambahkan)")
    if pt.unmapped:
        add("info", "Tag tidak dipetakan", ", ".join(pt.unmapped[:20]) + (" …" if len(pt.unmapped) > 20 else ""))
    return out


def _range(pt: ParsedTable):
    df = pt.data
    if pt.basis == "time" and "ts" in df and len(df):
        return df["ts"].min().to_pydatetime(), df["ts"].max().to_pydatetime(), None, None
    if "md" in df and len(df):
        return None, None, float(df["md"].min()), float(df["md"].max())
    return None, None, None, None


def store(db: Session, well: Well, pt: ParsedTable, sha: str, user: str, mode: str) -> IngestFile:
    t0, t1, d0, d1 = _range(pt)
    rec = IngestFile(well_id=well.id, filename=pt.filename, sha256=sha, record=pt.record, basis=pt.basis,
                     fmt=pt.fmt, rows=len(pt.data), t_start=t0, t_end=t1, d_start=d0, d_end=d1,
                     mapped=pt.mapped, unmapped=pt.unmapped, qc=qc_checks(pt, well), uploaded_by=user)
    db.add(rec)
    db.flush()
    df = pt.data
    if pt.record in (1, 2):
        cols = [c for c in CHANNELS if c in df]
        out = df[(["ts"] if pt.basis == "time" else ["md"]) + cols].copy()
        out.insert(0, "record", pt.record)
        out.insert(0, "well_id", well.id)
        if pt.basis == "time":
            if mode == "replace" and t0:
                db.execute(text("DELETE FROM ts_data WHERE well_id=:w AND record=:r AND ts BETWEEN :a AND :b"),
                           {"w": well.id, "r": pt.record, "a": t0, "b": t1})
                db.commit()
            rec.rows = _copy_upsert("ts_data", ["well_id", "record", "ts"], out, mode)
        else:
            rec.rows = _copy_upsert("depth_data", ["well_id", "record", "md"], out, "replace")
    elif pt.record == 3 and pt.basis == "time":
        rec.status = "skipped"  # PPFG acuan = Rec 03 basis depth; versi time-based tidak dipakai
        rec.qc = [*rec.qc, {"level": "info", "title": "Rec 03 basis waktu", "text": "dilewati; PPFG memakai file basis depth"}]
    elif pt.record == 3:
        nxt = (db.scalar(select(func.max(PPFGVersion.version)).where(PPFGVersion.well_id == well.id)) or 0) + 1
        ver = PPFGVersion(well_id=well.id, version=nxt, status="draft", source_file_id=rec.id, created_by=user,
                          notes=f"import {pt.filename}")
        db.add(ver)
        db.flush()
        keep = [c for c in ("md", "tvd", "pp", "sfg", "fg_min", "fg_max", "shmax", "obg", "formation") if c in df]
        rows = df[keep].replace({np.nan: None}).to_dict("records")
        db.bulk_insert_mappings(PPFGRow, [{**r, "version_id": ver.id} for r in rows])
    elif pt.record == 4:
        db.execute(delete(MudWeight).where(MudWeight.well_id == well.id))
        keep = [c for c in ("md", "tvd", "mw", "remark") if c in df]
        rows = df[keep].replace({np.nan: None}).to_dict("records")
        db.bulk_insert_mappings(MudWeight, [{**r, "well_id": well.id, "file_id": rec.id} for r in rows])
    elif pt.record == 7:
        db.execute(delete(Survey).where(Survey.well_id == well.id))
        keep = [c for c in ("md", "tvd", "inc", "azi", "dls") if c in df]
        rows = df[keep].replace({np.nan: None}).to_dict("records")
        db.bulk_insert_mappings(Survey, [{**r, "well_id": well.id, "file_id": rec.id} for r in rows])
    else:
        rec.status = "skipped"
    # simpan alias WID
    if "WID" in pt.raw:
        wid = pt.raw["WID"].dropna().astype(str).str.strip()
        wid = wid[~wid.isin({"", "-999.25", "nan"})]
        if len(wid):
            w = wid.mode().iloc[0]
            if w != well.name and w not in (well.aliases or []):
                well.aliases = [*(well.aliases or []), w]
    if pt.record == 1 and pt.basis == "time" and not db.scalar(select(func.count()).select_from(MudWeight)
                                                                  .where(MudWeight.well_id == well.id)):
        rec.qc = [*rec.qc, {"level": "warn", "title": "Mud weight belum ada",
                            "text": "ECD ⓥ belum bisa dihitung untuk sumur ini. Isi MW manual di Data & Upload → Mud weight, "
                                    "atau upload file MW (Rec 04)."}]
    db.add(AuditLog(username=user, action="ingest",
                    detail=f"{well.name}: {pt.filename} Rec {pt.record:02d} {pt.basis} {rec.rows} baris"))
    db.commit()
    return rec


def ingest_bytes(db: Session, well: Well, filename: str, content: bytes, user: str, mode: str = "append",
                 force: bool = False, source_tz: str | None = None) -> list[dict]:
    """source_tz: zona waktu kolom waktu tanpa offset (default WIB dari setting; Navita, SLB, dan Halliburton memakai
    WIB/UTC+7 menurut klien 28 Nov; 'UTC' hanya untuk file yang ditulis dalam UTC). Kolom waktu yang membawa offset (Z, +07:00) selalu dibaca sesuai offset-nya."""
    settings = get_settings()
    results = []
    updir = Path(settings.upload_dir) / well.name
    updir.mkdir(parents=True, exist_ok=True)
    (updir / Path(filename).name).write_bytes(content)  # arsip file mentah
    for name, b in iter_files(filename, content):
        sha = hashlib.sha256(b).hexdigest()
        old = db.scalar(select(IngestFile).where(IngestFile.well_id == well.id, IngestFile.sha256 == sha))
        if old and force:
            db.delete(old)  # proses ulang (mis. setelah perbaikan parser)
            db.flush()
        elif old:
            results.append({"file": name, "status": "duplicate", "message": "sudah pernah di-upload"})
            continue
        try:
            pt = canonicalize(parse_bytes(name, b), source_tz or settings.source_tz)
            rec = store(db, well, pt, sha, user, mode)
            results.append({"file": name, "status": rec.status, "record": rec.record, "basis": rec.basis,
                            "fmt": rec.fmt, "rows": rec.rows, "qc": rec.qc, "id": rec.id})
        except EmptyFile as e:
            db.rollback()
            results.append({"file": name, "status": "skipped", "message": str(e)})
        except Exception as e:  # noqa: BLE001  laporkan per file, lanjut file berikutnya
            db.rollback()
            log.exception("ingest gagal %s", name)
            results.append({"file": name, "status": "error", "message": str(e)})
    return results


def get_or_create_well(db: Session, name: str) -> Well:
    name = name.strip()
    w = db.scalar(select(Well).where(Well.name == name))
    if w:
        return w
    for cand in db.scalars(select(Well)):
        if name in (cand.aliases or []):
            return cand
    w = Well(name=name, aliases=[])
    db.add(w)
    db.commit()
    return w
