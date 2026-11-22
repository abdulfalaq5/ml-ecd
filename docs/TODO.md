# TODO — Sistem ECD ML (implementasi Proposal PHR Bab 1–12)

> **Acuan utama:** *Technical Proposal PHR — ML-Based Real-Time ECD Prediction, Bab 1–12* (20 Nov 2026). Penanda [PHR x.y] = bagian proposal.
> Struktur TODO mengikuti **roadmap Fase 0–5 bergerbang** [PHR Bab 10] dan **fase kapabilitas K1–K5** [PHR 4.6A].
> Semua komponen berjalan di **Docker** (`docker compose up`).
> **Update 21 Nov 2026 (v3.0):** seluruh dokumen diselaraskan dengan proposal PHR. Rincian perubahannya ada di desain, tabel "Penyesuaian v3.0".

---

## 0. Status & Prioritas Sekarang

> **Tahap sekarang: pembangunan sistem v0.1 (21 Nov 2026).** Dokumen sudah dipindah ke `docs/`. Pembangunan dimulai atas permintaan user.
>
> **Status implementasi v0.1** (cara jalan: [`SETUP.md`](SETUP.md))
> - [x] Docker Compose: `db` (TimescaleDB pg16), `backend` (FastAPI + ML), `frontend` (React + nginx), opsional `jupyter`
> - [x] Ingest 4 format (Navita LAS/CSV, rig LAS/CSV, zip): upload, folder pantau `data/inbox/<sumur>/`, CLI `python -m app.cli import`
> - [x] QC per file, kelengkapan 5 record, timeline cakupan, QC sign-off
> - [x] PPFG berversi (draft → approved, koreksi lewat salinan); MW effective-from hole depth; survey → TVD/inc
> - [x] Operating state (DRILL_ROT/SLIDE/REAM/WASH/CIRC/TRIP/STATIC), fitur permukaan saja
> - [x] Training A–D (MW-only, persistence, RF, XGB, LGBM): LOWO + blind tetap, metrik lengkap + CI bootstrap per sumur, per state + CLEAN-OUT, promotion gate 6/6, shadow/production/rollback
> - [x] Margin bit & open hole, alert NORMAL…CRITICAL/UNAVAILABLE + low confidence
> - [x] Detektor: pack-off, torque, overpull, tag, **lonjakan ECD ⓥ**, residual, loss, influx, differential, MW statis; mode cut-off + lead time
> - [x] 11 halaman UI sesuai mockup, login lokal + peran + audit log, laporan (Excel/cetak, narasi AI opsional)
> - [x] Backup/restore + tutorial migrasi server
> - [x] Uji ingest GW339 (17 file: Rec 01/02 time+depth, 03, 04, 07) dan PDSI 53.2 (LAS rig): semua OK
> - [x] Temuan: LAS rig menulis 0 sebagai -999.25 (identik dengan CSV pasangannya) → parser mengisi 0 untuk channel operasional
> - [ ] **Tanya klien:** file GW339 `export_las_record_02_20-11-2026_110648` (Rec 02 depth) ber-WID `P_BLSE27_0003HW_MSF`, bukan GW-339. File salah folder atau label Navita?
> - [x] **Ingest 9 sumur training (22 Nov 2026)**: ACS26, BDSI 18/19/21/61, BEKA-253/254/255, GW336 — 94 file. BEKA hanya file LAS (CSV identik); Rec 08 dilewati (opsional).
> - [x] **Training ecd-rf v1 (candidate)**, train 5 sumur berlabel, uji blind = GW339 (sumur case, interval ber-PWD). Model dipilih dari LOWO, blind hanya dilaporkan.
>
>   | Eksperimen | MAE LOWO (ppg) | MAE blind GW339 | ±0,1 ppg (blind) |
>   |---|---|---|---|
>   | A · MW-only | 0,289 | 0,429 | 8 % |
>   | **B · RF (terpilih)** | **0,263** | 0,333 | 16 % |
>   | C · XGBoost | 0,319 | 0,316 | 16 % |
>   | D · LightGBM | 0,267 | 0,313 | 14 % |
>   | A · Persistence (pakai ECD terukur sebelumnya, pembanding saja) | 0,026 | 0,130 | 67 % |
>
>   LOWO per sumur (RF): ACS26 0,22 · BDSI 61 0,24 · BDSI 19 0,31 · BDSI 21 0,37 · BDSI 18 0,47. Interval 90 % ≈ −0,48…+0,52 ppg (residual LOWO). RF vs LGBM berbeda di bawah noise seed (±0,02–0,03).
> - [x] Perbaikan hasil pengujian 22 Nov (26 test lulus: `docker compose exec backend pytest -q`):
>   - parser: file 400 MB memakan RAM 4,2 GB → 1,5 GB (baca numerik langsung, per potongan)
>   - parser: Rec 08 ASCII sempat terbaca Rec 01 (data LWD tercampur ke data rig BDSI 19) → deteksi record dari nama file
>   - parser: header ASCII bersatuan (`Mud Flow In (gpm)`) tidak terpetakan → flow-in BDSI 19/21 hilang, label ECD tidak terpakai
>   - parser: file kosong (hanya header) dilewati dengan pesan jelas; Rec 03 basis waktu tidak lagi membuat versi PPFG
>   - ML: target ΔECD = ECD − MW (pohon tidak bisa ekstrapolasi ECD absolut ke MW sumur lain); hyperparameter diregularisasi
>   - ML: pemilihan model dari LOWO, bukan dari sumur blind (blind = data uji); baris tanpa MW tidak dipakai training
>   - ML/alert: MW kosong → ECD ⓥ kosong dan level **UNAVAILABLE** (sebelumnya MW diisi median, level NORMAL)
>   - detektor/alert dihitung di resolusi tetap 30 dtk (sebelumnya berubah mengikuti zoom grafik; tampilan 7 hari error 500)
>   - detektor loss: flow out % kecil (2 → 1 %) tidak lagi dianggap loss; satu indikator = ADVISORY, flow out + pit = WARNING
>   - Overview 9,7 → 2,4 dtk (query rentang waktu lewat primary key)
> - [x] PDSI 53.2: MW 10,2 ppg dimasukkan manual dari laporan stuck PHR (slide 14), file `data/inbox/PDSI 53.2/MW_manual_laporan_stuck_record_04.csv`. Cut-off 12:00 7 Nov: ECD ⓥ 10,8–11,2 ppg, Tag/set-down berulang 3.750–3.830 ft (sesuai kronologi "got tag 8 klbs").
> - [ ] **Data yang perlu diminta ke klien:**
>   - BEKA-253/254/255: **Rec 04 (MW)**. Ada ±22.800 titik ECD terukur, tetapi tidak bisa dipakai training tanpa MW.
>   - GW336: semua file **Rec 01/02 basis waktu kosong** (hanya header). Perlu download ulang.
>   - BDSI 61 Rec 02 10–16 Nov, ACS26 Rec 02 11–14 Nov, Rec 03 basis waktu BDSI 18/61: file kosong.
>   - BDSI 61: tidak ada Rec 07 (survey); TVD dari kanal rig, inklinasi kosong.
>   - BDSI 60 (blind tetap) belum ada. PDF BEKA-255 berlabel "BDSI-60_BEKA-255": konfirmasi apakah BDSI 60 = rig, dan sumur blind mana yang dimaksud.
> - [ ] Ingest BDSI 60 (blind tetap) lalu training ulang; isi gate review/shadow/threshold/rollback
> - [ ] Kalibrasi ambang detektor bersama klien (GW339 19–20 Nov: WARNING ±750 mnt dari 2.770 mnt data; pack-off & tag paling sering)
> - [ ] Approve PPFG GW339 v1 (Geomechanics) + isi shoe MD tiap sumur agar margin keluar
> - [ ] Baseline hidraulik (tunggu A14), E LSTM, F hybrid, SHAP, drift monitor

Klien meminta fokus pada **2 kasus** sebelum analisa real-time awal Desember 2026. Sesuai [PHR 12.3], keduanya dikerjakan sebagai **studi retrospektif offline di Fase 2** setelah data readiness. Classifier stuck pipe **tidak** dibangun sebelum label cukup.

| Kasus | Sifat | Pertanyaan | Data |
|---|---|---|---|
| **PDSI 53.2 · BLSE-57 HW MSF** | past (stuck 7 Nov 14:50 @5.051 ft) | dengan cut-off 12:00 7 Nov, apakah indikasi abnormal terlihat, dan **sejak jam berapa**? | 1 LAS + CSV (6 Nov 07:45 – 10 Nov), **tanpa ECD**, TVD = 0; laporan PPTX + foto cutting |
| **GW339 · BLSE-056** | present (sloughing / partial pack-off cleanout 6-1/8") | apakah sistem mengenali perubahan risiko sebelum gangguan teridentifikasi? | Rec 01/02 time (27 Okt – 20 Nov) + depth, Rec 03/04/07, file harian 20 Nov (**ECD kosong**); Proposal GW339 |

Urutan kerja setelah gate Fase 0:
- [ ] **P1 (Fase 1)** Data readiness 5 record untuk 9 sumur training + 2 sumur uji: ingest, data dictionary, QC report, time–depth alignment, operating state, katalog event awal.
- [ ] **P2 (Fase 2)** Baseline MW-only (+ hidraulik bila reologi tersedia) + RF/XGB/LGBM, grouped CV per sumur + blind tetap. Hasilnya dipakai sebagai ECD ⓥ untuk PDSI 53.2, GW337, dan GW339 run 6-1/8".
- [ ] **P3 (Fase 2, K4 offline)** Studi kasus PDSI 53.2: katalog event, cut-off 12:00, indikator + risk score, lead time & false alarm/hari.
- [ ] **P4 (Fase 2, K4 offline)** Studi kasus GW339 mengikuti Proposal GW339 (desain Lampiran D.2): data ≥ 24–48 j sebelum indikasi pertama s.d. POOH; baseline hidraulik vs residual ML vs anomali multivariat; uji sensitivitas MW hanya setelah reologi/PPFG tervalidasi.
- [ ] **P5 (Fase 2 → 3)** Dashboard minimum untuk shadow: Live Monitor, Data & Upload, Formasi & FG, Riwayat Event, Analisis Anomali (+ Login, Overview).
- [ ] **P6 (Fase 2)** Laporan + slide studi kasus 53.2 & GW339 (narasi AI, dikonfirmasi klien/koordinator).

---

### 0.000 Audit analisis & ML (22 Nov 2026)

- **Bug diperbaiki:** MW (effective-from hole depth) memakai `cummax()` polos → satu spike hole depth mengunci MW terlalu tinggi.
  GW339: spike 635→3634 ft (29 Okt, sesudah data kosong 22,6 jam) membuat MW 10.0 (seharusnya 8.9/9.7) pada 8.521 baris / 760 titik berlabel.
  Diganti `hole_reached_robust()` (kenaikan ≤ 200 ft + 1000 ft/jam × jeda, maks ±300 ft; lebih besar butuh 10 sampel konfirmasi). Test: `tests/test_hole_reached.py`.
  Sumur training tidak terdampak (0 titik berlabel berubah) → model ecd-rf v1 tidak perlu dilatih ulang.
- Angka blind GW339 dengan MW benar: MAE 0,364 / bias −0,206 / cakupan interval 66% (catatan model tersimpan masih 0,337 sampai training ulang berikutnya).
- Tidak ada look-ahead di detektor; ECD terukur tidak dipakai sebagai fitur; LOWO grouped per sumur; prediksi 100% saat pompa hidup, 0 saat pompa mati.
- Tetap terbuka: interval terlalu sempit di sumur blind (31–66% vs target 90%); bias BDSI 60; MW BEKA-253/254/255 belum ada; hole depth GW339 14–16 Nov naik ke 9909 ft (kemungkinan glitch tracking depth, tidak memengaruhi MW).

## 0.00 Studi Kasus Rathole GW339 (usulan klien 22 Nov 2026) — DONE v1
- Sumber: DDR GW-339 #38 (11 Nov) & #39 (12 Nov Rev 1). Casing 7" di-set lebih awal di 5354 ftMD (tag 5330–5351 saat RIH), TD 8-1/2" 5651 → rathole ±297 ft; CIP 12 Nov 19:30 WIB. 6 event dari DDR dicatat (status Draft → perlu dikonfirmasi Drilling Eng).
- Fitur: field `rathole` per sumur (Data & Upload → Edit sumur), tanda zona di setiap indikasi (Live Monitor / Analisis Anomali), arsir rathole di Profil Depth, halaman **K · Studi Kasus Rathole** (fase 1 validasi ECD ⓥ vs APWD, fase 2 tren harian di zona rathole), jenis laporan `rathole` (Excel 6 sheet).
- Hasil awal: fase 1 (GW339 blind) MAE 0.337 ppg, bias −0.16; di kedalaman rathole bias −0.44 (ECD−MW naik ke ±1.1 ppg). Fase 2: SPP/100 gpm 391→498→550→743 (17–20 Nov), 16/17 torque spike & 27/47 pack-off di zona rathole; ECD ⓥ datar ±10.95 → model belum menangkap efek lubang 6-1/8"/restriksi.
- Perlu dari klien: DDR 13–20 Nov, MW aktual (DDR 10.4 vs Rec 04 10.3), approval PPFG GW339, data run 6-1/8" ber-PWD sumur lain (agar ukuran lubang bisa jadi fitur model).
- Backlog: parser otomatis PDF DDR (time log → event), fitur ukuran lubang di model.

### 0.0 Retraining 22 Nov 2026 (data `data/Model Training ECD`, data lama dihapus; backup `backups/20261122_073117`)
- Re-import 10 sumur dari folder (read-only). `MANGGA 0004` = ACS26 (header `ACS-26/MANGGA-04`); **BDSI 60 = sumur BEKA-256 di rig BDSI-60**, sumur blind tetap. GW339 & PDSI 53.2 (studi kasus) dipertahankan. BEKA: hanya LAS (CSV template = data sama).
- Model `ecd v1` RF (id 5, candidate), dipilih dari LOWO. Train berlabel: ACS26, BDSI 18/19/21/61. Blind: BDSI 60 + GW339.

| Model | MAE LOWO | Blind GW339 | Blind BDSI 60 |
|---|---|---|---|
| MW-only (a+b·MW) | 0.289 | 0.429 | 0.588 |
| **RF (dipakai)** | **0.236** | **0.337** | **0.538** |
| XGB | 0.345 | 0.317 | 0.586 |
| LGBM | 0.269 | 0.308 | 0.535 |

- BDSI 60: ΔECD (ECD−MW) terukur hanya +0.12 ppg (sumur training ±0.6) → semua model over-predict ±0.5 ppg; 19 Nov ECD median < MW (−0.24) → **tanya klien** (MW Rec 04 vs MW aktual / kalibrasi tool).
- Cakupan interval 90% di sumur blind baru 69% (GW339) & 31% (BDSI 60) → interval dari residual LOWO terlalu sempit untuk sumur baru; perlu lebih banyak sumur berlabel sebelum shadow.
- Masih tanpa prediksi (UNAVAILABLE): BEKA-253/254/255 (belum ada Rec 04 MW; BEKA-254 punya 19 rb titik ECD yang belum terpakai), GW336 (file time kosong).

## 1. Roadmap Bergerbang [PHR Bab 10] — ringkas

| Fase | Aktivitas | Gate | Deliverables [PHR 10.1] | Waktu (usulan) |
|---|---|---|---|---|
| **0 Scoping** | owner, akses data, daftar sumur, KPI, use case, persetujuan dokumen | ☐ Scope approved | dokumen desain disetujui, daftar keputusan [PHR 12.2] | Nov 2026 (sekarang) |
| **1 Data readiness** | record mapping, QC, time–depth alignment | ☐ Data QC sign-off | source-to-target mapping, data dictionary, QC report, readiness matrix, missingness map | akhir Nov |
| **2 Offline modeling** | baselines, RF/XGB/LGBM, blind-well, margin PPFG, studi kasus offline | ☐ Model performance reviewed | EDA report, model registry, validation pack, laporan studi kasus | akhir Nov – awal Des |
| **3 Shadow mode** | inferensi live tanpa tindakan (GW339, GW337) | ☐ Alarm/latency/quality acceptable | dashboard config, event taxonomy, log alarm/latency, feedback | awal Des (setelah gate 2) |
| **4 Controlled pilot** | alert dibantu RTO engineer | ☐ Pilot review & HSE approval | SOP/response guide, pilot report | menyusul |
| **5 Scale-up** | lebih banyak rig/section, drift, governance | ☐ Production change approval | handover package | menyusul |

**Prinsip yang mengikat semua fase:**
1. **Produk utama = nowcast ECD.** Forecast 5–15 mnt adalah fase terpisah [PHR 5.1].
2. **Surface-only input contract.** ECD/ANP/PWD hanya target [PHR 4.1, 7.3].
3. **PPFG layer terpisah & berversi (approved)**, tidak dicampur dengan label. Perubahan PPFG **bukan** pemicu retraining [PHR 4.2A, 7.4].
4. **No look-ahead leakage** [PHR 5.4]. Mode cut-off memakai aturan yang sama.
5. **Grouped per sumur + blind-well.** Tidak ada random split per baris [PHR 2.5, 5.7].
6. **Advisory tool.** Output membawa model version, completeness, quality, dan versi PPFG. Saat input invalid → *unavailable/low confidence* [PHR 4.6].
7. **Stuck pipe = engine terpisah (H4).** Dimulai dari rules + anomaly scoring offline, lalu shadow [PHR 8.3, 12.3].

---

## 2. Temuan dari Data, Dokumen & Chat Klien

### 2.1 Data source register [PHR 5.3]
| Rec | Isi | Basis | Status |
|---|---|---|---|
| 01 IDS Rig | depth, block, ROP, hookload, WOB, torque, RPM, SPP, flow in, flow out %, pit, gain/loss, SPM | Time & Depth | ✅ 9 + 2 sumur |
| 02 MWD/PWD | ECD, ANP, TVD, mud density, temperatur, inc/azi kontinu | Time & Depth | ✅ (tanpa ECD di GW337, PDSI 53.2, GW339 6-1/8") |
| 03 PPFG | PP, SFG, FG Min/Max, SHMax, OBG, Formation | Depth | ✅ (perlu status approved) |
| 04 Mud Weight | MUDWEIGHT, REMARK | Depth | ✅ (aturan effective-from perlu disetujui) |
| 07 Survey | MD, TVD, inc, azi, DLS | Depth | ✅ (kecuali Gula010, PDSI 53.2) |
| 08 LWD | ECD, caliper (BDSI 18/19) | Time & Depth | **opsional**, di luar 5 record proposal |
| 05, 06 | — | — | tidak diasumsikan ada |

### 2.2 Inventaris data di folder
| Folder / file | Sumur | Isi | Catatan |
|---|---|---|---|
| `Model Training ECD/bdsi 61 Gula0010` | BDSI-61 / GULAMO010 | Rec 01, 02, 03, 04 | Rec 01 time ±300 MB/minggu |
| `…/BDSI 18 MINA26 0017 HZ (5D-83A)` | BDSI-18 | Rec 01, 02, 03, 04, 07, (08) | horizontal |
| `…/BDSI 19 MINA 02222 HZ (3D-49D)` | BDSI-19 | Rec 01, 02, 03, 04, 07, (08) | horizontal |
| `…/BDSI 21 MINAS 2218 (6D-95A)` | BDSI-21 | Rec 01, 02, 03, 04, 07 | |
| `…/GW336 MUTI25 001 OPT` | GW336 | Rec 01, 02, 03, 04, 07 | 10–26 Okt |
| `…/MANGGA 0004 (O-O-44 A)` | ACS26 | Rec 01, 02, 03, 04, 07 | usulan blind tetap |
| `…/BEKA-253, 254, 255` | BEKA | template gabungan Rec 01 + ECD, 12.25" & 8.5" | Jun–Okt 2026 |
| `Sumur Uji Berjalan/GW339 BLSE0056` | GW339 | Rec 01, 02, 03, 04, 07 | studi kasus present |
| `export_las_record_01/02_21-11-2026_*.LAS` (root) | GW-339 / BLSE-056 | Rec 01 & 02 tanggal 20 Nov | **ECD kosong**; usul dipindah ke folder GW339 (menunggu konfirmasi) |
| `Sumur Uji Berjalan/PDSI 53.2` | BLSE-57 | 1 LAS + 1 CSV (~1 mnt) | **tanpa ECD**; kasus stuck |
| `12.25in section`, `8.5in Section` | Gula010 (export lama) | custom 20 channel | digantikan full record |

### 2.3 Temuan QC (detail di desain Bab 6.2 & `CHANNELS.md` §8–10)
- [x] ~~MW kosong di Rec 02~~ → MW dari **Rec 04**.
- [x] ~~TVA/GL/MFOP tidak ada~~ → ada di full Record 01.
- [x] ~~Tabel FG belum ada~~ → **Rec 03**. Kolom `FORMATION` Gula010 kosong → perlu formation tops.
- [ ] Outlier ECD 0,98–157 ppg → flag + review log, tidak dibuang otomatis [PHR 6.2].
- [ ] `Date/Time` rig vs `dtsrv` ±7 jam → normalisasi UTC, tampil WIB.
- [ ] Depth `.m` = ft; null `-999.25`; `WID` salah (`Kopar-52`, `P_BLSE27_0003HW_MSF`).
- [ ] PDSI 53.2: mnemonic berbeda, ±1 mnt, ECD = 0, TVD = 0 → alias + TVD survey.
- [ ] GW339 20 Nov: sampling 1–14 dtk, gap 04:17–06:01, `ACTC` = 0, tank bernama rig, 2 `SPARE`, SPP/WOB negatif di Rec 02.

### 2.4 Proposal PHR → keputusan yang mengikat (ringkas)
| Bagian | Keputusan |
|---|---|
| 1.2, 5.3 | lima record inti; Rec 08 opsional |
| 2.2, 8.1 | margin di bit **dan** open-hole exposed interval, dengan uncertainty; FG approved |
| 2.4, 5.1 | label = ECD PWD terukur lolos QC; tidak pernah dari hydraulic baseline |
| 4.2 | Layer A–E; raw tables + time table + depth table; as-of join |
| 4.3, 9.2 | enam dashboard + kontrol production |
| 4.4 | PHR-H1..H4 (GW339: GW-H1..H4) |
| 4.5, 5.7 | lima tahap validasi; metrik MAE/RMSE/R²/P90/P95/bias/kalibrasi; CI grouped bootstrap |
| 5.5 | baseline wajib MW-only, hidraulik, persistence; hybrid residual |
| 6.3 | sinkronisasi 7 langkah; measurement/transmission/ingestion time |
| 7.1 | eksperimen A–F; laporan per section 12.25"/8.5" |
| 7.4 | promotion gate; retrain karena drift/mud/section, bukan karena PPFG |
| 8.4 | Advisory/Warning/Critical; rekomendasi verifikasi; tanpa perintah otomatis |
| 10.2 | tujuh peran + approval |

### 2.5 Masukan klien (chat) → keputusan (semua sesuai proposal, lihat desain Lampiran F.2)
- [x] Sloughing: pumps off → MW statis vs batas bawah; pumps on → mekanis (torque/drag/SPP).
- [x] "Pre-drill" diganti evaluasi MW (istilah klien "MWW") → Profil Depth. Output berupa **rekomendasi verifikasi**.
- [x] FG Min dari model reservoir saat drilling → Rec 03 berversi + approval.
- [x] Tampilan ala template Navita (multi-channel satu sumbu, skala bisa diatur, picker), log format + kolom ALERT.
- [x] Flow out, tank volume, gain/loss → loss/influx warning [PHR 8.2].
- [x] Analisis mundur dengan cut-off tanpa menghapus file → no look-ahead.
- [x] Output "sejak jam berapa" → risk score + onset per indikator (modul H4).
- [x] Laporan + presentasi dibantu AI → halaman Laporan (AI eksternal disetujui 21 Nov).
- [x] Room tidak dibatasi → Overview.
- [x] Ekspektasi "≈100 %" → blind-well dijelaskan.
- [x] Login akun lokal (21 Nov).

---

## 3. Fase 1 — Data Readiness (K1) · gate: Data QC sign-off

### 3.1 Setup
- [ ] Struktur proyek:
  ```
  ecd/
  ├── data/raw/              # zip asli Navita (read-only)
  ├── data/processed/        # parquet per sumur/record
  ├── config/mnemonics.yaml  # data dictionary + alias (CHANNELS.md §0, §9)
  ├── services/{etl,ml,anomaly,api,dashboard,report}/
  ├── notebooks/             # EDA & studi kasus
  ├── docker-compose.yml · Makefile · .env
  ```
- [ ] Service: `db` (PostgreSQL + TimescaleDB + Parquet), `etl`, `ml`, `anomaly`, `mlflow`, `api`, `dashboard`, `report`, `jupyter`.

### 3.2 Layer A — Data acquisition [PHR 4.2]
- [ ] Ingest **zip** → LAS (lasio, streaming) & CSV; deteksi record (header + nama file) & basis time/depth.
- [ ] **Raw tables per record** disimpan apa adanya, dengan provenance (file, waktu ingest, source timestamp, depth reference).
- [ ] Rec 05/06/08 disimpan mentah. Rec 08 hanya dipakai bila disetujui.
- [ ] Upload inkremental (dedup overlap), folder dipantau.

### 3.3 Layer B — Data assurance [PHR 4.2, 6.1–6.3]
- [ ] **Data dictionary** di `config/mnemonics.yaml`: canonical name, original tag, unit, sensor origin, sampling, time zone, missing convention, range, valid section, owner.
- [ ] Mapping eksplisit (tanpa tebak nama); alias Navita / BEKA / PDSI 53.2 / tank GW339.
- [ ] QC berlapis: schema, unit, duplicate, frozen sensor, impossible jump, gap, drift, outlier fisik, cross-sensor. Clipping di-fit pada training saja.
- [ ] Sinkronisasi 7 langkah [PHR 6.3]: ID & unit → event time UTC → bit/hole depth & TVD survey → clock offset rig–MWD (cross-corr) → as-of join ±15 dtk → mapping Rec 03/04/07 per depth & versi → audit mismatch.
- [ ] Bedakan measurement / transmission / ingestion time.
- [ ] Resample ke grid tetap. Gap diberi flag, tidak diinterpolasi melewati batas.
- [ ] **Operating state**: drilling rotary, sliding, reaming, sirkulasi, connection, TIH, TOH, pumps off (dari `ACTC` bila terisi, atau dari aturan).
- [ ] Tabel kanonik: (a) time-indexed operational features, (b) depth-indexed well context.
- [ ] **Target availability** per sumur/section (coverage label ECD).

### 3.4 Layer D (awal) — PPFG & MW berversi
- [ ] `ppfg(well, md, tvd, pp, sfg, fg_min, fg_max, shmax, obg, formation, version, effective_date, approver, applicability, tvd_datum, uncertainty, status)`.
- [ ] `mud_weight(well, md, mw, remark, effective_from_rule, version)`. Aturan effective-from disetujui Mud Eng.
- [ ] Alur approval: draft → approved (Geomechanics).

### 3.5 Katalog event [PHR 4.5A]
- [ ] Skema: timestamp onset, MD, mode operasi, kategori (loss, influx, pack-off, tight hole/sloughing, differential, mechanical, stuck, noise), confidence, sumber (DDR/laporan/RTO), status review.
- [ ] Isi awal: PDSI 53.2 (dari PPTX). GW339 & 9 sumur training menunggu DDR.

### 3.6 Deliverables Fase 1
- [ ] Source-to-target mapping · data dictionary · QC report per sumur · data readiness matrix · missingness map · outlier review log · lineage diagram · **sign-off RTO**.

---

## 4. Fase 2 — Offline Modeling (K2, K3, K4 offline) · gate: Model performance reviewed

### 4.1 EDA [PHR 6.4]
- [ ] Per section & state: ECD–flow/SPP/MW/ROP/RPM; ECD vs TVD/MD + PPFG envelope + shoe + mud changes; lag/hysteresis.
- [ ] Bandingkan area (Beka, Minas, Gulamo, Balam) → perlu model per cluster?

### 4.2 Model ECD (nowcast) [PHR 5.5–5.7, 7.1–7.3]
- [ ] Fitur sesuai [PHR 5.5]; lag hanya dari masa lalu; konfigurasi **surface-only** & *sensor-enhanced* dilaporkan terpisah.
- [ ] **Eksperimen A** baseline: MW-only, persistence, hidraulik (butuh reologi/geometri; bila belum ada, tandai).
- [ ] **B** RF · **C** XGBoost · **D** LightGBM · **E** LSTM (bila time series stabil) · **F** hybrid residual.
- [ ] Grouped CV per sumur. Scaler/imputasi/feature selection di-fit per fold training. Satu sumur **blind tetap** (usulan ACS26).
- [ ] Uji ekstrapolasi **12.25" → 8.5"** [PHR 4.4].
- [ ] Metrik: MAE, RMSE, R², P90/P95, bias, kalibrasi, % dalam toleransi. Hasil per well/section/formasi/state. CI dari grouped bootstrap.
- [ ] Grafik wajib: actual vs predicted, residual by depth/flow/section, distribusi error, kalibrasi, SHAP.
- [ ] Uncertainty/prediction interval (dari residual blind per state) + detektor OOD.
- [ ] Evaluation report per sumur (desain Appendix B).
- [ ] Registry MLflow (versi data, code, hyperparams). Status Candidate → Shadow → Production.

### 4.3 Pressure window & loss/influx (K3) [PHR 8.1–8.2]
- [ ] Margin atas di bit & open-hole exposed interval (shoe → bit), margin bawah, margin statis. Ketidakpastian ditampilkan sebagai interval.
- [ ] Rule loss/influx: margin + pit + flow out−in + SPP. Nonaktif bila channel tidak ada.
- [ ] Backtest alert pada sumur historis: jumlah alert per tingkat, false alert per rig-day.

### 4.4 Modul stuck-pipe offline (K4) [PHR 8.3, 4.5A]
- [ ] Baseline per depth/state (P/U, S/O, RO, torque, SPP vs flow).
- [ ] 🆕 **Detektor lonjakan ECD ⓥ** untuk run tanpa PWD (PDSI 53.2 BHA #4): jalankan ECD ⓥ sepanjang run, tetapkan ambang x ppg / y mnt dari fluktuasi normal ECD ⓥ di sumur training, aturan abaikan (pompa baru hidup, connection, perubahan flow/MW); bandingkan dengan kronologi report PHR → lead time.
- [ ] 🆕 Minta **report stuck pipe PDSI 53.2 yang sudah dirilis PHR** (ground truth H4).
- [ ] Detektor rules + statistik (z-score robust, EWMA/CUSUM, hysteresis, durasi minimum): tag berulang, overpull, torque spike/stall, pack-off, residual ECD, differential (pipa diam), MW statis < batas bawah.
- [ ] Risk score 0–100 + onset per indikator + kategori dugaan (pack-off / differential / mechanical dievaluasi terpisah).
- [ ] **Mode cut-off** + uji otomatis: hasil tidak berubah bila data > T dihapus.
- [ ] **Studi kasus PDSI 53.2** (P3) & **GW339** (P4). Metrik: lead time vs onset terverifikasi, recall, precision, false alarm/hari.

### 4.5 Laporan studi kasus (P6)
- [ ] PDF/PPTX dengan narasi AI dari ringkasan hasil, catatan hipotesis, dan konfirmasi klien/koordinator.

---

## 5. Fase 2 → 3 — Dashboard & API (Layer E, Lapisan 5)

Sesuai [`UI_MOCKUP.md`](UI_MOCKUP.md):
- [ ] **Login akun lokal** (hash password, peran [PHR 10.2], akses per room) + audit log.
- [ ] **Overview** multi-room tanpa batas.
- [ ] **1 Live Monitor**: header atribut wajib (freshness, latency, state, model version, completeness, PPFG version), last valid vs current, degraded mode, track multi-channel ala Navita (skala per channel, preset, kunci ppg), Picker/Realtime/Latest Scroll/Show All, log format + ALERT, panel pressure window, alert card + ack.
- [ ] **2 Profil Depth**: MD/TVD, PPFG berversi, shoe/section, exposure interval, uncertainty, mode Rencana MW.
- [ ] **3 Riwayat Event**: kategori, label confidence, review workflow, evidence, audit.
- [ ] **4 Data & Upload**: kelengkapan 5 record, target availability, schema QC, clock drift, lineage, sign-off.
- [ ] **5 Formasi & FG**: versi, effective date, approver, applicability, datum, uncertainty, approve.
- [ ] **6 Model ML**: dataset & split, hasil blind per eksperimen, SHAP, promotion gate, rollback, lineage, drift.
- [ ] **Analisis Anomali** (modul H4): cut-off, baseline, risk score, indikator, verifikasi, lead time.
- [ ] **Laporan** (AI eksternal: kunci API di `.env`, bisa dimatikan, hanya ringkasan hasil dikirim).
- [ ] **Pengaturan**: ambang berversi + approval Drilling Eng & HSE, preset, user, AI, WIB.
- [ ] API: `/ingest`, `/wells`, `/timeseries`, `/predict`, `/ppfg` (+approve), `/mudweight`, `/anomaly/run?cutoff=`, `/events` (+review), `/backtest`, `/models/{id}/promote|rollback`, `/report`, `/audit`.
- [ ] Downsampling min/max per bucket; gap tidak disambung.

---

## 6. Fase 3 — Shadow Mode · gate: Alarm/latency/quality acceptable
- [ ] Live inference **tanpa tindakan operasional** di GW339, GW337 (awal Des, setelah gate Fase 2).
- [ ] Catat: latency source-to-display, data availability, alert per tingkat, false alert per rig-day, feedback engineer, adoption (ack/review).
- [ ] Monitoring error (bila ada label) & drift.
- [ ] Event taxonomy final + dashboard configuration.

## 7. Fase 4 — Controlled Pilot · gate: Pilot review & HSE approval
- [ ] Alert dibantu RTO engineer; SOP/response guide.
- [ ] Evaluasi kelayakan early warning stuck (K5): lead time & beban false alarm layak bagi RTO? [PHR 12.3]
- [ ] Pilot report: error per operating state, alert quality, data latency, feedback engineer [PHR 1.5].
- [ ] Evaluasi nilai ekonomi skenario [PHR 11.2].

## 8. Fase 5 — Scale-up · gate: Production change approval
- [ ] Lebih banyak rig/section; retraining dipicu drift / mud system / section / performa turun.
- [ ] Governance: versioning, approval, audit, rollback plan, model performance review [PHR 5.8].
- [ ] Handover package: manual pengguna (tanpa Python), manual instalasi Docker, runbook retraining.

## 9. Testing & Dokumentasi (berjalan di semua fase)
- [ ] Unit test ETL (LAS/CSV/zip, alias, null, satuan, timezone), test API, **test no look-ahead / cut-off**, test promotion gate.
- [ ] README: `docker compose up`, upload zip, tambah sumur, approve PPFG.

## 10. Backlog di luar proposal (hanya bila disetujui — desain Lampiran H C6)
- [ ] What-if (flow/RPM/ROP/MW → ECD).
- [ ] Proyeksi ECD per depth / forecast 5–15 mnt (fase terpisah setelah uji prospektif [PHR 5.1]).
- [ ] Citra cutting (SOP foto, label, CNN).
- [ ] Notifikasi WhatsApp/Telegram.

---

## 11. Yang Perlu Dikonfirmasi / Dikirim Klien

Daftar lengkap dengan usulan default ada di **desain Lampiran H**. Yang paling menentukan:
- [ ] **A14 Baseline hidraulik PHR** + reologi PV/YP, hole/casing size, BHA (baseline wajib [PHR 5.5, 12.2]).
- [ ] **A17 Provenance label ECD Rec 02** (PWD, kedalaman sensor, kalibrasi) + **A16** interval PWD per sumur.
- [ ] **A13** Rec 08 dipakai (opsional) atau tidak.
- [ ] **A10/A11** katalog event: DDR kejadian di 9 sumur training & GW339; waktu efektif MW 10,4 → 10,0.
- [ ] **A1** MW di Rec 04 · **A2** arti ACTC · **A3** formation tops · **A4–A7** pertanyaan file GW339 20 Nov · **A8** data Navita PDSI 53.2.
- [ ] **B6** tingkat alert Normal/Advisory/Warning/Critical · **B1/B12** batas bawah & margin open hole · **B11** horizon forecast · **B14** aturan effective-from MW.
- [ ] **E2/E5** target akurasi & engineering tolerance (ditetapkan PHR setelah studi data).
- [ ] **F7** nama approver tiap peran · **A15** persetujuan data owner · **G3** penyetuju dokumen.
- [ ] 🆕 **A18/A19 Clean-out run:** apakah PWD sumur training merekam saat clean-out/reaming/back-reaming; daftar run BHA tanpa ECD tool berikutnya.
- [ ] 🆕 **Audit label per state clean-out** (Fase 1): hitung jam ECD valid di sirkulasi/reaming/back-reaming/washing per sumur → menentukan apakah ECD ⓥ boleh dipakai di clean-out (desain Bab 5.1, 5.7).
- [ ] 🆕 **Data BDSI 60** (sedang di-download klien) → audit & QC → tetapkan peran: **blind tetap (usulan)** atau sumur training ke-10 (E3).
- [x] ~~Pemetaan hipotesis~~ → H4 di PDSI 53.2 (statis), H1–H3 di GW339 (dinamis, shadow) + blind-well; disepakati klien 21 Nov (desain Bab 4.4).
- [x] ~~F3 Login~~ → **akun lokal** (21 Nov).
- [x] ~~F2 AI eksternal~~ → **boleh**; hanya ringkasan hasil yang dikirim (21 Nov).
- [ ] Opsional: pindahkan 2 file LAS 20 Nov ke `Sumur Uji Berjalan/GW339 BLSE0056` (menunggu persetujuan).
