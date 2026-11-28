"""Room/sumur, upload, QC & kelengkapan data (halaman Data & Upload, Overview)."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..core import sections as sec
from ..core.analysis import compute, f
from ..db import get_db
from ..ingest.service import get_or_create_well, ingest_bytes
from ..ingest.watcher import scan_once
from ..models import IngestFile, MudWeight, MudWeightChange, PPFGVersion, Setting, Survey, User, Well
from ..core.data import time_range
from ..security import audit, current_user, require

router = APIRouter(prefix="/api", tags=["wells"])


def well_out(db: Session, w: Well) -> dict:
    t0, last = time_range(db, w.id)
    n_ecd = db.scalar(text("SELECT count(ecd) FROM ts_data WHERE well_id=:w"), {"w": w.id})
    r = (t0, last, n_ecd)
    fresh = (datetime.now(timezone.utc) - last).total_seconds() / 60 if last else None
    return {"id": w.id, "name": w.name, "field": w.field, "aliases": w.aliases or [], "section": w.section,
            "shoe_md": w.shoe_md, "role": w.role, "status": w.status, "notes": w.notes, "rathole": w.rathole,
            "sections": w.sections or [],
            "data_start": r[0].isoformat() if r[0] else None, "data_end": last.isoformat() if last else None,
            "fresh_min": f(fresh, 0), "ecd_points": int(r[2] or 0)}


class SectionsIn(BaseModel):
    sections: list[dict]


@router.get("/wells/{wid}/sections")
def get_sections(wid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    w = db.get(Well, wid) or _404()
    return {"sections": w.sections or [], "presets": sec.presets_for_ui(), "casing_id_default": sec.casing_id_defaults()}


@router.put("/wells/{wid}/sections")
def put_sections(wid: int, body: SectionsIn, db: Session = Depends(get_db), u: User = Depends(require("well_edit"))):
    w = db.get(Well, wid) or _404()
    try:
        rows = sec.clean_sections(body.sections)
    except ValueError as e:
        raise HTTPException(400, f"Section: {e}")
    w.sections = rows or None
    audit(db, u.username, "well_sections", f"{w.name}: " + "; ".join(
        f"{r['from_md']:g} ft {r['hole_size']:g}\" pv={r['pv']} yp={r['yp']}" for r in rows))
    db.commit()
    return {"sections": rows}


@router.get("/wells")
def list_wells(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [well_out(db, w) for w in db.scalars(select(Well).order_by(Well.name))]


class WellIn(BaseModel):
    name: str
    field: str = ""
    section: str = ""
    shoe_md: float | None = None
    role: str = "train"
    status: str = "active"
    notes: str = ""
    rathole: dict | None = None


@router.post("/wells")
def create_well(body: WellIn, db: Session = Depends(get_db), u: User = Depends(require("well_edit"))):
    w = get_or_create_well(db, body.name)
    for k in ("field", "section", "shoe_md", "role", "status", "notes"):
        setattr(w, k, getattr(body, k))
    audit(db, u.username, "well_create", w.name)
    db.commit()
    return well_out(db, w)


@router.put("/wells/{wid}")
def update_well(wid: int, body: WellIn, db: Session = Depends(get_db), u: User = Depends(require("well_edit"))):
    w = db.get(Well, wid) or _404()
    for k in ("field", "section", "shoe_md", "role", "status", "notes"):
        setattr(w, k, getattr(body, k))
    if "rathole" in body.model_fields_set:  # hanya diubah bila dikirim
        w.rathole = clean_rathole(body.rathole)
    audit(db, u.username, "well_update", f"{w.name}: shoe={w.shoe_md} role={w.role} rathole={w.rathole}")
    db.commit()
    return well_out(db, w)


def clean_rathole(r: dict | None) -> dict | None:
    """Validasi zona rathole. Kosong / top tidak diisi -> None (fitur rathole nonaktif)."""
    if not r or r.get("top_md") in (None, ""):
        return None
    try:
        top, base = float(r["top_md"]), float(r["base_md"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Rathole: isi top MD dan base MD (angka, ft)")
    if not 0 <= top < base:
        raise HTTPException(400, "Rathole: top MD harus lebih dangkal dari base MD")
    since = r.get("since") or None
    if since:
        try:
            datetime.fromisoformat(str(since).replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "Rathole: format waktu 'sejak' tidak valid")
    return {"top_md": top, "base_md": base, "since": since, "note": str(r.get("note") or "")[:500]}


def _404():
    raise HTTPException(404, "Sumur tidak ditemukan")


@router.post("/wells/{wid}/upload")
async def upload(wid: int, files: list[UploadFile] = File(...), mode: str = Form("append"), tz: str = Form("WIB"),
                 db: Session = Depends(get_db), u: User = Depends(require("upload"))):
    """tz: zona waktu file bila kolom waktunya tanpa offset — WIB (Navita, default) atau UTC (sebagian export SLB/Halliburton)."""
    w = db.get(Well, wid) or _404()
    src_tz = {"WIB": None, "UTC": "UTC"}.get(tz.upper())
    if tz.upper() not in ("WIB", "UTC"):
        raise HTTPException(400, "Zona waktu harus WIB atau UTC")
    out = []
    for fl in files:
        content = await fl.read()
        out.extend(ingest_bytes(db, w, fl.filename or "upload", content, u.username, "replace" if mode == "replace" else "append",
                                source_tz=src_tz))
    return {"results": out}


# ---------------------------------------------------------------- mud weight manual

class MWRow(BaseModel):
    md: float
    mw: float
    remark: str | None = None


class MWIn(BaseModel):
    rows: list[MWRow]


class MWChangeRow(BaseModel):
    ts: datetime           # ISO; tanpa zona = WIB
    mw: float
    remark: str | None = None


class MWChangeIn(BaseModel):
    rows: list[MWChangeRow]


def _changes_out(db: Session, wid: int) -> list[dict]:
    rows = db.scalars(select(MudWeightChange).where(MudWeightChange.well_id == wid).order_by(MudWeightChange.ts)).all()
    return [{"ts": r.ts.isoformat(), "mw": r.mw, "remark": r.remark} for r in rows]


def _mw_out(db: Session, wid: int) -> dict:
    rows = db.scalars(select(MudWeight).where(MudWeight.well_id == wid).order_by(MudWeight.md)).all()
    fids = {r.file_id for r in rows if r.file_id}
    files = {f.id: f.filename for f in db.scalars(select(IngestFile).where(IngestFile.id.in_(fids)))} if fids else {}
    src = "manual" if rows and not fids else ("file: " + ", ".join(sorted(set(files.values()))) if fids else None)
    # pembanding: mud density in dari data streaming (median per 500 ft hole depth), bila ada
    dens = db.execute(text("""SELECT floor(hole_depth / 500) * 500 AS d, percentile_cont(0.5) WITHIN GROUP (ORDER BY mud_dens_in)
                              FROM ts_data WHERE well_id=:w AND mud_dens_in BETWEEN 6 AND 22 AND hole_depth > 0
                              GROUP BY 1 ORDER BY 1"""), {"w": wid}).all()
    return {"rows": [{"md": r.md, "mw": r.mw, "remark": r.remark} for r in rows], "source": src,
            "changes": _changes_out(db, wid),
            "stream_density": [{"md_from": float(d), "mw": round(float(v), 2)} for d, v in dens]}


@router.get("/wells/{wid}/mud-weight")
def get_mw(wid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    db.get(Well, wid) or _404()
    return _mw_out(db, wid)


@router.put("/wells/{wid}/mud-weight")
def put_mw(wid: int, body: MWIn, db: Session = Depends(get_db), u: User = Depends(require("mw_edit"))):
    """Tabel MW manual (mis. dari DDR / mud report) bila tidak ada file Rec 04 Navita. Mengganti seluruh tabel MW sumur.
    MW berlaku sejak hole depth `md` tercapai (sama seperti Rec 04)."""
    w = db.get(Well, wid) or _404()
    seen: set[float] = set()
    rows = []
    for r in sorted(body.rows, key=lambda r: r.md):
        if r.md < 0 or r.md > 40000:
            raise HTTPException(400, f"Kedalaman {r.md:g} ft di luar 0–40.000 ft")
        if not 6 <= r.mw <= 22:
            raise HTTPException(400, f"MW {r.mw:g} ppg di luar 6–22 ppg (isi dalam ppg)")
        if r.md in seen:
            raise HTTPException(400, f"Kedalaman {r.md:g} ft diisi dua kali")
        seen.add(r.md)
        rows.append({"well_id": wid, "md": float(r.md), "mw": float(r.mw), "remark": (r.remark or "").strip()[:256] or None})
    db.execute(MudWeight.__table__.delete().where(MudWeight.well_id == wid))
    if rows:
        db.bulk_insert_mappings(MudWeight, rows)
    audit(db, u.username, "mud_weight_manual", f"{w.name}: " + "; ".join(f"{r['md']:g} ft {r['mw']:g} ppg" for r in rows))
    db.commit()
    return _mw_out(db, wid)


@router.put("/wells/{wid}/mud-weight/changes")
def put_mw_changes(wid: int, body: MWChangeIn, db: Session = Depends(get_db), u: User = Depends(require("mw_edit"))):
    """Perubahan MW berbasis waktu (jam dari DDR / mud report). MW berlaku sejak `ts` sampai MW per kedalaman
    berubah lagi. Mengganti seluruh daftar perubahan berwaktu sumur; tabel MW per kedalaman tidak disentuh."""
    w = db.get(Well, wid) or _404()
    wib = ZoneInfo("Asia/Jakarta")
    seen: set = set()
    rows = []
    for r in sorted(body.rows, key=lambda r: r.ts if r.ts.tzinfo else r.ts.replace(tzinfo=wib)):
        ts = r.ts if r.ts.tzinfo else r.ts.replace(tzinfo=wib)
        if not 6 <= r.mw <= 22:
            raise HTTPException(400, f"MW {r.mw:g} ppg di luar 6–22 ppg (isi dalam ppg)")
        if ts in seen:
            raise HTTPException(400, f"Waktu {ts.isoformat()} diisi dua kali")
        seen.add(ts)
        rows.append({"well_id": wid, "ts": ts, "mw": float(r.mw), "remark": (r.remark or "").strip()[:256] or None})
    db.execute(MudWeightChange.__table__.delete().where(MudWeightChange.well_id == wid))
    if rows:
        db.bulk_insert_mappings(MudWeightChange, rows)
    audit(db, u.username, "mud_weight_change", f"{w.name}: " + ("; ".join(
        f"{r['ts'].astimezone(wib):%d %b %Y %H:%M} WIB {r['mw']:g} ppg" for r in rows) or "dikosongkan"))
    db.commit()
    return _mw_out(db, wid)


@router.post("/ingest/scan")
def scan(_: User = Depends(require("upload"))):
    return {"processed": scan_once()}


@router.get("/wells/{wid}/files")
def files(wid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.scalars(select(IngestFile).where(IngestFile.well_id == wid).order_by(IngestFile.id.desc())).all()
    return [{"id": r.id, "filename": r.filename, "record": r.record, "basis": r.basis, "fmt": r.fmt, "rows": r.rows,
             "t_start": r.t_start.isoformat() if r.t_start else None, "t_end": r.t_end.isoformat() if r.t_end else None,
             "d_start": r.d_start, "d_end": r.d_end, "status": r.status, "qc": r.qc, "mapped": r.mapped,
             "unmapped": r.unmapped, "uploaded_by": r.uploaded_by, "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/wells/{wid}/quality")
def quality(wid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    w = db.get(Well, wid) or _404()
    rows = db.scalars(select(IngestFile).where(IngestFile.well_id == wid)).all()
    comp = {}
    for rec in (1, 2, 3, 4, 7):
        for basis in ("time", "depth"):
            fs = [r for r in rows if r.record == rec and r.basis == basis and r.status == "ok"]
            if not fs:
                continue
            ts = [r.t_start for r in fs if r.t_start] + [r.t_end for r in fs if r.t_end]
            ds = [r.d_start for r in fs if r.d_start is not None] + [r.d_end for r in fs if r.d_end is not None]
            comp[f"{rec}_{basis}"] = {"files": len(fs), "rows": sum(r.rows for r in fs),
                                      "t0": min(ts).isoformat() if ts else None, "t1": max(ts).isoformat() if ts else None,
                                      "d0": min(ds) if ds else None, "d1": max(ds) if ds else None}
    ppfg = db.scalars(select(PPFGVersion).where(PPFGVersion.well_id == wid).order_by(PPFGVersion.version)).all()
    mw_n = db.scalar(select(func.count()).select_from(MudWeight).where(MudWeight.well_id == wid))
    sv_n = db.scalar(select(func.count()).select_from(Survey).where(Survey.well_id == wid))
    # ketersediaan label: % waktu pumps-on (Rec 01) yang punya ECD valid (Rec 02), per jam
    cov = pd.read_sql(text(
        "SELECT time_bucket(INTERVAL '1 hour', ts) h, "
        "bool_or(record=1) r1, bool_or(ecd BETWEEN 7 AND 20) ecd, "
        "avg(flow_in) FILTER (WHERE record=1) q FROM ts_data WHERE well_id=:w GROUP BY 1 ORDER BY 1"),
        db.connection(), params={"w": wid})
    timeline, avail = [], None
    if len(cov):
        cov["seg"] = cov.apply(lambda r: "rec01_ecd" if r.r1 and r.ecd else ("rec01" if r.r1 else ("ecd_only" if r.ecd else "none")), axis=1)
        full = pd.date_range(cov.h.min(), cov.h.max(), freq="1h", tz="UTC")
        seg = cov.set_index("h")["seg"].reindex(full).fillna("gap")
        start = seg.index[0]
        prev = seg.iloc[0]
        for t, v in seg.iloc[1:].items():
            if v != prev:
                timeline.append({"t0": start.isoformat(), "t1": t.isoformat(), "kind": prev})
                start, prev = t, v
        timeline.append({"t0": start.isoformat(), "t1": (seg.index[-1] + pd.Timedelta(hours=1)).isoformat(), "kind": prev})
        pumped = cov[(cov.q.fillna(0) > 50)]
        avail = float((pumped.ecd.fillna(False)).mean()) if len(pumped) else None
    qc = []
    for r in sorted(rows, key=lambda r: r.id, reverse=True)[:30]:
        for q in r.qc or []:
            qc.append({**q, "file": r.filename, "record": r.record})
    so = db.get(Setting, f"qc_signoff_{wid}")
    return {"well": well_out(db, w), "completeness": comp,
            "ppfg_versions": [{"id": v.id, "version": v.version, "status": v.status} for v in ppfg],
            "mud_weight_rows": mw_n, "survey_rows": sv_n, "target_availability": f(avail, 3),
            "timeline": timeline, "qc": qc,
            "signoff": so.value if so else None}


@router.post("/wells/{wid}/qc/signoff")
def signoff(wid: int, db: Session = Depends(get_db), u: User = Depends(require("qc_signoff"))):
    db.get(Well, wid) or _404()
    key = f"qc_signoff_{wid}"
    s = db.get(Setting, key) or Setting(key=key)
    s.value = {"by": u.username, "at": datetime.now(timezone.utc).isoformat()}
    db.merge(s)
    audit(db, u.username, "qc_signoff", f"well {wid}")
    db.commit()
    return s.value


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(current_user)):
    out = []
    for w in db.scalars(select(Well).where(Well.status == "active").order_by(Well.name)):
        base = well_out(db, w)
        card = {**base, "level": "UNAVAILABLE", "ecd": None, "ecd_kind": None, "margin_up": None, "margin_low": None,
                "state": None, "bit_depth": None, "note": "belum ada data", "spark": []}
        if base["data_end"]:
            try:
                r = compute(db, w, points=120)
            except Exception as e:  # noqa: BLE001
                card["note"] = f"gagal hitung: {e}"
                out.append(card)
                continue
            if not r.get("empty"):
                df = r["df"]
                last = df.iloc[-1]
                kind = "m" if pd.notna(last.get("ecd")) else ("v" if pd.notna(last.get("ecd_pred")) else None)
                stale = (base["fresh_min"] or 0) > 10
                card.update({
                    "level": last["level"], "ecd": f(last.get("ecd_ref")), "ecd_kind": kind,
                    "margin_up": f(min(x for x in [last.get("margin_up_bit"), last.get("margin_up_oh")] if pd.notna(x)) if any(pd.notna(x) for x in [last.get("margin_up_bit"), last.get("margin_up_oh")]) else None),
                    "margin_low": f(last.get("margin_low")), "state": last.get("state"),
                    "bit_depth": f(last.get("bit_depth"), 0), "stale": stale,
                    "note": last.get("reason") or "tidak ada anomali terdeteksi pada data tersedia",
                    "spark": [f(x) for x in df["ecd_ref"].tail(80).tolist()],
                    "model": r["model"].name + f" v{r['model'].version}" if r["model"] else None,
                })
        out.append(card)
    return out
