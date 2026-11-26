"""Uji parser terhadap potongan file asli (4 format). Jalankan: docker compose exec backend pytest -q"""
from pathlib import Path

import pandas as pd
import pytest

from app.ingest.parser import canonicalize, parse_bytes

FX = Path(__file__).parent / "fixtures"
# fixtures = potongan file asli klien, sengaja tidak ada di GitHub (.gitignore) -> test dilewati bila tidak ada
pytestmark = pytest.mark.skipif(not FX.is_dir(), reason="fixtures data klien tidak tersedia (tidak di-commit)")


def load(name):
    return canonicalize(parse_bytes(name, (FX / name).read_bytes()), "Asia/Jakarta")


def test_navita_rec01_time():
    pt = load("export_las_record_01_21-11-2026_120513.LAS")
    assert pt.fmt == "las-navita" and pt.record == 1 and pt.basis == "time"
    d = pt.data
    assert len(d) > 10
    assert {"ts", "bit_depth", "hookload", "spp", "flow_in"} <= set(d.columns)
    assert str(d["ts"].dt.tz) == "UTC"
    assert d["ts"].is_monotonic_increasing


def test_navita_rec02_ecd_label():
    pt = load("export_las_record_02_21-11-2026_120417.LAS")
    assert pt.record == 2
    assert "ecd" in pt.data.columns
    ecd = pt.data["ecd"].dropna()
    assert ecd.empty or ecd.between(7, 20).all()


@pytest.mark.parametrize("name", ["rig_sample.las", "rig_sample.csv"])
def test_rig_formats(name):
    pt = load(name)
    assert pt.record == 1 and pt.basis == "time"
    d = pt.data
    assert len(d) >= 20
    for c in ("bit_depth", "hookload", "torque", "spp", "flow_in"):
        assert c in d.columns, c
    # ECD = 0 pada file rig berarti tidak terukur -> NaN
    if "ecd" in d:
        assert not (d["ecd"] == 0).any()
    # dtsrv/TIME dianggap WIB -> UTC (07:45 WIB = 00:45 UTC)
    first = d["ts"].iloc[0]
    assert first.tz is not None


def test_csv_wib_to_utc():
    pt = load("rig_sample.csv")
    assert pt.data["ts"].iloc[0] == pd.Timestamp("2026-11-06 00:45:12", tz="UTC")


def test_rig_las_equals_csv():
    """LAS rig menulis 0 sebagai -999.25; hasil kanonik harus sama dengan CSV pasangannya."""
    a = load("rig_sample.las").data.set_index("ts")
    b = load("rig_sample.csv").data.set_index("ts")
    j = a.join(b, lsuffix="_las", rsuffix="_csv", how="inner")
    assert len(j) >= 20
    for c in ("flow_in", "rpm", "wob", "spp", "hookload"):
        assert (j[f"{c}_las"].fillna(-1) - j[f"{c}_csv"].fillna(-1)).abs().max() < 0.01, c


def test_rec04_uses_depth_index():
    pt = load("export_las_record_04_sample.LAS")
    assert pt.record == 4 and pt.basis == "depth"
    assert len(pt.data) > 10 and pt.data["md"].notna().all() and (pt.data["mw"] > 0).all()


def test_ascii_rec08_not_rig():
    """Rec 08 (LWD) ASCII tidak boleh terbaca sebagai Rec 01 (bug: data LWD tercampur ke data rig)."""
    pt = load("export_ascii_record_08_sample.csv")
    assert pt.record == 8


def test_ascii_rec01_compact_timestamp():
    """dtsrv ASCII = yyyymmddHHMMSS (WIB) -> UTC."""
    pt = load("export_ascii_record_01_sample.csv")
    assert pt.fmt == "csv-navita" and pt.record == 1
    assert pt.data["ts"].iloc[0] == pd.Timestamp("2026-11-04 17:00:00", tz="UTC")
    assert pt.data["bit_depth"].notna().all()


def test_empty_las_is_skipped_not_error():
    from app.ingest.parser import EmptyFile
    with pytest.raises(EmptyFile):
        load("export_las_record_03_time_empty.LAS")


def test_template_las_numeric_and_ecd():
    """Template BEKA (Rec 01 + ECD, spasi): dibaca numerik langsung, waktu digabung dari 2 token."""
    pt = load("beka_template_sample.LAS")
    assert pt.record == 1 and pt.fmt == "las-navita"
    assert pd.api.types.is_float_dtype(pt.raw["DBTM"])
    assert pt.data["ts"].iloc[0] == pd.Timestamp("2026-06-10 17:00:00", tz="UTC")
    assert "ecd" in pt.data and "flow_in" in pt.data and pt.data["flow_in"].notna().all()


def test_ascii_headers_with_units_are_mapped():
    """Header ASCII membawa satuan ('Mud Flow In (gpm)'); flow_in wajib terpetakan (fitur utama model)."""
    pt = load("export_ascii_record_01_sample.csv")
    for c in ("flow_in", "active_pit", "gain_loss", "spp", "hookload"):
        assert c in pt.mapped, c
    assert pt.mapped["flow_in"] == "Mud Flow In (gpm)"
    assert pt.mapped["flow_out_pct"] == "Mud Flow Out %"  # bukan 'Mud Flow Out (avg)' (bbl)


def test_torque_lbf_ft_converted_to_kft_lb():
    """Export Rec 01 BLSE-055 menulis TORQUE dalam lbf.ft; harus jadi kft·lb seperti file lain."""
    name = "export_las_record_01_21-11-2026_120513.LAS"
    raw = (FX / name).read_bytes()
    base = canonicalize(parse_bytes(name, raw), "Asia/Jakarta").data
    if "torque" not in base or base["torque"].dropna().empty:
        pytest.skip("fixture tanpa torque")
    txt = raw.decode("latin-1")
    import re
    m = re.search(r"^(TORQUE\s+)\.(\S+)", txt, flags=re.M)
    assert m, "kurva TORQUE tidak ada di header fixture"
    # tulis ulang satuan + nilai ×1000 di blok data tidak praktis; cukup pastikan faktor satuan diterapkan
    alt = txt[:m.start(2)] + "lbf.ft" + txt[m.end(2):]
    conv = canonicalize(parse_bytes(name, alt.encode("latin-1")), "Asia/Jakarta").data
    pd.testing.assert_series_equal(conv["torque"], base["torque"] * 1e-3, check_names=False)


def test_unit_factor_table():
    from app.ingest.parser import _unit_factor
    assert _unit_factor("torque", "lbf.ft") == 1e-3 and _unit_factor("torque", "ft-lbf") == 1e-3
    assert _unit_factor("torque", "kft.lb") == 1.0 and _unit_factor("torque", "klbf.ft") == 1.0
    assert _unit_factor("wob", "lbf.ft") == 1.0
