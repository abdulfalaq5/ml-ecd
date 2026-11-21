"""Parser file Navita / rig: LAS 2.0 (spasi atau tab) dan CSV (ASCII Navita 2 baris header, atau CSV rig).

Output: ParsedTable berisi DataFrame kanonik + metadata. Mapping tag eksplisit dari mnemonics.yaml.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

NULLS = {"-999.25", "-999.2500", "-999", "-9999", "null", "NULL", "NaN", "nan", ""}
DT_START = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})[ T]+(\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)")
FREE_TEXT = {"REMARK", "FORMATION", "FORMATIONNAME", "COMMENT"}   # bisa berisi spasi
TEXT_MNEM = {"WID", "SKNO", "DATE", "TIME", *FREE_TEXT}
REC_IN_NAME = re.compile(r"record[ _-]?0?(\d)", re.I)


@lru_cache
def mnemonics() -> dict:
    return yaml.safe_load((Path(__file__).resolve().parent.parent / "mnemonics.yaml").read_text())


class EmptyFile(ValueError):
    """File valid tetapi tanpa baris data."""


@dataclass
class Curve:
    mnem: str
    unit: str
    desc: str


@dataclass
class ParsedTable:
    filename: str
    fmt: str                      # las-navita | las-rig | csv-navita | csv-rig
    basis: str                    # time | depth
    record: int                   # 1,2,3,4,7 (0 = tidak dikenali)
    header: dict
    curves: list[Curve]
    raw: pd.DataFrame             # kolom = nama unik per curve
    data: pd.DataFrame = field(default_factory=pd.DataFrame)  # kanonik
    mapped: dict = field(default_factory=dict)                # canonical -> tag asli
    unmapped: list = field(default_factory=list)
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------- pembacaan file

def iter_files(filename: str, content: bytes):
    """Yield (nama, bytes) untuk file biasa atau isi .zip (LAS/CSV/TXT)."""
    if filename.lower().endswith(".zip") or content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for info in zf.infolist():
                n = info.filename
                if info.is_dir() or "__MACOSX" in n or Path(n).name.startswith("."):
                    continue
                if Path(n).suffix.lower() in {".las", ".csv", ".txt", ".asc"}:
                    yield Path(n).name, zf.read(info)
    else:
        yield Path(filename).name, content


def _decode(b: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def _unique(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for n in names:
        k = n or "COL"
        if k in seen:
            seen[k] += 1
            out.append(f"{k}__{seen[k]}")
        else:
            seen[k] = 0
            out.append(k)
    return out


CURVE_RE = re.compile(r"^\s*(?P<mn>[^\s.:]+)\s*\.(?P<unit>[^\s:]*)\s*(?P<data>[^:]*?)\s*:\s*(?P<desc>.*?)\s*$")


def _parse_header_line(line: str) -> tuple[str, str, str, str] | None:
    m = CURVE_RE.match(line)
    if m:
        return m["mn"].strip(), m["unit"].strip(), m["data"].strip(), m["desc"].strip()
    if ":" in line:  # mis. "SPARE3\t\t\t: TOTAL PUMP" (tanpa titik)
        left, desc = line.split(":", 1)
        return left.strip(), "", "", desc.strip()
    return None


def _split_header(content: bytes) -> tuple[str, bytes]:
    """Pisahkan header LAS (didecode) dan blok data ~A (tetap bytes, agar tidak menggandakan memori)."""
    m = re.search(rb"(?im)^[ \t]*~A[^\n]*(\n|\Z)", content)
    if not m:
        return _decode(content), None
    return _decode(content[: m.start()]), content[m.end():]


def _read_numeric(body: bytes, names: list[str], sep: str, text_cols: list[str]) -> pd.DataFrame:
    """Baca blok data langsung ke float (NULL Navita -> NaN). Kolom teks tetap string."""
    it = pd.read_csv(io.BytesIO(body), sep=sep, header=None, names=names, index_col=False,
                     dtype={c: str for c in text_cols}, na_values=sorted(NULLS), keep_default_na=False,
                     on_bad_lines="skip", engine="c", encoding="latin-1", skip_blank_lines=True,
                     chunksize=50_000)  # per potongan: memori puncak tokenizer kecil untuk file ratusan MB
    parts = list(it)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=names)


def parse_las(content: bytes | str, filename: str) -> ParsedTable:
    if isinstance(content, str):
        content = content.encode("utf-8")
    head, body = _split_header(content)
    section = ""
    curves: list[Curve] = []
    header: dict = {}
    for line in head.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("~"):
            section = s[1:2].upper()
            continue
        parsed = _parse_header_line(line)
        if not parsed:
            continue
        mn, unit, val, desc = parsed
        if section == "C":
            curves.append(Curve(mn, unit, desc))
        elif section == "W":
            header[mn.upper()] = val
    if body is None or not curves:
        raise ValueError("Format LAS tidak dikenali (blok ~C atau ~A tidak ada)")
    if not body.strip():
        raise EmptyFile("blok ~A kosong: file tidak berisi baris data")

    names = _unique([c.mnem for c in curves])
    # beberapa LAS rig mengulang nama kolom di baris pertama setelah ~A; lewati baris kosong/judul
    while body:
        nl = body.find(b"\n")
        first = (body if nl < 0 else body[:nl]).decode("latin-1").strip()
        if first and first.split()[0].upper() != curves[0].mnem.upper():
            break
        body = b"" if nl < 0 else body[nl + 1:]
    peek = body[:20000].decode("latin-1").splitlines()[:20]
    tab = any("\t" in ln for ln in peek)
    is_time = curves[0].mnem.lower() in {"dtsrv", "time"}
    fmt = "las-rig" if tab else "las-navita"
    text_cols = [n for n, c in zip(names, curves) if c.mnem.upper() in TEXT_MNEM]

    if tab:
        raw = _read_numeric(body, names, "\t", [names[0], *text_cols])
    else:
        split_dt = is_time and bool(peek) and bool(re.match(r"^\s*\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}", peek[0]))
        cols = (["__date", "__clock"] + names[1:]) if split_dt else names
        try:
            if any(c.mnem.upper() in FREE_TEXT for c in curves):
                raise ValueError("kolom teks bebas")  # REMARK/FORMATION bisa berisi spasi
            raw = _read_numeric(body, cols, r"\s+", (cols[:2] if split_dt else [names[0]]) + text_cols)
            if split_dt:
                ts = raw.pop("__date") + "T" + raw.pop("__clock")
                raw.insert(0, names[0], ts)
        except (pd.errors.ParserError, ValueError):
            lines = body.decode("latin-1").splitlines()
            if is_time:
                lines = [DT_START.sub(r"\1T\2", ln, count=1) for ln in lines]
            raw = _read_whitespace(lines, names)
    return ParsedTable(filename, fmt, "time" if is_time else "depth", 0, header, curves, raw)


def _read_whitespace(body: list[str], names: list[str]) -> pd.DataFrame:
    buf = "\n".join(ln for ln in body if ln.strip())
    try:
        return pd.read_csv(io.StringIO(buf), sep=r"\s+", header=None, names=names, dtype=str,
                           keep_default_na=False, engine="c")
    except (pd.errors.ParserError, ValueError):
        # baris dengan teks bebas (mis. REMARK berisi spasi): sisa token digabung ke kolom terakhir
        n = len(names)
        rows = []
        for ln in body:
            t = ln.split()
            if not t:
                continue
            if len(t) > n:
                t = t[: n - 1] + [" ".join(t[n - 1:])]
            elif len(t) < n:
                t = t + [""] * (n - len(t))
            rows.append(t)
        return pd.DataFrame(rows, columns=names)


def parse_csv(content: bytes | str, filename: str) -> ParsedTable:
    if isinstance(content, str):
        content = content.encode("utf-8")
    if content.startswith(b"\xef\xbb\xbf"):
        content = content[3:]
    pos, lines = 0, []
    for _ in range(2):  # dua baris header pertama saja yang didecode
        nl = content.find(b"\n", pos)
        end = len(content) if nl < 0 else nl
        lines.append(_decode(content[pos:end]).rstrip("\r"))
        pos = end + 1
        if nl < 0:
            break
    if not lines or not lines[0].strip():
        raise ValueError("CSV kosong")
    header = [h.strip() for h in lines[0].split(",")]
    skip = 1
    fmt = "csv-rig"
    units = [""] * len(header)
    if len(lines) > 1:
        second = [h.strip() for h in lines[1].split(",")]
        unit_like = sum(1 for x in second if x in {"timestamp", "----", "ft", "psi", "klb", "ppg", "%", "rpm", "bbl", "SPM"})
        if unit_like >= max(3, len(second) // 4):
            skip = 2
            fmt = "csv-navita"
            units = second
    curves = [Curve(h, u, h) for h, u in zip(header, units)]
    names = _unique(header)
    start = 0
    for _ in range(skip):
        nl = content.find(b"\n", start)
        start = len(content) if nl < 0 else nl + 1
    text_cols = [names[0]] + [n for n, c in zip(names, curves) if c.mnem.upper() in TEXT_MNEM]
    raw = _read_numeric(content[start:], names, ",", text_cols)
    if raw.empty:
        raise EmptyFile("CSV hanya berisi header: tidak ada baris data (cek ulang rentang waktu export)")
    first = header[0].lower()
    is_time = first in {"date time server", "time", "dtsrv", "timestamp", "datetime"}
    return ParsedTable(filename, fmt, "time" if is_time else "depth", 0, {}, curves, raw)


def parse_bytes(name: str, content: bytes) -> ParsedTable:
    head = content.lstrip()[:400]
    if head.startswith(b"~") or b"~V" in head[:200].upper():
        pt = parse_las(content, name)
    else:
        pt = parse_csv(content, name)
    pt.record = detect_record(pt)
    return pt


# ---------------------------------------------------------------- mapping kanonik

def _to_num(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        out = s.astype(float)
        return out.where(out > -999, np.nan)
    s = s.astype(str).str.strip()
    s = s.where(~s.isin(NULLS), None)
    out = pd.to_numeric(s, errors="coerce")
    return out.where(out > -999, np.nan)


def detect_record(pt: ParsedTable) -> int:
    m = REC_IN_NAME.search(pt.filename)
    if m:
        return int(m.group(1))  # termasuk 5/6/8 -> nanti dilewati (bukan record model)
    mn = {c.mnem.upper() for c in pt.curves}
    if "FGMIN" in mn or "SFG" in mn:
        return 3
    if "MUDWEIGHT" in mn:
        return 4
    if "DSVM" in mn or "SINC" in mn:
        return 7
    rid_col = next((n for c, n in zip(pt.curves, pt.raw.columns)
                    if c.mnem.upper() == "RID" or c.desc.upper() == "RECORD IDENTIFIER"), None)
    if rid_col is not None:
        rid = _to_num(pt.raw[rid_col]).dropna()
        if len(rid):
            return int(rid.mode().iloc[0])
    return 1


def _match(pt: ParsedTable, schema: dict) -> dict[str, str]:
    """canonical -> nama kolom unik di pt.raw. Mnemonic diutamakan, deskripsi untuk SPARE/tidak dikenal."""
    names = list(pt.raw.columns)
    mapped: dict[str, str] = {}
    used: set[str] = set()
    for canon, spec in schema.items():
        al = {a.upper() for a in spec.get("mnem", [])}
        for c, n in zip(pt.curves, names):
            if n not in used and c.mnem.upper() in al:
                mapped[canon] = n
                used.add(n)
                break
    known_mnem = {a.upper() for spec in schema.values() for a in spec.get("mnem", [])}
    for canon, spec in schema.items():
        if canon in mapped:
            continue
        al = {a.upper() for a in spec.get("desc", [])}
        for c, n in zip(pt.curves, names):
            if n in used or c.mnem.upper() in known_mnem:
                continue
            if c.desc.upper() in al:
                mapped[canon] = n
                used.add(n)
                break
    # header ASCII Navita membawa satuan: "Mud Flow In (gpm)" -> "MUD FLOW IN"
    for canon, spec in schema.items():
        if canon in mapped:
            continue
        al = {_norm(a) for a in [*spec.get("mnem", []), *spec.get("desc", [])]}
        for c, n in zip(pt.curves, names):
            if n in used or c.mnem.upper() in known_mnem:
                continue
            if _norm(c.desc) in al or _norm(c.mnem) in al:
                mapped[canon] = n
                used.add(n)
                break
    return mapped


def _norm(x: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", x).strip().upper()


SKIP_UNMAPPED = {"WID", "SKNO", "RID", "SQID", "DATE", "TIME", "DTSRV", "DEPTH", "DATE TIME SERVER"}


ZERO_AS_NULL = ("flow_in", "rpm", "wob", "rop", "torque", "spp", "spm1", "spm2", "spm3", "flow_out_pct")


def canonicalize(pt: ParsedTable, source_tz: str) -> ParsedTable:
    mn = mnemonics()
    schema = {1: mn["rig"], 2: mn["rig"], 3: mn["ppfg"], 4: mn["mud"], 7: mn["survey"]}.get(pt.record, mn["rig"])
    mapping = _match(pt, schema)
    raw = pt.raw
    df = pd.DataFrame(index=raw.index)

    if pt.basis == "time":
        tcol = raw.columns[0]
        ts_raw = raw[tcol].astype(str).str.strip()
        if ts_raw.str.fullmatch(r"\d{9,11}(\.\d+)?").mean() > 0.9:
            ts = pd.to_datetime(pd.to_numeric(ts_raw, errors="coerce"), unit="s", utc=True)
        else:
            ts = pd.to_datetime(ts_raw.str.replace("T", " ", regex=False), errors="coerce", format="mixed")
            ts = ts.dt.tz_localize(source_tz, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
        df["ts"] = ts
    else:
        dcol = raw.columns[0]
        df["md"] = _to_num(raw[dcol])

    for canon, col in mapping.items():
        if canon == "md" and pt.basis == "depth":
            # indeks DEPTH utama; kolom MD (MDPPFG/DSVM) hanya cadangan bila indeks kosong
            df["md"] = df["md"].fillna(_to_num(raw[col]))
            continue
        if canon in {"formation", "remark"}:
            v = raw[col].astype(str).str.strip()
            df[canon] = v.where(~v.isin(NULLS), None)
        else:
            df[canon] = _to_num(raw[col])

    if pt.record in (1, 2) and pt.fmt == "las-rig":
        # Export LAS rig menulis 0 sebagai -999.25 (terbukti identik dengan CSV pasangannya, PDSI 53.2)
        for c in ZERO_AS_NULL:
            if c in df:
                df[c] = df[c].fillna(0.0)
    if pt.record in (1, 2):
        spm = [c for c in ("spm1", "spm2", "spm3") if c in df]
        if spm:
            df["spm_total"] = df[spm].sum(axis=1, min_count=1)
            df = df.drop(columns=spm)
        if "ecd" in df:
            df.loc[df["ecd"] <= 0, "ecd"] = np.nan  # ECD = 0 berarti tidak ada sensor
        if "anp" in df:
            df.loc[df["anp"] <= 0, "anp"] = np.nan
        key = "ts" if pt.basis == "time" else "md"
        df = df.dropna(subset=[key]).drop_duplicates(subset=[key], keep="last").sort_values(key)
    elif pt.record == 3:
        vals = [c for c in ("pp", "sfg", "fg_min", "fg_max") if c in df]
        df = df.dropna(subset=["md"]).dropna(subset=vals, how="all").drop_duplicates("md").sort_values("md")
    elif pt.record == 4:
        df = df.dropna(subset=["md"])
        if "mw" in df:
            df = df[df["mw"] > 0]
        df = df.drop_duplicates("md").sort_values("md")
    elif pt.record == 7:
        if "md" in mapping:  # survey: MD stasiun (DSVM) lebih tepat daripada indeks
            alt = _to_num(raw[mapping["md"]])
            df["md"] = alt.fillna(df["md"])
        df = df.dropna(subset=["md"]).drop_duplicates("md").sort_values("md")

    pt.data = df.reset_index(drop=True)
    pt.mapped = {k: next((c.mnem for c, n in zip(pt.curves, raw.columns) if n == v), v) for k, v in mapping.items()}
    used = set(mapping.values()) | {raw.columns[0]}
    pt.unmapped = sorted({c.mnem for c, n in zip(pt.curves, raw.columns)
                          if n not in used and c.mnem.upper() not in SKIP_UNMAPPED and not c.mnem.upper().startswith("SPARE")})
    return pt
