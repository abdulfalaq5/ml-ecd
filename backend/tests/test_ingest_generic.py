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


# ---- format asli dari contoh klien 28 Nov (isi dipendekkan & disamarkan)

def test_halliburton_survey_report_csv_with_title_block():
    csv = (b"\n,Survey Report\n\n,Report Date:,17-Nov-2025 ,,,,Survey Calc Method:,Minimum Curvature\n"
           b",Client:,X,,,,DLS:,LUBINSKI,\n,Well:,W-1,,,,TVD Reference Datum:,RTe\n\n\n"
           b"Comments,MD,Inc,Azi,TVD,TVDSS,DLS,BUILD,WALK,LATITUDE\n\n"
           b"-,   ft   ,(deg),(deg),   ft   ,   ft   ,   ft   ,(deg), 100ft) ,DD:MM:SS\n\n"
           b"Tie-in,1732.80,42.49,149.31,1589.34,1385.34,0.00,0.00,0.00,1\xb0 16' N\n"
           b"Proj to 12.25in CP,1800.00,42.70,151.00,1640.00,1436.00,0.00,0.00,0.00,1\xb0 16' N\n"
           b"    ,1825.40,42.87,153.59,1657.43,1453.43,3.16,0.41,4.62,1\xb0 16' N\n"
           b"Last survey; CtC = 20.1 ft,1889.30,44.31,157.49,1703.72,1499.72,4.77,2.25,6.10,1\xb0 16' N\n"
           b"Projected to TD Well; CtC = 10.2 ft,1950.00,44.31,157.49,1747.10,1543.10,0.00,0.00,0.00,1\xb0 16' N\n")
    pt = load("W-1_12.25in HS_MWD Survey.txt.csv", csv)
    assert pt.record == 7
    d = pt.data
    assert list(d["md"]) == [1732.8, 1825.4, 1889.3, 1950.0]   # proyeksi lama dibuang, proyeksi di bit dipertahankan
    assert any(n[1] == "Proyeksi dibuang" for n in pt.notes)
    assert any(n[1] == "Proyeksi di bit dipertahankan" for n in pt.notes)
    assert d["tvd"].iloc[0] == pytest.approx(1589.34) and d["dls"].iloc[2] == pytest.approx(4.77)


def test_slb_survey_excel_report_header_multiline_cells():
    meta = [["[W-1] (Non-Def Survey)", None, None], ["Report Date:", "September 16, 2026", "Survey / DLS Computation:"],
            ["Well:", "W-1", "TVD Reference Datum:"], ["Version / Patch:", "2.10.839.0", "Total Corr Mag North->Grid North:"]]
    rows = [["Comments", "MD\n(ft)", "Incl\n(°)", "Azim Grid\n(°)", "TVD\n(ft)", "NS\n(N/S ft)", "DLS\n(°/100ft)"],
            ["Tie-In", 0, 0, 0, 0, "N 0.00", "N/A"], [None, 153.08, 0.83, 160.99, 153.075, "S 0.92", 0.619],
            [None, 211.48, 0.82, 164.1, 211.469, "S 1.72", 0.079], ["Proj. to TD", 300, 0.82, 164.1, 300.0, "S 2.0", 0],
            [None], ["Survey Type:", None, None]]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as xw:
        pd.DataFrame(meta + [[None]] + rows).to_excel(xw, sheet_name="Survey", header=False, index=False)
    pt = load("W-1_8.5in Survey GeodeticReport.xlsx", buf.getvalue())
    assert pt.record == 7 and pt.mapped["azi"].startswith("Azim Grid")
    assert list(pt.data["md"]) == [0, 153.08, 211.48, 300] and pt.data["inc"].iloc[1] == pytest.approx(0.83)


def test_halliburton_time_based_csv_and_las_names_with_spaces():
    cols = ("Time(unitless),Block Position(ft),Hole Depth(ft),Depth(ft),Hookload(klbm),Torque(ft.lbf),"
            "SPP(psig),Flowrate(galUS/min),PWD Annular Pressure(psig),PWD Ann Press - EMW(lbm/galUS)\n")
    csv = (cols + "2026-11-28T05:41:24.19+07:00,59.3,3643.6,3643.6,,,,,,\n"
                  "2026-11-28T05:41:28.51+07:00,,,,111.2,5102.8,,591.2,,\n"
                  "2026-11-28T05:41:30.00+07:00,40.0,3643.6,3624.3,,,2133.9,,2019.2,10.87\n").encode()
    pt = load("pasopati_W-1_28_Nov_26.csv", csv, tz="UTC")       # offset +07:00 menang atas pilihan UTC
    d = pt.data
    assert d["ts"].iloc[0] == pd.Timestamp("2026-11-27 22:41:24.19", tz="UTC")
    assert {"bit_depth", "hole_depth", "flow_in", "ecd", "anp"} <= set(pt.mapped)
    assert d["bit_depth"].iloc[-1] == pytest.approx(3624.3) and d["ecd"].iloc[-1] == pytest.approx(10.87)
    assert d["torque"].iloc[1] == pytest.approx(5.1028)            # ft.lbf → kft·lb
    las = ("~Version Information\n VERS. 2.0 :\n WRAP. NO :\n~Well Information\n"
           "STRT.unitless  2026-11-28T05:43:24.23+07:00  : START DEPTH\nNULL.  -999.25 : NULL VALUE\n"
           "~Curve Information\nTime.unitless   : Time\nBlock Position.ft   : Block Position\n"
           "Hole Depth.ft   : Hole Depth\nDepth.ft  : Depth\nPWD Ann Press - EMW.lbm/galUS  : Ann Press - EMW\n~A\n"
           "2026-11-28T05:43:24.23+07:00  56.95  3645.94  3645.94  -999.25\n"
           "2026-11-28T05:43:29.23+07:00  50.10  3645.94  3639.10  10.90\n")
    pt = load("pasopati_W-1.las", las.encode())
    assert pt.mapped["block_pos"] == "Block Position" and pt.mapped["ecd"] == "PWD Ann Press - EMW"
    assert pt.data["bit_depth"].iloc[-1] == pytest.approx(3639.1)


def test_slb_interact_csv_mnemonics():
    csv = (b"TIME,BPOS,SPPA,RPM,BONB,BHD,SPPA,SWOB,GS_TDTRQ\ns,ft,psi,c/min,,ft,psi,1000 lbf,1000 ft.lbf\n"
           b"2026-11-06T17:25:00,27.03,602.37,0.00,1.00,5351.25,602.37,-44.92,-999.25\n"
           b"2026-11-06T17:25:03,27.39,601.54,0.00,1.00,5351.25,601.54,-43.09,4.2\n")
    pt = load("8d50f3c.csv", csv)
    assert pt.mapped["hole_depth"] == "BHD" and pt.mapped["torque"] == "GS_TDTRQ"
    assert pt.data["ts"].iloc[0] == pd.Timestamp("2026-11-06 10:25", tz="UTC")   # tanpa offset = WIB
    assert pt.data["torque"].iloc[1] == pytest.approx(4.2)                       # 1000 ft.lbf = kft·lb


def test_swapped_ecd_and_annular_pressure_columns_fixed():
    csv = (b"TIME,BDEP,ECD,ANNPRESS\ns,ft,ppg,psi\n"
           b"2026-11-12T07:20:04,1404,664.0,9.50\n2026-11-12T07:20:34,1405,9.6,700.0\n")
    pt = load("export_ascii_record_02_x.csv", csv)
    d = pt.data
    assert list(d["ecd"]) == [9.5, 9.6] and list(d["anp"]) == [664.0, 700.0]
    assert any(n[1] == "Kanal ECD/ANP tertukar" for n in pt.notes)
