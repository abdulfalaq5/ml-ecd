"""Upload tanpa Navita: survey / MW generik (CSV & Excel), time-based gaya SLB / Halliburton, satuan metrik, waktu."""
import io

import numpy as np
import pandas as pd
import pytest

from app.ingest.parser import canonicalize, iter_files, min_curvature, parse_bytes


def load(name, content, tz="Asia/Jakarta"):
    return canonicalize(parse_bytes(name, content), tz)


def test_min_curvature_known_values():
    # vertikal: TVD = MD, DLS 0
    tvd, dls = min_curvature([0, 1000], [0, 0], [0, 0])
    assert tvd[-1] == pytest.approx(1000) and dls[-1] == 0
    # build 0→30° dalam 1000 ft dengan azimuth tetap: DLS 3°/100 ft; TVD busur = R·sin(30°), R = 1000/(π/6)
    tvd, dls = min_curvature([1000, 2000], [0, 30], [45, 45], tvd0=1000)
    assert dls[-1] == pytest.approx(3.0, abs=1e-6)
    assert tvd[-1] - 1000 == pytest.approx(1000 / (np.pi / 6) * 0.5, rel=1e-6)


def test_generic_survey_csv_metric_without_tvd():
    csv = b"MD (m),Inc (deg),Azi (deg)\n0,0,0\n304.8,0,0\n609.6,30,90\n"
    pt = load("Survey GW339.csv", csv)
    assert pt.record == 7
    d = pt.data
    assert d["md"].iloc[-1] == pytest.approx(2000, abs=0.1)          # m → ft
    assert d["tvd"].iloc[1] == pytest.approx(1000, abs=0.1) and d["dls"].iloc[-1] == pytest.approx(3.0, abs=0.01)
    assert any(n[1] == "TVD dihitung" for n in pt.notes)


def test_generic_survey_excel_with_title_rows():
    df = pd.DataFrame({"Measured Depth": [0, 500, 1000], "Inclination": [0, 2, 5], "Azimuth": [0, 120, 125], "TVD": [0, 499.9, 998.9]})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as xw:
        pd.DataFrame([["Survey report SLB"], ["Well: X"]]).to_excel(xw, header=False, index=False, startrow=0)
        df.to_excel(xw, index=False, startrow=3)
    files = list(iter_files("svy.xlsx", buf.getvalue()))
    assert len(files) == 1                                            # xlsx bukan zip berisi file
    pt = load(*files[0])
    assert pt.record == 7 and len(pt.data) == 3
    assert pt.data["tvd"].iloc[-1] == pytest.approx(998.9) and pt.data["dls"].notna().all()


def test_generic_mud_weight_table_sg():
    csv = b"Depth (ft),MW (sg),Remark\n0,1.08,spud\n3000,1.20,DDR 12 Nov\n"
    pt = load("mw_manual.csv", csv)
    assert pt.record == 4
    assert pt.data["mw"].tolist() == pytest.approx([1.08 * 8.3454, 1.20 * 8.3454])


def test_halliburton_style_date_time_columns_dayfirst_metric():
    csv = (b"Date,Time,Bit Depth,Hole Depth,Hook Load,Flow In,Standpipe Pressure,Rotary RPM,Weight on Bit\n"
           b"dd/mm/yyyy,hh:mm:ss,m,m,kN,L/min,bar,rpm,kN\n"
           b"20/11/2026,13:00:00,1000,1200,500,2000,150,80,50\n"
           b"20/11/2026,13:00:05,1000.5,1200,500,2000,150,80,50\n")
    pt = load("HAL_GW339_time.csv", csv)
    assert pt.record == 1 and pt.basis == "time"
    d = pt.data
    assert d["ts"].iloc[0] == pd.Timestamp("2026-11-20 06:00:00", tz="UTC")     # WIB → UTC
    assert d["bit_depth"].iloc[0] == pytest.approx(3280.84, abs=0.1)
    assert d["hookload"].iloc[0] == pytest.approx(112.4, abs=0.1)
    assert d["flow_in"].iloc[0] == pytest.approx(528.3, abs=0.1)
    assert d["spp"].iloc[0] == pytest.approx(2175.6, abs=0.1)


def test_slb_style_mnemonics_iso_utc_and_tz_override():
    csv = (b"TIME,BDEP,DMEA,HKLD,TFLO,SPPA,SRPM,SWOB,TQA,ECD_ARC\n"
           b"2026-11-20T06:00:00Z,5000,5200,180,450,1800,90,20,8,9.8\n"
           b"2026-11-20T06:00:05Z,5001,5200,180,450,1800,90,20,8,9.8\n")
    pt = load("slb_stream.csv", csv)
    d = pt.data
    assert {"bit_depth", "hole_depth", "hookload", "flow_in", "spp", "rpm", "wob", "torque", "ecd"} <= set(d.columns)
    assert d["ts"].iloc[0] == pd.Timestamp("2026-11-20 06:00:00", tz="UTC")
    naive = b"TIME,BDEP,DMEA\n2026-11-20 06:00:00,1,2\n2026-11-20 06:00:05,1,2\n"
    assert load("x.csv", naive, "UTC").data["ts"].iloc[0] == pd.Timestamp("2026-11-20 06:00:00", tz="UTC")
    assert load("x.csv", naive).data["ts"].iloc[0] == pd.Timestamp("2026-11-19 23:00:00", tz="UTC")


def test_ambiguous_date_flagged():
    csv = b"Date Time,Bit Depth,Hole Depth\n05/11/2026 10:00:00,1,2\n05/11/2026 10:00:05,1,2\n"
    pt = load("x.csv", csv)
    assert pt.data["ts"].iloc[0].tz_convert("Asia/Jakarta").month == 11
    assert any(n[1] == "Format tanggal ambigu" for n in pt.notes)
