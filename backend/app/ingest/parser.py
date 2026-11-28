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
SURVEY_IN_NAME = re.compile(r"survey|svy|deviation|directional", re.I)
EXCEL_EXT = (".xlsx", ".xlsm", ".xls")
# header kolom waktu (setelah _norm) untuk CSV/Excel non-Navita (SLB, Halliburton, rig lain)
TIME_HEADERS = {"DATE TIME SERVER", "TIME", "DTSRV", "TIMESTAMP", "DATETIME", "DATE TIME", "DATE", "TIME STAMP",
                "RIG TIME", "YYYY MM DD HH MM SS", "TIME INDEX", "INDEX TIME"}
DATE_ONLY = re.compile(r"^\s*(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})\s*$")
CLOCK = re.compile(r"^\s*\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s*$")
DMY = re.compile(r"^\s*(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})")


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
    if filename.lower().endswith(EXCEL_EXT):
        yield Path(filename).name, content
    elif filename.lower().endswith(".zip") or content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for info in zf.infolist():
                n = info.filename
                if info.is_dir() or "__MACOSX" in n or Path(n).name.startswith("."):
                    continue
                if Path(n).suffix.lower() in {".las", ".csv", ".txt", ".asc", *EXCEL_EXT}:
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


CURVE_RE = re.compile(r"^\s*(?P<mn>[^\s.:]+(?: [^\s.:]+)*)\s*\.(?P<unit>[^\s:]*)\s*(?P<data>[^:]*?)\s*:\s*(?P<desc>.*?)\s*$")


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
    is_time = curves[0].mnem.lower() in {"dtsrv", "time", "datetime", "timestamp", "date", "time_stamp"}
    fmt = "las-rig" if tab else "las-navita"
    text_cols = [n for n, c in zip(names, curves) if c.mnem.upper() in TEXT_MNEM]

    if tab:
        raw = _read_numeric(body, names, "\t", [names[0], *text_cols])
    else:
        split_dt = (is_time and bool(peek) and bool(re.match(r"^\s*\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}", peek[0]))
                    and not (len(curves) > 1 and curves[1].mnem.upper() == "TIME"))   # DATE + TIME = dua kurva
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


@lru_cache
def _alias_keys() -> frozenset:
    """Semua nama kanal yang dikenal (mnemonik & deskripsi, dinormalisasi) + header waktu: untuk mencari baris header."""
    keys = set(TIME_HEADERS)
    for schema in mnemonics().values():
        if isinstance(schema, dict):
            for spec in schema.values():
                if isinstance(spec, dict):
                    keys |= {_norm(a) for a in [*spec.get("mnem", []), *spec.get("desc", [])]}
    keys.discard("")
    return frozenset(keys)


def _header_score(cells: list) -> int:
    return sum(1 for c in cells if c is not None and str(c).strip() and _norm(str(c)) in _alias_keys())


def _sep_of(line: str) -> str:
    return "," if line.count(",") >= max(line.count(";"), line.count("\t")) else (";" if line.count(";") >= line.count("\t") else "\t")


def _is_blank_row(line: str) -> bool:
    return not re.sub(r"[,;\t\s\"]", "", line)


def parse_csv(content: bytes | str, filename: str) -> ParsedTable:
    if isinstance(content, str):
        content = content.encode("utf-8")
    if content.startswith(b"\xef\xbb\xbf"):
        content = content[3:]
    pos, lines, starts = 0, [], []
    for _ in range(60):  # baris awal saja yang didecode (header bisa di bawah blok judul laporan)
        nl = content.find(b"\n", pos)
        end = len(content) if nl < 0 else nl
        starts.append(pos)
        lines.append(_decode(content[pos:end]).rstrip("\r"))
        pos = end + 1
        if nl < 0:
            break
    h = 0
    if _header_score(_split_cells(lines[0])) < 2:
        # laporan survey (Halliburton/SLB): judul, info sumur, lalu baris header "MD, Inc, Azi, TVD, …"
        h = next((i for i, ln in enumerate(lines[1:], 1) if _header_score(_split_cells(ln)) >= 3), 0)
    if h:
        nxt = next((i for i in range(h + 1, min(h + 4, len(lines))) if not _is_blank_row(lines[i])), None)
        lines = [lines[h]] + ([lines[nxt]] if nxt is not None else [])
        content = content[starts[h]:] if nxt is None else (
            content[starts[h]:starts[h + 1]] + content[starts[nxt]:])
    if not lines or not lines[0].strip():
        raise ValueError("CSV kosong")
    sep = _sep_of(lines[0])
    header = [h.strip().strip('"') for h in lines[0].split(sep)]
    skip = 1
    fmt = "csv-rig"
    units = [_unit_in_header(h) for h in header]
    if len(lines) > 1:
        second = [h.strip().strip('"') for h in lines[1].split(sep)]
        unit_like = sum(1 for x in second if x in {"timestamp", "----", "ft", "psi", "klb", "ppg", "%", "rpm", "bbl", "SPM"})
        if unit_like >= max(3, len(second) // 4):
            skip = 2
            fmt = "csv-navita"
            units = second
        elif _is_unit_row(second):
            skip = 2
            units = [u or v for u, v in zip(second, units)]
    curves = [Curve(h, u, h) for h, u in zip(header, units)]
    names = _unique(header)
    start = 0
    for _ in range(skip):
        nl = content.find(b"\n", start)
        start = len(content) if nl < 0 else nl + 1
    text_cols = [names[0]] + [n for n, c in zip(names, curves) if c.mnem.upper() in TEXT_MNEM]
    if len(names) > 1:
        text_cols.append(names[1])          # kolom TIME bila tanggal & jam terpisah (dikonversi lagi bila angka)
    raw = _read_numeric(content[start:], names, sep, text_cols)
    if raw.empty:
        raise EmptyFile("CSV hanya berisi header: tidak ada baris data (cek ulang rentang waktu export)")
    if len(names) > 1 and names[1] in raw and not _looks_clock(raw[names[1]]):
        raw[names[1]] = _to_num(raw[names[1]])
    is_time = _norm(header[0]) in TIME_HEADERS or _looks_datetime(raw[names[0]])
    return ParsedTable(filename, fmt, "time" if is_time else "depth", 0, {}, curves, raw)


def _split_cells(line: str) -> list[str]:
    return [c.strip().strip('"') for c in line.split(_sep_of(line))]


def _unit_in_header(h: str) -> str:
    m = re.search(r"[(\[]([^)\]]*)[)\]]\s*$", h)
    return m.group(1).strip() if m else ""


def _is_num(x: str) -> bool:
    try:
        float(x)
        return True
    except ValueError:
        return False


def _is_unit_row(row: list[str]) -> bool:
    """Baris ke-2 berisi satuan (ft, klbf, psi, gal/min, …) bila mayoritas sel teks pendek, bukan angka/tanggal."""
    vals = [x for x in row if x]
    if len(vals) < 2:
        return False
    texty = [x for x in vals if not _is_num(x) and not DATE_ONLY.match(x) and not re.match(r"^\s*\d{4}-\d{2}-\d{2}", x)
             and not DMY.match(x) and not CLOCK.match(x) and len(x) <= 16]
    return len(texty) >= 0.6 * len(vals)


def _looks_clock(s: pd.Series) -> bool:
    v = s.dropna().astype(str).head(50)
    return len(v) > 0 and v.str.match(CLOCK).mean() > 0.9


def _looks_datetime(s: pd.Series) -> bool:
    v = s.dropna().astype(str).str.strip().head(50)
    if v.empty:
        return False
    pat = r"^(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4}|\d{14})(?:[ T]\d{1,2}:\d{2}.*)?$"
    return v.str.match(pat).mean() > 0.9 or v.str.fullmatch(r"\d{10}(?:\d{3})?(?:\.\d+)?").mean() > 0.9


def excel_to_csv(content: bytes) -> bytes:
    """Sheet Excel pertama yang berisi tabel → CSV (header, baris satuan bila ada, data). Untuk survey/MW/time-based
    dari SLB, Halliburton, atau rekap manual. Baris judul di atas header dilewati."""
    sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, dtype=object)
    for _, df in sheets.items():
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if df.empty:
            continue
        rows = df.values.tolist()
        scores = [_header_score(r) for r in rows[:60]]
        best = max(range(len(scores)), key=lambda i: scores[i]) if scores else 0
        order = [best] if scores and scores[best] >= 3 else range(min(len(rows) - 1, 30))
        for i in order:
            cells = ["" if pd.isna(x) else re.sub(r"\s+", " ", str(x)).strip() for x in rows[i]]
            texts = [x for x in cells if x and not _is_num(x)]
            if len(texts) < 2:
                continue
            nxt = [r for r in rows[i + 1:i + 4]]
            numeric = lambda r: sum(1 for x in r if isinstance(x, (int, float, pd.Timestamp)) and not pd.isna(x)
                                    or (isinstance(x, str) and _is_num(x.strip())))
            if not any(numeric(r) >= 2 for r in nxt):
                continue
            out = pd.DataFrame(rows[i + 1:], columns=_unique([c or f"COL{j}" for j, c in enumerate(cells)]))
            out = out.map(lambda x: x.isoformat(sep=" ") if isinstance(x, (pd.Timestamp,)) or hasattr(x, "isoformat") else x)
            buf = io.StringIO()
            out.to_csv(buf, index=False)
            return buf.getvalue().encode("utf-8")
    raise ValueError("Excel: tidak ditemukan tabel (baris header + baris angka) di sheet mana pun")


def parse_bytes(name: str, content: bytes) -> ParsedTable:
    if name.lower().endswith(EXCEL_EXT):
        content = excel_to_csv(content)
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
    if pt.basis == "depth" and _is_generic_survey(pt):
        return 7
    if pt.basis == "depth" and _has_alias(pt, "mud", "mw") and len(pt.curves) <= 8:
        return 4                                   # tabel MW generik: kedalaman + MW (+ catatan)
    rid_col = next((n for c, n in zip(pt.curves, pt.raw.columns)
                    if c.mnem.upper() == "RID" or c.desc.upper() == "RECORD IDENTIFIER"), None)
    if rid_col is not None:
        rid = _to_num(pt.raw[rid_col]).dropna()
        if len(rid):
            return int(rid.mode().iloc[0])
    return 1


def _has_alias(pt: ParsedTable, schema: str, canon: str) -> bool:
    spec = mnemonics()[schema][canon]
    keys = {_norm(c.mnem) for c in pt.curves} | {_norm(c.desc) for c in pt.curves}
    return bool(keys & {_norm(a) for a in [*spec.get("mnem", []), *spec.get("desc", [])]})


def _is_generic_survey(pt: ParsedTable) -> bool:
    """Survey dari SLB/Halliburton/manual: kolom MD + inklinasi + azimuth, sedikit kolom, atau nama file 'survey'."""
    if not (_has_alias(pt, "survey", "inc") and _has_alias(pt, "survey", "azi")):
        return False
    return len(pt.curves) <= 14 or bool(SURVEY_IN_NAME.search(pt.filename))


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
    """'Bit Depth (ft)' / 'BIT_DEPTH [m]' / 'Hook-Load' → 'BIT DEPTH' / 'HOOK LOAD'."""
    x = re.sub(r"\s*[(\[][^)\]]*[)\]]\s*$", "", str(x))
    return re.sub(r"[\s_\-]+", " ", x).strip().upper()


COMMENT_HEADERS = {"COMMENTS", "COMMENT", "REMARKS", "REMARK", "DESCRIPTION", "STATION", "STATION TYPE", "SURVEY TYPE"}
PROJ_RE = re.compile(r"^\s*proj", re.I)
SKIP_UNMAPPED = {"WID", "SKNO", "RID", "SQID", "DATE", "TIME", "DTSRV", "DEPTH", "DATE TIME SERVER"}


# Satuan non-standar → satuan kanonik (torque kft·lb). Contoh: export Rec 01 BLSE-055 (ACS-26) menulis TORQUE
# dalam lbf.ft (median 5.040 saat sirkulasi), file lain sumur yang sama kft.lb.
# Data SLB / Halliburton bisa metrik: dikonversi ke satuan lapangan (ft, klb, psi, gpm, ppg, kft·lb, ft/h).
_TQ = {"LBF.FT": 1e-3, "FT.LBF": 1e-3, "LB.FT": 1e-3, "FT.LB": 1e-3, "LBFFT": 1e-3, "FTLBF": 1e-3,
       "KN.M": 0.737562, "KNM": 0.737562, "N.M": 0.000737562, "NM": 0.000737562}
_LEN = {"M": 3.28084, "METER": 3.28084, "METRE": 3.28084, "MTR": 3.28084}
_FORCE = {"KN": 0.224809, "KDAN": 2.24809, "DAN": 0.00224809, "TON": 2.20462, "TONNE": 2.20462, "T": 2.20462,
          "MT": 2.20462, "LBF": 1e-3, "LB": 1e-3, "KG": 0.00220462, "KGF": 0.00220462}
_PRESS = {"BAR": 14.5038, "KPA": 0.145038, "MPA": 145.038}
_FLOW = {"L/MIN": 0.264172, "LPM": 0.264172, "M3/MIN": 264.172, "M3/H": 4.40287, "BBL/MIN": 42.0, "BPM": 42.0}
_DENS = {"SG": 8.3454, "G/CM3": 8.3454, "G/CC": 8.3454, "KG/M3": 0.0083454, "KG/L": 8.3454, "LB/FT3": 0.133681, "PCF": 0.133681}
_ROP = {"M/H": 3.28084, "M/HR": 3.28084, "FT/MIN": 60.0, "M/MIN": 196.85}
_VOL = {"M3": 6.28981, "L": 0.00628981}
UNIT_FACTORS = {"torque": _TQ, "torque_max": _TQ,
                **{c: _LEN for c in ("bit_depth", "bit_tvd", "hole_depth", "hole_tvd", "block_pos", "md", "tvd")},
                "hookload": _FORCE, "hookload_max": _FORCE, "wob": _FORCE,
                "spp": _PRESS, "anp": _PRESS, "flow_in": _FLOW,
                "ecd": _DENS, "mud_dens_in": _DENS, "mw": _DENS, "rop": _ROP,
                "active_pit": _VOL, "trip_tank": _VOL, "gain_loss": _VOL,
                "dls": {"DEG/30M": 1 / 0.984252, "°/30M": 1 / 0.984252, "DEG/10M": 3.048}}


def _unit_of(pt: ParsedTable, raw: pd.DataFrame, col: str) -> str:
    return next((c.unit for c, n in zip(pt.curves, raw.columns) if n == col), "")


def _unit_factor(canon: str, unit: str) -> float:
    u = unit.strip().upper().replace("-", ".").replace(" ", "")
    return UNIT_FACTORS.get(canon, {}).get(u, 1.0)


ZERO_AS_NULL = ("flow_in", "rpm", "wob", "rop", "torque", "spp", "spm1", "spm2", "spm3", "flow_out_pct")


def parse_time(pt: ParsedTable, raw: pd.DataFrame, source_tz: str) -> pd.Series:
    """Kolom waktu → UTC. Mendukung: ISO / 'YYYY-MM-DD hh:mm:ss', tanggal & jam di dua kolom (DATE, TIME),
    dd/mm/yyyy vs mm/dd/yyyy (ditebak dari isi), epoch detik / milidetik, dan offset zona waktu di teks (Z, +07:00).
    Tanpa offset: dianggap `source_tz` (default WIB; bisa dipilih UTC saat upload)."""
    tcol = raw.columns[0]
    ts_raw = raw[tcol].astype(str).str.strip()
    if len(raw.columns) > 1 and ts_raw.head(50).str.match(DATE_ONLY).mean() > 0.9 and _looks_clock(raw[raw.columns[1]]):
        ts_raw = ts_raw + " " + raw[raw.columns[1]].astype(str).str.strip()
        pt.notes.append(("info", "Waktu", f"tanggal ({tcol}) + jam ({raw.columns[1]}) digabung"))
    if ts_raw.str.fullmatch(r"1\d{12}(\.\d+)?").mean() > 0.9:   # epoch ms (14 digit = yyyymmddHHMMSS Navita)
        return pd.to_datetime(pd.to_numeric(ts_raw, errors="coerce"), unit="ms", utc=True)
    if ts_raw.str.fullmatch(r"\d{9,11}(\.\d+)?").mean() > 0.9:
        return pd.to_datetime(pd.to_numeric(ts_raw, errors="coerce"), unit="s", utc=True)
    dayfirst = False
    m = ts_raw.head(5000).str.extract(DMY).dropna()
    if len(m):
        a, b = m[0].astype(int), m[1].astype(int)
        if (a > 12).any():
            dayfirst = True
        elif (b > 12).any():
            dayfirst = False
        else:
            dayfirst = True     # ambigu (semua ≤ 12): Indonesia memakai hari/bulan
            pt.notes.append(("warn", "Format tanggal ambigu", "tanggal ≤ 12 semua: dibaca hari/bulan/tahun (dd/mm/yyyy). "
                             "Cek rentang waktu hasil upload."))
    txt = ts_raw.str.replace("T", " ", regex=False)
    has_tz = txt.head(50).str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True).mean() > 0.9
    if has_tz:
        return pd.to_datetime(txt, errors="coerce", format="mixed", dayfirst=dayfirst, utc=True)
    ts = pd.to_datetime(txt, errors="coerce", format="mixed", dayfirst=dayfirst)
    return ts.dt.tz_localize(source_tz, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")


def min_curvature(md, inc, azi, tvd0: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """TVD & DLS (°/100 ft) metode minimum curvature. Tie-in: stasiun pertama; bila MD pertama > 0 tanpa TVD,
    dianggap lubang vertikal dari permukaan (TVD = MD di stasiun pertama bila inklinasi kecil)."""
    md, inc, azi = (np.asarray(x, dtype=float) for x in (md, inc, azi))
    i1, i2 = np.radians(inc[:-1]), np.radians(inc[1:])
    da = np.radians(azi[1:] - azi[:-1])
    cosb = np.cos(i2 - i1) - np.sin(i1) * np.sin(i2) * (1 - np.cos(da))
    beta = np.arccos(np.clip(cosb, -1, 1))
    rf = np.where(beta > 1e-9, 2 / np.where(beta > 1e-9, beta, 1) * np.tan(beta / 2), 1.0)
    dmd = np.diff(md)
    dtvd = dmd / 2 * (np.cos(i1) + np.cos(i2)) * rf
    if tvd0 is None:  # permukaan → stasiun pertama: anggap lurus dengan inklinasi rata-rata 0..inc1
        a = np.radians(inc[0]) if len(inc) else 0.0
        tvd0 = md[0] * (np.sin(a) / a if a > 1e-9 else 1.0) if len(md) else 0.0
    tvd = np.concatenate([[tvd0], tvd0 + np.cumsum(dtvd)]) if len(md) else np.array([])
    dls = np.concatenate([[0.0], np.where(dmd > 0, np.degrees(beta) / np.where(dmd > 0, dmd, 1) * 100, 0.0)]) if len(md) else np.array([])
    return tvd, dls


def complete_survey(df: pd.DataFrame, notes: list) -> pd.DataFrame:
    """Survey tanpa TVD / DLS (mis. dari SLB, Halliburton, atau Excel manual) dilengkapi minimum curvature."""
    if not {"inc", "azi"} <= set(df) or df[["inc", "azi"]].dropna().empty:
        notes.append(("warn", "Survey tidak lengkap", "kolom inklinasi / azimuth tidak ditemukan"))
        return df
    df = df.dropna(subset=["inc", "azi"]).reset_index(drop=True)
    tie = "tvd" in df and pd.notna(df["tvd"].iloc[0])
    has_tvd = "tvd" in df and df["tvd"].notna().all()
    has_dls = "dls" in df and df["dls"].notna().iloc[1:].all() if len(df) > 1 else True
    tvd, dls = min_curvature(df["md"], df["inc"], df["azi"], float(df["tvd"].iloc[0]) if tie else None)
    if not has_tvd:
        df["tvd"] = df["tvd"].fillna(pd.Series(tvd)) if "tvd" in df else tvd
        notes.append(("info", "TVD dihitung", "minimum curvature" + ("" if tie else "; tie-in: lurus dari permukaan ke stasiun pertama")))
    if not has_dls:
        df["dls"] = df["dls"].fillna(pd.Series(dls)) if "dls" in df else dls
        notes.append(("info", "DLS dihitung", "minimum curvature, °/100 ft"))
    if (df["inc"] < 0).any() or (df["inc"] > 120).any() or (df["azi"] < 0).any() or (df["azi"] > 360).any():
        notes.append(("warn", "Survey di luar rentang", "inklinasi harus 0–120°, azimuth 0–360°: cek urutan kolom"))
    return df


def canonicalize(pt: ParsedTable, source_tz: str) -> ParsedTable:
    mn = mnemonics()
    schema = {1: mn["rig"], 2: mn["rig"], 3: mn["ppfg"], 4: mn["mud"], 7: mn["survey"]}.get(pt.record, mn["rig"])
    mapping = _match(pt, schema)
    raw = pt.raw
    if pt.basis == "time" and pt.record in (1, 2) and "bit_depth" not in mapping:
        col = next((n for c, n in list(zip(pt.curves, raw.columns))[1:] if _norm(c.mnem) == "DEPTH"
                    and n not in mapping.values()), None)
        if col is not None:
            mapping["bit_depth"] = col
            pt.notes.append(("info", "Bit depth", f"kolom '{col}' dibaca sebagai bit depth (format Halliburton)"))
    df = pd.DataFrame(index=raw.index)

    if pt.basis == "time":
        df["ts"] = parse_time(pt, raw, source_tz)
        bad = float(df["ts"].isna().mean()) if len(df) else 0.0
        if bad > 0.05:
            pt.notes.append(("warn", "Waktu tidak terbaca", f"{bad:.0%} baris tanpa waktu valid (dibuang). Cek format kolom waktu."))
    else:
        dcol = raw.columns[0]
        df["md"] = _to_num(raw[dcol]) * _unit_factor("md", _unit_of(pt, raw, dcol))

    for canon, col in mapping.items():
        if canon == "md" and pt.basis == "depth":
            # indeks DEPTH utama; kolom MD (MDPPFG/DSVM) hanya cadangan bila indeks kosong
            df["md"] = df["md"].fillna(_to_num(raw[col]))
            continue
        if canon in {"formation", "remark"}:
            v = raw[col].astype(str).str.strip()
            df[canon] = v.where(~v.isin(NULLS), None)
        else:
            unit = _unit_of(pt, raw, col)
            fac = _unit_factor(canon, unit)
            df[canon] = _to_num(raw[col]) * fac
            if fac != 1.0:
                pt.notes.append(("info", f"Satuan {canon}", f"{unit} → satuan lapangan (×{fac:g})"))

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
        if "ecd" in df and "anp" in df:
            # Navita BDSI 60 (11–14 Nov, 12-1/4"): kanal ECD berisi tekanan annulus (psi) & ANNPRESS berisi ECD (ppg)
            swap = (df["ecd"] > 30) & df["anp"].between(6, 20)
            if swap.any():
                df.loc[swap, ["ecd", "anp"]] = df.loc[swap, ["anp", "ecd"]].to_numpy()
                pt.notes.append(("warn", "Kanal ECD/ANP tertukar", f"{int(swap.sum())} baris: ECD berisi tekanan (psi) dan "
                                 "annular pressure berisi ppg → ditukar balik"))
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
            if len(df) and not df["mw"].between(6, 22).all():
                pt.notes.append(("warn", "MW di luar 6–22 ppg", "cek satuan kolom MW (ppg; SG / g/cm³ / kg/m³ dikonversi bila satuannya tertulis)"))
        df = df.drop_duplicates("md").sort_values("md")
    elif pt.record == 7:
        if "md" in mapping:  # survey: MD stasiun (DSVM) lebih tepat daripada indeks
            alt = _to_num(raw[mapping["md"]]) * _unit_factor("md", _unit_of(pt, raw, mapping["md"]))
            df["md"] = alt.fillna(df["md"])
        # Baris proyeksi ("Projected to TD", "Proj to 8.5in CP", "Proj. to TD"): proyeksi di bit (stasiun terdalam file)
        # DIPERTAHANKAN untuk TVD/inklinasi di bit (ECD ⓥ) — klien 28 Nov; tergantikan otomatis saat survey baru di-upload
        # (upload survey mengganti seluruh survey sumur). Proyeksi yang sudah dilewati stasiun asli dibuang.
        for col in raw.columns:
            if _norm(col) in COMMENT_HEADERS or col == raw.columns[0]:
                v = raw[col].astype(str)
                proj = v.str.match(PROJ_RE) & df.index.isin(raw.index)
                if not proj.any():
                    continue
                deepest = df["md"].max()
                at_bit = proj & (df["md"] >= deepest)
                drop = proj & ~at_bit
                if at_bit.any():
                    pt.notes.append(("info", "Proyeksi di bit dipertahankan",
                                     f"MD {deepest:g} ft ({v[at_bit].iloc[0].strip()[:30]}): bukan survey official, "
                                     "tergantikan saat survey berikutnya di-upload"))
                if drop.any():
                    pt.notes.append(("info", "Proyeksi dibuang", f"{int(drop.sum())} baris proyeksi di atas stasiun asli: "
                                     + ", ".join(sorted({x.strip()[:30] for x in v[drop]}))))
                    df = df.drop(index=raw.index[drop], errors="ignore")
        df = df.dropna(subset=["md"]).drop_duplicates("md").sort_values("md")
        df = complete_survey(df, pt.notes)

    pt.data = df.reset_index(drop=True)
    pt.mapped = {k: next((c.mnem for c, n in zip(pt.curves, raw.columns) if n == v), v) for k, v in mapping.items()}
    used = set(mapping.values()) | {raw.columns[0]}
    pt.unmapped = sorted({c.mnem for c, n in zip(pt.curves, raw.columns)
                          if n not in used and c.mnem.upper() not in SKIP_UNMAPPED and not c.mnem.upper().startswith("SPARE")})
    return pt
