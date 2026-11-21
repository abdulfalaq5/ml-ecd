# Dokumen Desain Sistem — Machine Learning-Based Real-Time ECD Prediction

**PHR Drilling Operations | Engineering & Real-Time Operations (RTO)**
**Implementasi dari *Technical Proposal PHR Bab 1–12* (Revised Technical Draft, 20 Nov 2026)**
**Studi kasus awal: GW339 / BLSE-056 (present) dan PDSI 53.2 / BLSE-57 HW MSF (past)**

| | |
|---|---|
| Jenis dokumen | Dokumen desain sistem (untuk persetujuan sebelum pengembangan) |
| Versi | **3.0** (menggantikan v2.1 dan v2.0 21 Nov, serta v1.0 19 Nov 2026) |
| Tanggal | 21 November 2026 |
| Status | **Draf final, mengikuti proposal PHR**. Dokumen difinalkan sebelum sistem dibangun dan masih menunggu persetujuan klien |
| **Acuan utama** | **`klien/PHR_Proposal_ECD_ML_Lengkap_Bab_1-12.docx`** (proposal klien). Penanda **[PHR x.y]** = nomor bagian di proposal |
| Acuan pendukung | Percakapan klien (`klien/percaakapanclient.md`), Proposal Prognosis GW339 (penanda **[GW §n]**), laporan stuck PDSI 53.2 (`klien/Hipotesis H4/`), jurnal (`referensi/`), isi data Navita |
| Dokumen terkait | `CHANNELS.md` (data dictionary, Appendix A), `UI_MOCKUP.md` (enam dashboard), `TODO.md` (roadmap Fase 0–5) |

> **Aturan acuan.** Proposal PHR Bab 1–12 adalah acuan utama dokumen ini. Masukan klien dari chat dan dokumen lain dipakai **selama tidak bertentangan** dengan proposal. Bila ada perbedaan, yang dipakai adalah proposal, dan perbedaannya dicatat di tabel "Penyesuaian v3.0" di bawah serta di **Lampiran H** (pertanyaan konfirmasi).
>
> Semua angka pada mockup dan contoh tabel adalah **ilustrasi**, bukan KPI atau hasil uji [PHR 1.5, 4.3, 7.3]. Dokumen ini **tidak mengklaim** hasil validasi lapangan PHR maupun akurasi deteksi stuck pipe [PHR status dokumen].

**Penyesuaian v3.0 terhadap proposal PHR (dibanding v2.1)**

| Topik | v2.1 | v3.0 (mengikuti proposal) | Acuan |
|---|---|---|---|
| Struktur dokumen | 17 bab versi sendiri | **Bab 1–12 + Appendix A–C sama dengan proposal**. Studi kasus, tutorial, dan pertanyaan dipindah ke lampiran D–H | seluruh |
| Sumber data inti | Rec 01, 02, 03, 04, 07, 08 | **Lima record: 01 IDS Rig, 02 MWD/PWD, 03 PPFG, 04 Mud Weight, 07 Survey**. Rec 05/06 tidak diasumsikan ada. Rec 08 (LWD) hanya **opsional** dan perlu konfirmasi | [PHR 1.2, 5.3] |
| Produk utama | nowcast + prognosis 5/15/30 mnt | **Nowcast ECD pada waktu t**. Forecast 5–15 mnt adalah fase pengembangan terpisah dan baru dilaporkan setelah uji prospektif | [PHR 5.1] |
| Stuck pipe | modul early warning (H4) jalan bersamaan dengan ECD | **Engine terpisah, scope tambahan**. Dimulai dari anomaly scoring + engineering rules secara **offline**, lalu shadow mode (Fase 4). Supervised classifier hanya dibuat bila event berlabel cukup | [PHR 1.6, 4.6A, 8.3, 12.3] |
| Tingkat status | Aman / Waspada / Anomali / Bahaya / No Data | **Normal / Advisory / Warning / Critical**, ditambah **Unavailable / Low confidence** | [PHR 4.6, 8.4] |
| Margin atas | FG Min − ECD di bit | FG_min − ECD di bit **dan di open-hole exposed interval** (shoe → bit), **dengan interval ketidakpastian** | [PHR 2.2, 8.1] |
| Margin bawah | ECD − max(PP, SFG) | dievaluasi **terhadap PP/collapse sesuai model geomekanika**. Usulan default = max(PP, SFG) dan menunggu persetujuan Geomechanics | [PHR 8.1] |
| Baseline model | MW-only, hidraulik (bila ada reologi), persistence | **Ketiganya wajib**. Baseline hidraulik menjadi syarat, jadi data reologi/geometri dan model hidraulik yang berlaku di PHR masuk kebutuhan data utama | [PHR 5.5, 12.2] |
| Validasi | LOWO, kronologis, backtest, shadow | **Lima tahap validasi** [PHR 4.5] + rolling-origin dengan embargo + CI per sumur (grouped resampling) + kinerja per section 12.25"/8.5" | [PHR 4.5, 5.7, 7.1] |
| Lead time | dilaporkan untuk semua alert | **Hanya untuk event warning** (stuck/loss) terhadap event yang dikonfirmasi engineer. **Tidak dilaporkan untuk nowcast ECD** | [PHR 4.5] |
| Target akurasi | usulan RMSE < 0,1–0,2 ppg | **Tidak ada target numerik sebelum studi distribusi data**. Target ditetapkan dan disetujui Engineering/RTO PHR | [PHR 1.5, 5.8] |
| Dashboard | 11 halaman | **Enam dashboard proposal** (Live Monitor, Profil Depth, Riwayat Event, Data & Upload, Formasi & FG, Model ML) dengan kontrol production. Halaman pendukung dari permintaan klien: Login, Overview, Analisis Anomali, Laporan, Pengaturan | [PHR 4.3, 9.2] |
| What-if, proyeksi, citra cutting | fitur sistem | **Di luar lingkup proposal**. Masuk backlog dan hanya dikerjakan bila disetujui | [PHR 1.4] |
| Saran MW | "saran MW ≥ …" | diganti **"rekomendasi verifikasi"**. Sistem tidak memberi perintah perubahan MW/flow | [PHR 8.4] |
| Peran | Driller / Engineer-RTO / Admin | **Mengikuti peran proposal**: Drilling Eng, RTO, Mud Eng, Geomechanics, Directional/MWD, Data/ML, HSE/Well Control | [PHR 10.2] |
| Roadmap | Fase 0–11 versi sendiri | **Fase 0–5 bergerbang** [PHR Bab 10] + fase kapabilitas 1–5 [PHR 4.6A] | [PHR 4.6A, 10] |

**Riwayat versi sebelumnya:** v2.1 (21 Nov) menambahkan Gambaran Sistem 1 halaman, tutorial pengguna, matriks masukan klien, pertanyaan konfirmasi, data GW339 20 Nov, serta keputusan login akun lokal dan AI eksternal. v2.0 menambahkan definisi record Navita, MWW, early sign, cut-off, tampilan ala Navita, room tanpa batas, dan integrasi Proposal GW339.

---

## Gambaran Sistem dalam 1 Halaman

**Apa yang dilakukan sistem?** Sistem membaca data Navita hasil download (.zip) dari lima record [PHR 1.2], lalu untuk setiap sumur menjawab pertanyaan berikut:

| # | Pertanyaan pengguna | Jawaban sistem | Fungsi proposal | Dashboard |
|---|---|---|---|---|
| 1 | *ECD sekarang berapa?* (termasuk bila PWD tidak ada) | ECD terukur ⓜ, atau **ECD prediksi ⓥ** dari model ML/hybrid, disertai confidence dan quality status | ECD nowcasting [PHR 5.1] | Live Monitor |
| 2 | *Seberapa dekat ECD ke batas formasi?* | margin terhadap **FG_min** (atas) dan **PP/collapse** (bawah), dihitung di bit dan di open hole, dengan versi PPFG | Pressure window surveillance [PHR 8.1] | Live Monitor, Profil Depth |
| 3 | *Ada indikasi loss/influx?* | warning berbasis rule: kedekatan ECD ke FG + pit volume + flow out−in + SPP. **Bukan diagnosis loss** | Loss/influx early warning [PHR 8.2] | Live Monitor, Riwayat Event |
| 4 | *Ada kondisi abnormal yang mendahului stuck, dan sejak jam berapa?* | risk score + indikator penyebab + waktu mulai + channel bukti (**hipotesis H4**, modul tambahan) | Stuck-pipe module [PHR 1.6, 8.3] | Analisis Anomali |
| 5 | *Seberapa bisa dipercaya modelnya?* | metrik blind-well, error per operating state, SHAP, lineage, promotion gate | Model governance [PHR 7, 9.2] | Model ML |

```
 INPUT (Navita .zip)               LAYER SISTEM [PHR 4.2]                               OUTPUT (RTO dashboard)
 ─────────────────────             ─────────────────────────────────────────────        ───────────────────────────
 Rec 01 IDS Rig (time/depth) ─┐    A  Data acquisition: simpan raw + provenance         • Live Monitor (+ freshness,
 Rec 02 MWD/PWD (time/depth) ─┤    B  Data assurance: time–depth mapping, QC,             confidence, model version)
 Rec 03 PPFG (depth)         ─┼──► C  Prediction: hydraulic baseline + ML/hybrid ECD ──► • Profil Depth (PPFG berversi)
 Rec 04 Mud Weight (depth)   ─┤    D  Formation context: margin vs FG/PP versi approved   • Alert advisory/warning/critical
 Rec 07 Survey (depth)       ─┘    E  Monitoring & events: alert, hysteresis, label       • Riwayat Event (label engineer)
                                   + engine stuck-pipe terpisah (Fase 4)                  • Model ML (blind-well, SHAP)
                                                                                         • Analisis Anomali & Laporan
```

**Yang sistem lakukan dan tidak lakukan** [PHR 1.4, 4.6, 8.4]

| Sistem MELAKUKAN | Sistem TIDAK melakukan |
|---|---|
| Mengestimasi ECD (nowcast) dari parameter yang tersedia saat operasi | Memprediksi FG/PP. Nilai ini diambil dari Record 03 versi approved [PHR 8.1] |
| Menampilkan margin terhadap batas formasi beserta ketidakpastiannya | Mendiagnosis loss/kick/stuck. ECD > FG **tidak membuktikan** loss [PHR 2.6, 8.2] |
| Memberi alert berbasis margin, confidence, persistence, dan sinyal pendukung | Memerintahkan perubahan flow, MW, atau tindakan well control [PHR 8.4] |
| Menampilkan "prediction unavailable / low confidence" bila data tidak valid | Menghasilkan angka yang tampak presisi saat input tidak valid [PHR 4.6] |
| Menyimpan versi data, model, PPFG, serta audit trail | Menggantikan well-control procedures, hydraulics engineering, atau keputusan drilling supervisor [PHR 1.4] |

---

## Daftar Isi

1. [Executive Summary](#bab-1--executive-summary)
2. [Technical Background & Operational Challenges](#bab-2--technical-background--operational-challenges)
3. [Literature Review & Technical Benchmarking](#bab-3--literature-review--technical-benchmarking)
4. [Research Gap & Proposed PHR Innovation](#bab-4--research-gap--proposed-phr-innovation)
5. [Research Methodology](#bab-5--research-methodology)
6. [Data Processing & EDA](#bab-6--data-processing--exploratory-data-analysis)
7. [Model Development, Validation & Benchmarking](#bab-7--model-development-validation--benchmarking)
8. [ECD Monitoring & Drilling Risk Analytics](#bab-8--ecd-monitoring--drilling-risk-analytics)
9. [System Architecture & Dashboard](#bab-9--system-architecture--dashboard)
10. [Implementation Roadmap](#bab-10--implementation-roadmap)
11. [Expected Benefits & KPIs](#bab-11--expected-benefits--kpis)
12. [Conclusions & Recommendations](#bab-12--conclusions--recommendations)
- [Referensi](#referensi-utama) · [Appendix A Data Dictionary](#appendix-a--data-dictionary) · [Appendix B Evaluation Report](#appendix-b--evaluation-report-template) · [Appendix C Formulas](#appendix-c--formulas--interpretation)
- Lampiran D [Studi Kasus Awal](#lampiran-d--studi-kasus-awal) · E [Alur Pengguna (Tutorial)](#lampiran-e--alur-pengguna-tutorial) · F [Keterlacakan Proposal & Masukan Klien](#lampiran-f--keterlacakan-proposal--masukan-klien) · G [Glosarium](#lampiran-g--glosarium)
- **Lampiran H [Daftar Pertanyaan Konfirmasi Klien](#lampiran-h--daftar-pertanyaan-konfirmasi-klien)**

> **Bacaan cepat untuk klien:** mulai dari **Gambaran Sistem** di atas, lalu **Bab 8.5** (logika setiap data masuk), **Lampiran E** (tutorial pengguna), dan **Lampiran H** (pertanyaan yang perlu dikonfirmasi).

---

## Bab 1 — Executive Summary

### 1.1 Latar belakang dan kebutuhan [PHR 1.1]

ECD adalah indikator tekanan efektif fluida pemboran saat sirkulasi. Nilainya dipengaruhi mud weight, annular frictional pressure loss, kondisi aliran, geometri sumur, rheology, rotasi string, dan transportasi cutting. Perubahan ECD yang tidak teridentifikasi dapat mempersempit margin terhadap batas formasi dan menaikkan risiko lost circulation maupun ketidakstabilan lubang.

Kondisi PHR saat ini (dari data dan diskusi klien):
- ECD terukur dari tool downhole SLB/Halliburton (Record 02) **tidak selalu tersedia**. GW337 dan PDSI 53.2 tidak punya sensor ECD, dan run 6-1/8" GW339 pada 20 Nov juga tanpa ECD.
- Navita sudah menampilkan parameter live dan margin ECD vs FG. Namun tampilannya berupa log yang perlu ditafsirkan, dan kemampuan menafsirkan berbeda antar personel.
- Pada dua kejadian November 2026 (stuck pipe PDSI 53.2 dan sloughing/partial pack-off GW339), tanda abnormal muncul beberapa jam sebelum kejadian terkonfirmasi.

### 1.2 Solusi yang diusulkan [PHR 1.2]

Membangun pipeline **ECD Monitor** berbasis lima sumber data: **Record 01** (IDS Rig, time/depth), **Record 02** (MWD/PWD, time/depth), **Record 03** (PPFG geomechanics, depth), **Record 04** (mud weight, depth), dan **Record 07** (directional survey, depth). Sistem menggabungkan **ECD prediction**, **formation-margin monitoring**, dan **kajian lanjutan stuck-pipe early warning** sebagai fungsi decision support yang terpisah.

### 1.3 Sasaran teknis [PHR 1.3]

| # | Sasaran proposal | Implementasi di sistem |
|---|---|---|
| 1 | Dataset terstandardisasi dan traceable lintas section/sumur, dengan audit sinkronisasi waktu & kedalaman | Layer A–B (Bab 4.2, 6), data dictionary (Appendix A, `CHANNELS.md`), laporan QC per sumur |
| 2 | Menguji RF, XGBoost, LightGBM, dan model sekuensial (bila data temporal memadai) terhadap hydraulic baseline | Eksperimen A–F (Bab 7.1) |
| 3 | Validasi generalisasi dengan sumur blind dan split kronologis. Laporan berisi MAE, RMSE, R², bias, error ekstrem, dan performa per operating state | Bab 5.7, 7.2, Appendix B |
| 4 | Menampilkan ECD aktual/prediksi, margin terhadap batas formasi yang disetujui, tren, kualitas data, dan event review | Enam dashboard (Bab 9.2, `UI_MOCKUP.md`) |
| 5 | Uji shadow mode sebelum dipakai sebagai decision support operasional | Fase 3 (Bab 10), mulai awal Desember 2026 di GW339, GW337 (BDSI 60 sudah selesai → uji blind offline) |

### 1.4 Ruang lingkup dan batasan [PHR 1.4]

| Termasuk | Tidak termasuk |
|---|---|
| Estimasi ECD real-time untuk section dan konfigurasi drilling yang tercakup data latih: 12.25", 8.5", serta 6-1/8" bila ada label | Bukti otomatis prediksi loss/kick dari model ECD |
| Margin terhadap PPFG berversi, alert terverifikasi, dan event review | Diagnosis tunggal loss dari alarm ECD vs FG, karena alarm ini hanya indikator paparan risiko |
| Modul stuck-pipe anomaly (tahap lanjutan, offline → shadow) | Pengganti well-control procedures, hydraulics engineering, atau keputusan drilling supervisor |
| Input zip Navita (ASCII LAS/CSV) | Perhitungan PPFG/geomekanik (disediakan PHR via Rec 03) |
| Dukungan klien: Overview multi-room, Laporan (narasi AI), Login lokal | Backlog di luar proposal: what-if, proyeksi depth, citra cutting (perlu persetujuan) |

### 1.5 Deliverables dan kriteria keberhasilan [PHR 1.5]

| Deliverable | Acceptance evidence (diusulkan proposal) | Bentuk di sistem |
|---|---|---|
| Data mart drilling | data dictionary, unit conversion, completeness, timestamp/depth audit | DB TimescaleDB/Parquet + `CHANNELS.md` + laporan QC (Data & Upload) |
| ECD models | performa blind-well dan perbandingan dengan hydraulic baseline | model registry + evaluation report (Appendix B) |
| Monitoring prototype | live trend, depth profile, model provenance, event logs | enam dashboard |
| Pilot report | error per operating state, alert quality, data latency, feedback engineer | laporan Fase 3–4 |

> Target numerik akurasi dan ambang alert final **ditetapkan setelah studi distribusi data PHR**. Angka pada mockup hanyalah contoh antarmuka, bukan KPI terverifikasi [PHR 1.5].

### 1.6 Penambahan scope: stuck-pipe early warning [PHR 1.6]

Sebagai fase lanjutan, platform mengevaluasi potensi early warning stuck pipe dari torque-and-drag, hookload, surface torque, RPM, SPP, flow, WOB, ROP, survey, serta tren ECD. Outputnya berupa **risk score dan indikator penyebab yang mungkin**, bukan diagnosis. Label kejadian stuck/near-stuck **harus dikonfirmasi** dari DDR, laporan operasi, dan review engineer. Atas permintaan klien, dua studi kasus (PDSI 53.2 dan GW339, Lampiran D) dijalankan **sebagai studi retrospektif offline** untuk menguji hipotesis H4. Studi ini bukan klaim kemampuan sistem.

---

## Bab 2 — Technical Background & Operational Challenges

### 2.1 Definisi ECD dan prinsip hydraulics [PHR 2.1]

```
ECD (ppg) = MW (ppg) + ΔP_annular (psi) / [0.052 × TVD (ft)]
```

- ΔP_annular harus mewakili kehilangan tekanan annulus yang relevan untuk titik evaluasi. Persamaan ini merupakan penyederhanaan, sehingga kondisi transien, densitas fluida, dan efek suhu/tekanan perlu ditangani sesuai kebutuhan.
- **ECD dan batas formasi harus dirujuk pada datum/kedalaman yang konsisten** (TVD yang sama, referensi tekanan yang sama).
- Saat pompa mati, ΔP_annular ≈ 0 sehingga tekanan dasar lubang ≈ **ESD ≈ MW**. Saat trip, ada efek swab/surge.
- Hubungan ECD dengan flow dan state tidak selalu linear karena cuttings loading, rheology, geometri, eccentricity, dan rotasi. Asumsi concentric annulus dan steady state juga terbatas [Alsaihati 2021].

### 2.2 Pressure window dan engineering margin [PHR 2.2]

- Batas operasi **tidak bisa direduksi menjadi satu angka PP dan FG**. PP berkaitan dengan well control, collapse/stability pressure dapat menjadi batas bawah tambahan, dan batas atas dipengaruhi fracture/formation integrity (FIT/LOT) beserta uncertainty-nya.
- Mud weight window adalah konsep geomekanika tersendiri [Chen 2025] dan diperlakukan sebagai **layer terpisah** dari model ECD.
- Margin sederhana di dashboard: **`margin_atas = FG_min − ECD_pred`** (atau `− ECD_actual`) pada interval yang sama. Margin positif yang kecil berarti mendekati batas, **bukan bukti formasi pasti fracture**.
- **FG_min yang ditampilkan wajib nilai approved dan berlaku untuk open-hole exposed interval, bukan hanya formasi di bit depth.** Implementasinya ada di Bab 8.1.

Konteks dari klien yang mengisi konsep di atas:
- **Record 03 Navita** berisi PP, **SFG (Shear Failure Gradient)**, FG Min/Max, SHMax, dan OBG. Klien memakai SFG sebagai batas collapse/sloughing.
- **Sloughing** (dinding lubang rontok, umumnya di shale) terjadi dalam dua kondisi:
  - **Pumps off**: hanya MW (statis) yang menahan lubang, sehingga MW di bawah SFG berisiko.
  - **Pumps on**: penyebabnya umumnya **mekanis** (rotasi, gesekan torsi, tool joint).
- **FG Min adalah angka model reservoir** yang diperoleh saat sumur akan dibor, sehingga perubahannya (mis. akibat depletion) baru diketahui saat ada drilling baru. Rec 03 karena itu wajib **berversi** [PHR 2.5].

### 2.3 Operasi yang mengubah ECD [PHR 2.3]

| Faktor operasional | Pengaruh | Implikasi pemodelan | Channel / record PHR |
|---|---|---|---|
| Flow rate / pump transitions | friksi annulus & transien berubah | segmentasi pump-on/off, lag dan ramp | `MFIA`, `SPM1–3` (Rec 01) |
| Mud density / rheology | suku hidrostatik & friksi berubah | timestamp mud report, validitas PV/YP | `MUDWEIGHT` (Rec 04). **Reologi belum ada di Navita** |
| ROP / cuttings loading | solids transport, restriksi annulus | lagged features, konteks hole cleaning | `ROP`, `LSTK` (Rec 01) |
| RPM / string motion | friksi & transport berubah | operating-state features | `RPM`, `BPOS` (Rec 01) |
| Hole size / BHA / inclination | clearance & eccentricity berubah | metadata per section | Rec 07 (`SINC`), metadata section/BHA (manual) |
| Depth / TVD | hidrostatik & geometri | MD–TVD alignment, versi survey | `DBTM`/`DMEA` (Rec 01), Rec 07 |

### 2.4 Keterbatasan data dan sensor [PHR 2.4]

Data rig dan service company berbeda dalam sampling rate, clock, penamaan, dan coverage. Ketidaksesuaian clock dan interpolasi yang salah dapat membuat fitur dan target tidak sejajar sehingga akurasinya semu. Beberapa temuan nyata dari data PHR (detail di Bab 6.2):

| Keterbatasan | Contoh di data PHR |
|---|---|
| Sampling berbeda / tidak tetap | Rec 01 1 dtk (Gula010) vs **1–14 dtk** (GW339 20 Nov); Rec 02 30 dtk; PDSI 53.2 ±1 menit |
| Clock berbeda | `Date/Time` rig vs `dtsrv` server selisih ±7 jam |
| Penamaan berbeda | PDSI 53.2 memakai `DEPTBITM`, `TVOLACT`, `SPARE2`. Tank GW339 bernama rig (`ACTIVESLUG`, `TANK3–5`) |
| Label tidak selalu ada | ECD = 0/kosong di GW337, PDSI 53.2, dan GW339 run 6-1/8" |
| Outlier | ECD 0,98–157 ppg di beberapa sumur |

**Aturan label [PHR 2.4, 5.1]:**
- Bila ECD downhole dipakai sebagai label, provenance sensor, kalibrasi, kedalaman pengukuran, dan konversi tekanan ke ECD harus dibuktikan.
- **Label tidak boleh diisi dari hydraulic baseline lalu dilaporkan sebagai ground truth.**
- Pada periode tanpa label, model tetap boleh melakukan inferensi, tetapi akurasinya tidak dapat dinilai.

### 2.5 Risiko interpretasi [PHR 2.5]

- **Loss** harus dikonfirmasi dengan flow-out/pit-volume, pump state, dan investigasi engineer. ECD tinggi saja tidak membuktikan loss.
- **Nilai FG** mengandung uncertainty dan dapat berubah, sehingga setiap perubahan perlu **versioning**.
- **Outlier sensor** (ECD puluhan sampai ratusan ppg) ditandai dan diperiksa, **tidak otomatis dibuang** karena bisa terkait event nyata.
- **Random split** pada data yang berdekatan waktu menghasilkan leakage, sehingga yang dipakai adalah group-by-well dan time-based holdout. Ini menjelaskan ekspektasi "≈100 %" dari klien (Lampiran H E1).

### 2.6 Relevansi ECD terhadap stuck pipe [PHR 2.6]

- Kenaikan ECD dapat terkait cuttings loading, restricted annulus, atau pack-off, tetapi **ECD bukan indikator tunggal stuck pipe**.
- *Differential sticking* terkait differential pressure, filter cake, kontak string–dinding, dan kondisi statis. *Mechanical sticking* terkait keyseat, ledge, geometri, cuttings bed, atau pack-off.
- Analisis wajib memakai **operating state** (drilling, sliding, reaming, connection, TIH/TOH), parameter mekanik dan hidraulik, serta survey.
- Signature yang layak diuji, dan semuanya **hanya hipotesis**:
  1. torque/drag naik pada depth dan mode sebanding;
  2. SPP naik disertai flow turun atau perubahan ECD (pack-off);
  3. overpull atau slack-off abnormal;
  4. indikasi loss, tight hole, atau fill-on-bottom.

---

## Bab 3 — Literature Review & Technical Benchmarking

### 3.1 Kerangka evaluasi [PHR 3.1]

Empat artikel menjawab dua kebutuhan: (a) prediksi ECD saat drilling dan (b) batas pressure window geomekanika. Karena target, data, dan desain split berbeda, **RMSE antarpublikasi tidak boleh diranking langsung**.

### 3.2–3.6 Matriks bukti [PHR 3.2–3.6]

| Studi | Target / data | Pendekatan | Hasil dilaporkan | Catatan untuk PHR → keputusan desain |
|---|---|---|---|---|
| Alsaihati, Elkatatny & Abdulraheem 2021 (ACS Omega) | ECD, horizontal 5-7/8", 3.567 titik + 1.152 titik sumur kedua | SVM, RF, FN | RF: RMSE 0,42 / R² 0,99 testing; RMSE 0,35 / R² 0,95 Well-2 | Uji lintas sumur penting, tetapi 2 sumur belum cukup → **blind-well wajib** |
| Ekechukwu & Adejumo 2024 (Sci. Rep.) | ECD, sinyal permukaan, 1 sumur, 2.262 titik | XGBoost + SHAP | R² 0,989, RMSE 0,023; fitur penting MW, weight on hook, SPP | **SHAP wajib** (asosiasi, bukan kausal). Random split satu sumur tidak sama dengan blind-well |
| Chen et al. 2025 (Processes) | **MWW pre-drill** (PP, collapse, fracture), 12 sumur | rock mechanics + geological sequence matching + physics-guided LSTM | error collapse −40,96 %, PP −30,43 %, fracture −39,02 % | **PPFG adalah layer terpisah**. Penelitian ini bukan bukti model ECD dapat memprediksi FG |
| Leerojanaprapa et al. 2026 (IJTech) | ECD, 6,125", 38.863 record, 24 variabel MWD/LWD/PWD | SVM, RF, ANN, GB, XGB | RF terbaik, RMSE 0,031 (random 80/20) | Seleksi model secara empiris. **Pisahkan konfigurasi surface-only dan sensor-enhanced** |

### 3.7 Sintesis [PHR 3.7]

Literatur mendukung kelayakan regresi ECD dengan ML, pentingnya input operasional, dan manfaat interpretabilitas. Namun semua itu **belum menjamin akurasi di PHR**. Pembuktian lokal masih diperlukan untuk heterogenitas rig/vendor, mud program, ukuran lubang, transisi section, serta event dan data gap. Karena itu model ECD dipisahkan dari pressure window geologi.

### 3.8 Batas bukti untuk stuck pipe [PHR 3.8]

Keempat jurnal **tidak memvalidasi** deteksi stuck pipe. Modul stuck-pipe adalah perluasan engineering yang memerlukan literatur tambahan, definisi label kejadian, dan pengujian khusus. **Kinerja prediksi ECD tidak boleh ditafsirkan sebagai akurasi deteksi stuck pipe.**

---

## Bab 4 — Research Gap & Proposed PHR Innovation

### 4.1 Research gap [PHR 4.1]

| Gap | Implikasi | Respons PHR → implementasi |
|---|---|---|
| Generalisasi lintas sumur | cakupan & split studi berbeda | blind-well holdout + evaluasi per section (Bab 5.7) |
| Ketersediaan data permukaan | sebagian studi memakai downhole | **surface-only deployable input contract**: ECD/ANP/PWD hanya target, tidak pernah fitur (Bab 5.5) |
| Konsistensi fisika | asumsi hidraulik vs perilaku lapangan | hydraulic baseline + optional residual ML (Bab 7.1 F) |
| Konteks formasi | model ECD ≠ prediksi MWW | layer FG/PP version-controlled (Rec 03) |
| Kepercayaan operasional | akurasi saja tidak cukup | SHAP, uncertainty, quality flags, review engineer |
| Bukti event | threshold ECD bukan konfirmasi loss | event label + korroborasi pit/flow (Bab 8.2) |

### 4.2 Proposed architecture [PHR 4.2]

#### 4.2A Data source register dan aturan integrasi

| Record | Basis | Isi (temuan di file Navita) | Peran | Aturan |
|---|---|---|---|---|
| **01 IDS Rig** | time (1 dtk; GW339 1–14 dtk) & depth (0,25 ft) | bit/hole depth, block, ROP, hookload, WOB, torque, RPM, SPP, flow in, **flow out %**, tank/pit, gain/loss, SPM, strokes, `ACTC` | **fitur** ECD, operating state, loss/influx, stuck-pipe | cek mapping tag, unit, timestamp, data quality |
| **02 MWD/PWD** | time (30 dtk) & depth | **ECD**, annular pressure (`ANP`), TVD (`DVER`), mud density, temperatur, SPP MWD, inklinasi/azimuth kontinu, turbine RPM | **target** ECD (bila sensor & kualitas terkonfirmasi), TVD | ECD hanya label bila provenance terkonfirmasi. Pisahkan depth sensor PWD dari bit depth |
| **03 PPFG** | depth | `PP`, `SFG`, `FGMIN`, `FGMAX`, `SHMAX`, `OBG`, `FORMATION` | batas risiko berversi | **bukan label ECD**, tidak dicampur dengan target. Simpan basis depth, satuan, versi, uncertainty |
| **04 Mud Weight** | depth | `MUDWEIGHT`, `REMARK` | fitur MW, evaluasi MW statis | depth snapshot ≠ nilai tiap timestamp, sehingga **aturan effective-from harus disetujui engineer** |
| **07 Survey** | depth | MD, TVD, inc, azi, DLS, N/S, E/W | TVD, DLS, exposure geometrik stuck | interpolasi minimum curvature, MD ≠ TVD |
| 05, 06 | — | — | tidak diasumsikan ada [PHR 5.3] | disimpan mentah bila terunduh |
| 08 LWD *(opsional, di luar 5 record proposal)* | time & depth | ECD, annular pressure, PWD depth, caliper (hanya BDSI 18 & 19) | label alternatif dan bukti caliper, **hanya bila disetujui** (Lampiran H A13) | — |

**Canonical integration [PHR 4.2A]:**
- Simpan **raw tables per record** apa adanya.
- Dari raw tables, bangun dua tabel: (a) **time-indexed operational feature table** dan (b) **depth-indexed well-context table**.
- **As-of join** untuk data depth-based mengikuti posisi bit/sensor, waktu berlakunya data, dan aturan lag.
- **Interpolasi** survey dan geomekanika hanya dilakukan di dalam domain valid dan tidak boleh melewati batas formasi atau casing.
- **Tanpa future leakage**: revisi PPFG, mud report, atau survey yang belum tersedia pada waktu prediksi historis tidak boleh dipakai.
- Untuk model stuck pipe, fitur diagregasi **per operating state dan event window**, bukan sekadar resampling global.

#### Layer A–E

| Layer | Isi [PHR 4.2] | Service Docker (Bab 9.1) |
|---|---|---|
| **A — Data acquisition** | ingest Rec 01/02 (time/depth), 03/04/07 (depth). Data asli, satuan, source timestamp, depth reference, dan provenance dipertahankan | `etl` (ingest zip, alias mnemonic) |
| **B — Data assurance** | canonical time–depth mapping. Rekonsiliasi MD/TVD, timestamp, clock offset, latency, missingness, kualitas sensor, interpolasi terbatas per section/formasi. Setiap transformasi punya quality flag dan audit trail | `etl` (QC, sinkronisasi, operating state) |
| **C — Prediction** | hydraulic baseline + beberapa ML regressor. Opsi hybrid `ECD_pred = ECD_hydraulic + ML_residual`. Model dipilih dari blind-well metrics, error tail, robustness, dan latency, **bukan R² saja** | `ml`, `mlflow` |
| **D — Formation context** | PP/FG approved dengan version control. Margin dihitung di depth dan exposure interval yang konsisten, dengan sumber, tanggal revisi, dan uncertainty | `api` (layer PPFG) |
| **E — Monitoring & event management** | trend, depth profile, alert, event annotation. Alert memakai hysteresis, minimum duration, valid data check, dan suppression saat pump-off/sensor invalid | `api`, `dashboard`, `anomaly` |

### 4.3 Pemetaan enam dashboard [PHR 4.3]

| Dashboard | Fungsi engineering | Kontrol tambahan yang direkomendasikan |
|---|---|---|
| Data & Upload | ingest & QC Rec 01/02 | source lineage, clock drift, target availability |
| Model ML | training, metrik, SHAP | group split, confidence, model registry |
| Formasi & FG | tabel tekanan formasi & versi | approval authority, TVD datum, uncertainty |
| Riwayat Event | label loss/noise & catatan engineer | review workflow, evidence traceability |
| Profil Depth | ECD/MW/PP/FG vs depth | exposure interval, depth reference, limit version |
| Live Monitor | ECD aktual vs prediksi, alert card | latency, stale-data badge, operational state |

Detail desain tiap dashboard ada di Bab 9.2 dan `UI_MOCKUP.md`. Contoh angka di dalamnya (RMSE 0,08 ppg, FG, loss event, margin) **tidak boleh dipakai sebagai hasil uji** [PHR 4.3].

### 4.4 Hipotesis dan pertanyaan teknis [PHR 4.4]

| Kode | Hipotesis | Cara uji di sistem |
|---|---|---|
| **PHR-H1** | ML dengan parameter drilling yang tersedia saat operasi mengurangi error ECD terhadap hydraulic baseline pada blind wells | Eksperimen A vs B–E, blind-well (Bab 7.1) |
| **PHR-H2** | Hybrid physics–ML lebih robust daripada pure ML saat mud properties, hole section, atau operating state bergeser | Eksperimen F vs B–D, evaluasi subgroup (Bab 5.7 Tahap 4) |
| **PHR-H3** | Quality flags, interpretability, dan formation margin meningkatkan keterpakaian sebagai decision support | feedback engineer & adoption KPI di shadow/pilot (Bab 11) |
| **PHR-H4** | Gabungan indikator hidraulik, mekanik, survey, dan perubahan operating state mengidentifikasi kondisi abnormal yang mendahului sebagian kejadian stuck/near-stuck | engine stuck-pipe (Bab 8.3), studi kasus (Lampiran D). Butuh label independen, blind-well, false alarm rate, precision, recall, lead time, event-level detection rate |

**Pemetaan hipotesis → kasus uji (disepakati klien, 21 Nov 2026):**

| Hipotesis | Kasus / data uji | Sifat uji | Bukti yang dihasilkan |
|---|---|---|---|
| PHR-H1, H2 | 9 sumur training (grouped CV) + **sumur blind** (usulan **BDSI 60**, sumur selesai, lihat Bab 5.2) | statis, offline | MAE/RMSE/P95/bias vs baseline A per sumur & section |
| PHR-H1, H2, H3 | **GW339 / BLSE-056** — sumur **berjalan (dinamis)**. Run 6-1/8" memakai **rotary BHA tanpa tool ECD** (dipilih karena isu sloughing/risiko stuck) | dinamis, shadow mode | nilai **ECD prediksi ⓥ** di interval tanpa PWD (nilai tambah utama), kestabilan/latency/quality flag live, feedback engineer (H3). **Akurasi** hanya dihitung di interval GW339 yang masih punya ECD terukur |
| PHR-H4 | **PDSI 53.2 / BLSE-57** — sumur **sudah selesai (statis)**, kejadian stuck 7 Nov | statis, offline, mode cut-off | onset & lead time per indikator, false alarm di periode normal |
| PHR-H4 (pendukung) | GW339 (sloughing / partial pack-off) | dinamis, shadow | deteksi indikasi pack-off live, direview engineer |

> Dua studi kasus adalah **uji awal**, bukan bukti statistik. H1–H2 dinilai dari blind-well, bukan dari GW339 run 6-1/8" (tidak ada label ECD).

**Pertanyaan kritis [PHR 4.4]:** seberapa jauh model dapat diekstrapolasi dari section 12.25" ke 8.5" atau ke sumur lain tanpa retraining? Pertanyaan ini diuji sebagai eksperimen tersendiri (latih di 12.25", uji di 8.5") dan dilaporkan terpisah.

> Penamaan: hipotesis mekanisme khusus kasus GW339 dari Proposal GW339 ditulis **GW-H1..H4** (Lampiran D.2) agar tidak tertukar dengan PHR-H1..H4.

### 4.5 Rancangan validasi [PHR 4.5]

| Tahap | Isi | Keluaran |
|---|---|---|
| 1 | data audit & baseline reconstruction per well/section | laporan QC + baseline MW-only/hidraulik |
| 2 | training dengan **grouped CV per sumur** dan feature engineering yang time-aware | kandidat model |
| 3 | **blind holdout**: sumur yang tidak dipakai selama tuning | evaluation report per sumur (Appendix B) |
| 4 | evaluasi subgroup: flow regime, section, mud system, inclination, high-ROP, pump transitions | tabel error per subgroup |
| 5 | **shadow deployment**: pantau error prediksi & drift sebelum operational release | pilot report |

- **Metrik utama:** MAE dan RMSE (ppg).
- **Metrik tambahan:** R², signed bias, P90/P95 absolute error, residual vs depth/flow, % prediksi dalam **engineering tolerance yang disepakati** (Lampiran H E5).
- **Metrik alarm:** precision/recall, false alerts per operating hour, lead time terhadap event yang dikonfirmasi engineer. **Lead time tidak dilaporkan bila sistem hanya nowcasting.**

#### 4.5A Validasi khusus stuck-pipe warning

1. Bangun **katalog event** dari DDR, driller report, dan post-run review. Setiap event berisi timestamp, MD, mode operasi, kategori stuck/near-stuck, dan confidence label.
2. Pisahkan train dan test per sumur dan per waktu, tanpa fitur pasca-kejadian.
3. Ukur false alarm per drilling day, lead time, serta precision/recall di level event.
4. Evaluasi **differential sticking, mechanical sticking, dan pack-off secara terpisah**.
5. Mulai dalam shadow mode dengan review engineer. Threshold dan tindakan mengikuti SOP PHR.

### 4.6 Prinsip deployment dan keselamatan [PHR 4.6]

Sistem adalah **advisory tool**. Setiap output wajib membawa:

| Atribut output | Contoh tampilan |
|---|---|
| timestamp | `20 Nov 19:30 WIB` |
| well / section | `GW339 · 6-1/8"` |
| model version | `ecd-xgb v1.2 (Shadow)` |
| input completeness | `fitur valid 11/12 (TORQUE ✗)` |
| uncertainty / quality status | `±0,2 ppg · confidence OK` atau `LOW CONFIDENCE (OOD)` |
| formation-limit version | `PPFG Rec 03 v2 (19 Nov, approved: …)` |

Bila data tidak valid atau OOD, sistem menampilkan **"prediction unavailable / low confidence"**, bukan angka yang tampak presisi. Keputusan well control, perubahan MW, dan mitigasi loss tetap mengikuti prosedur PHR dan otorisasi engineer.

#### 4.6A Fase pengembangan kapabilitas

| Fase kapabilitas | Isi | Fase roadmap (Bab 10) |
|---|---|---|
| K1 | integrasi & audit lima record | Fase 1 Data readiness |
| K2 | ECD nowcasting & hydraulic baseline | Fase 2 Offline modeling |
| K3 | PPFG margin & alert tervalidasi | Fase 2 → 3 |
| K4 | stuck-pipe anomaly detection **offline** lalu **shadow mode** | Fase 2 (studi kasus offline) → Fase 3 (shadow) |
| K5 | evaluasi kelayakan early warning operasional setelah bukti performa cukup | Fase 4 Controlled pilot |

Model mengeluarkan status **unavailable / degraded** bila data kritis tidak valid.

### 4.7 Kontribusi yang ditargetkan [PHR 4.7]

Integrasi lima record dengan alignment dua sumbu (time/depth), prediksi ECD berbasis ML/hybrid, evaluasi margin PPFG berversi, dan modul anomali stuck-pipe multivariat. Semua klaim peningkatan akurasi dan peringatan dini memerlukan blind-well validation dan evaluasi event historis.

---

## Bab 5 — Research Methodology

### 5.1 Desain penelitian dan definisi produk [PHR 5.1]

- *Applied engineering research* dengan urutan: data readiness → retrospective development → blind-well validation → shadow-mode trial → controlled pilot.
- **Produk utama: estimasi ECD pada waktu t (nowcast).** Forecast horizon 5–15 menit adalah fase pengembangan berbeda dan hanya dilaporkan setelah pengujian prospektif. Proposal GW339 menyebut horizon 5/15/30 menit, dan perbedaan ini dikonfirmasi di Lampiran H B11.
- **Use case prioritas 🆕 (klien, 21 Nov 2026): clean-out run tanpa tool ECD.** Ke depan akan banyak run BHA (mis. rotary BHA karena risiko sloughing/stuck) di lubang yang **sudah dibor**. Run ini hanya cleanout: sirkulasi, reaming, back-reaming, washing, wiper trip. Datanya **time-based** karena hole depth hampir tidak bertambah. Di sinilah **ECD prediksi ⓥ** memberi nilai paling besar. Konsekuensinya:
  - Inferensi dan tampilan memakai **basis waktu**. ECD dievaluasi di **bit depth** (bukan hole depth) dan margin dihitung terhadap PPFG di bit dan di titik terlemah open hole (shoe → hole TD), karena bit bergerak naik-turun di dalam interval terbuka.
  - Fitur kunci clean-out: `bit_depth`, `hole_depth − bit_depth`, TVD bit (survey), flow, SPP, RPM, block velocity, MW, waktu sejak sirkulasi dimulai.
  - **Risiko distribution shift:** label ECD kebanyakan berasal dari interval drilling. Model hanya boleh dipakai di state clean-out bila **label PWD di state yang sama** (sirkulasi/reaming/back-reaming di sumur training) cukup dan lolos blind-well. Bila tidak, output diberi badge **Low confidence** dan Eksperimen F (hybrid) diprioritaskan.
  - **ECD ⓥ hanya valid saat pompa jalan.** Tripping/back-reaming tanpa sirkulasi (swab/surge) butuh model hidraulik (A14).
- **Unit analisis:** well – hole section – timestamp – depth – operational state.
- **Target:** ECD downhole terukur yang lolos quality flag, **bukan ECD sintetis** dari model hidraulik. Tanpa PWD, data hanya dipakai untuk inferensi (**ECD prediksi ⓥ**) atau analisis tanpa label.

### 5.2 Populasi sumur dan kriteria seleksi [PHR 5.2]

**Populasi:** sumur PHR dengan Record 01 & 02 serta metadata well/section/interval.

**Kandidat training wajib memiliki:**
- interval pengukuran ECD yang cukup;
- konsistensi timestamp dan depth;
- log perubahan mud properties.

**Variasi sampel yang dicari:** hole size, inclination, formasi, mud system, BHA, dan operating state.

| Sumur | Area / tipe | Record | Peran usulan | Catatan label ECD |
|---|---|---|---|---|
| BDSI-61 / Gula010 | Gulamo | 01, 02, 03, 04 | training | ada (outlier perlu QC) |
| BDSI-18 / MINA26-0017 HZ | Minas, horizontal | 01, 02, 03, 04, 07, (08) | training | ada |
| BDSI-19 / MINA-02222 HZ | Minas, horizontal | 01, 02, 03, 04, 07, (08) | training | ada |
| BDSI-21 / MINAS 2218 | Minas | 01, 02, 03, 04, 07 | training | ada |
| GW336 / MUTI25-001 | — | 01, 02, 03, 04, 07 | training | ada |
| ACS26 / MANGGA 0004 | Mangga | 01, 02, 03, 04, 07 | training | ada |
| BEKA-253 / 254 / 255 | Beka | template gabungan Rec 01 + ECD | training | hanya saat drilling dengan tool |
| **GW339 / BLSE-056** | Balam SE | 01, 02, 03, 04, 07 + file harian 20 Nov | **studi kasus + shadow** | sebelum run 6-1/8" (bila ada). Run 6-1/8" **tanpa ECD** |
| **PDSI 53.2 / BLSE-57 HW MSF** | Balam SE | 1 LAS + CSV (format rig berbeda) | **studi kasus stuck (offline)** | **tanpa ECD** |
| **BDSI 60** 🆕 | — | (sedang di-download klien) | **sumur blind / testing** (alternatif: sumur training ke-10) — sumur sudah selesai | dicek saat audit; peran final Lampiran H E3 |
| GW337 | — | (menyusul) | shadow mode awal Des | tanpa sensor ECD |

Pembagian blind-well final ditetapkan setelah audit data (Lampiran H E3).

**Kriteria eksklusi:** sensor tidak terkalibrasi, timestamp tidak bisa diselaraskan, satuan ambigu, label ECD tidak dapat diverifikasi, atau interval dengan gangguan akuisisi ekstrem. **Eksklusi tidak boleh otomatis menghilangkan peristiwa loss/stuck** karena itu akan menciptakan bias keselamatan.

### 5.3 Data source register [PHR 5.3]

Nomor record mengikuti nomenklatur operasional (tabel Bab 4.2A). **Mode time-based dan depth-based Record 01/02 adalah dua penyajian dari sumber yang sama, bukan dua sensor independen.** Karena itu, keduanya tidak dihitung sebagai data ganda saat training, dan perbandingan Model-T vs Model-D dilakukan pada titik depth yang sama.

### 5.4 Metode integrasi time–depth [PHR 5.4]

- **Data master** disimpan pada **event time yang dinormalisasi ke UTC** (tampilan ke pengguna dalam **WIB**). Atributnya: bit depth MD, hole depth MD, TVD, well ID, dan section.
- **Rig vs MWD**: disejajarkan memakai diagnostik clock offset (cross-correlation SPP/hookload), normalisasi zona waktu, drift check, dan toleransi join yang ditetapkan **sebelum training** (usulan ±15 dtk).
- **Resampling** mempertahankan provenance, source timestamp, dan **gap flag**. Gap tidak diinterpolasi melewati batas.
- **As-of depth join** dilakukan di dalam section yang sama, tanpa ekstrapolasi melewati casing/formation atau zona tanpa data.
- **Survey** diinterpolasi geometris (minimum curvature). MD dan TVD tidak pernah dipertukarkan.
- **PPFG & MW** dipetakan menurut effective-depth interval dan version/effective date.
- **No look-ahead leakage**: data yang baru diketahui setelah waktu prediksi tidak dipakai sebagai fitur pada timestamp sebelumnya. Aturan ini juga mendasari **mode cut-off** (Bab 8.3).

### 5.5 Target, fitur dan baseline [PHR 5.5]

- **Fitur utama:** MW, flow in, SPP, RPM, WOB, ROP, hookload, torque, MD/TVD, inclination, hole size, BHA/annular geometry, operational state, dan rheology bila tersedia.
- **Fitur tambahan:** rolling trends, relasi SPP/flow, stand transition, lagged ECD, dan section identity. **Lag hanya dihitung dari masa lalu.**
- **Input contract surface-only:** ECD, ANP, dan PWD tidak pernah menjadi fitur pada konfigurasi yang dipakai di sumur tanpa sensor. Lagged ECD **hanya** dipakai di konfigurasi *sensor-enhanced* dan dilaporkan terpisah [PHR 3.5, 7.3].

| Baseline wajib | Definisi | Kebutuhan data |
|---|---|---|
| (i) MW-only | ECD ≈ MW (Rec 04) | tersedia |
| (ii) Hydraulic ECD | model rheology (Bingham/Power-law/Herschel-Bulkley) + geometri annulus | **reologi PV/YP, hole/casing size, BHA → diminta** (Lampiran H A14) |
| (iii) Persistence | ECD(t) = ECD(t−Δ) untuk deret waktu | tersedia bila ada label |

**Hybrid residual:** `ECD_pred = ECD_hydraulic + ML_residual`. Kelayakannya ditentukan oleh benchmark blind-well.

### 5.6 Algoritma dan tuning [PHR 5.6]

- **Kandidat:** RF, XGBoost, LightGBM, dan LSTM/sequence model bila cakupan deret waktu memadai. Model tabular menjadi baseline kuat sebelum model sequence dicoba.
- **Tuning:** group-aware CV pada sumur training. Scaler, imputasi, dan feature selection **di-fit hanya pada fold training**.
- **SHAP** dipakai untuk interpretasi kontribusi model, bukan sebagai bukti sebab-akibat fisika.
- **Saat deployment:** monitoring feature drift serta deteksi uncertainty/OOD wajib aktif.

### 5.7 Strategi validasi [PHR 5.7]

- **Holdout utama:** satu atau lebih sumur yang **sama sekali tidak** dipakai di training, tuning, imputasi, feature selection, atau threshold selection.
- Dengan 9 sumur training, dipakai leave-one-well-out untuk diagnosis dan minimal satu sumur blind tetap untuk laporan akhir.
- **Forecast** (fase lanjut): rolling-origin temporal validation dengan **embargo**.
- **Metrik regresi:** MAE, RMSE, R², P90/P95 absolute error, bias, dan **kalibrasi** per well/section/formation/operational state.
- **Evaluasi wajib per state clean-out 🆕:** metrik blind-well dilaporkan terpisah untuk sirkulasi, reaming, back-reaming, dan washing (selain drilling). State tanpa label cukup ditulis **"belum tervalidasi"**, bukan dirata-rata ke angka global.
- **Metrik risiko:** false alarms per drilling day, precision, recall, event lead time, missed events, dan alarm persistence.
- **Confidence interval** diperoleh dari resampling berkelompok di level sumur (grouped bootstrap).

### 5.8 Acceptance criteria dan governance [PHR 5.8]

- Kriteria numerik **belum ditetapkan sebagai hasil yang dicapai**. Engineering/RTO PHR menyetujui target berdasarkan toleransi error untuk narrow-margin drilling, variasi FG, dan biaya false alarm.
- Perubahan model memerlukan **versioning data, code, dan hyperparameters**, approval, audit log, rollback plan, serta model performance review. Implementasinya di MLflow registry dan halaman Model ML.

---

## Bab 6 — Data Processing & Exploratory Data Analysis

### 6.1 Inventarisasi dan data dictionary [PHR 6.1]

**Data dictionary per record** berisi: canonical field name, original tag, unit, sensor origin, sampling rate, source time zone, missing-value convention, expected physical range, valid section, dan owner. Isinya ada di **Appendix A** (ringkas) dan **`CHANNELS.md`** (lengkap, termasuk alias mnemonic antar rig).

- Mapping tag dibuat **eksplisit**, tidak berdasarkan kemiripan nama. Contoh: `SPARE` GW339 yang isinya identik dengan torque tidak otomatis dianggap torque.
- Completeness dilaporkan per well, section, sensor, dan operating mode.
- **Jumlah baris tidak sama dengan jumlah observasi independen.**

### 6.2 Quality control dan sensor validation [PHR 6.2]

**QC berlapis** mencakup: schema checks, unit conversion, duplicates, frozen sensors, impossible jumps, telemetry gaps, recalibration, drift, outlier fisik, dan cross-sensor consistency.

- Aturan clipping **dilatih pada data training saja**.
- **Label engineer** (loss, kick, pack-off, stuck) disimpan **terpisah dari flag noise sensor**.

**Temuan QC pada data PHR yang sudah diterima:**

| # | Temuan | Dampak | Penanganan |
|---|---|---|---|
| 1 | Export custom lama Rec 01 tanpa `TVA`, `GL`, `MFOP` | loss/influx tidak bisa | **selesai**: full Record 01 berisi semua channel |
| 2 | Mud density Rec 02 97–100 % nol | fitur MW hilang | **selesai**: MW dari **Rec 04** |
| 3 | Rec 03 tersedia (Gula010: PP 8,3–8,7, SFG 9,1–11,2, FG Min 13,2–16,5 ppg); `FORMATION` kosong | nama formasi tidak ada | minta formation tops |
| 4 | Gula010 ±3.250 ft: MW 11,0 < SFG 11,2 | kandidat studi MW statis | dipakai di EDA |
| 5 | Outlier ECD 0,98–157 ppg | merusak training | flag fisik (usulan 7–20 ppg) + Hampel; **tidak dibuang otomatis** |
| 6 | Null `-999.25`; depth berlabel `.m` padahal ft | salah baca | konversi + catatan |
| 7 | `Date/Time` rig vs `dtsrv` selisih ±7 jam | sinkronisasi salah | acuan `dtsrv`, normalisasi UTC, tampilan WIB |
| 8 | PDSI 53.2: mnemonic berbeda, interval ±1 menit, ECD = 0, TVD = 0 | ingest gagal / tanpa label | tabel alias, ECD prediksi ⓥ, TVD dari survey |
| 9 | Rec 01 ±300 MB/minggu/sumur | lambat | ingest streaming, Parquet/TimescaleDB |
| 10 | ECD tidak valid saat pumps off/tripping | label palsu | dipisah per operating state |
| 11 | GW339 20 Nov: **ECD Rec 02 kosong** (run 6-1/8") | tidak ada label | ECD prediksi ⓥ, tanpa klaim akurasi |
| 12 | GW339 20 Nov Rec 01: interval 1–14 dtk (median 7), gap 04:17–06:01 | bias rolling | resample ke grid tetap. Gap ditandai, tidak diinterpolasi |
| 13 | GW339 20 Nov Rec 01: `ACTC` = 0, `TVA`/`GL` kosong, tank bernama rig | operating state & pit tidak langsung ada | state diturunkan dari flow/RPM/depth/block. Active pit dihitung dari tank aktif yang dikonfirmasi |
| 14 | GW339 20 Nov Rec 02: `WID` = `P_BLSE27_0003HW_MSF`, SPP/WOB negatif, hookload 181 vs 149 klb | identitas & kalibrasi | konfirmasi nama. Parameter mekanik diambil dari Rec 01 |

### 6.3 Prosedur sinkronisasi [PHR 6.3]

| Langkah | Isi | Catatan implementasi |
|---|---|---|
| 1 | standardisasi well/section ID & unit | tabel alias + koreksi `WID` |
| 2 | normalisasi event time | `dtsrv` → UTC |
| 3 | rekonstruksi bit depth, hole depth, survey-derived TVD | Rec 07 min. curvature; `DVER` Rec 02 sebagai cek |
| 4 | estimasi clock offset rig–MWD | cross-correlation SPP/hookload Rec 01 vs Rec 02 |
| 5 | nearest/as-of join dalam toleransi | ±15 dtk (usulan) |
| 6 | mapping Rec 03/04/07 per depth & versi | effective-depth + effective date |
| 7 | audit mismatch & export quality report | laporan QC di Data & Upload |

Untuk MWD yang terlambat dikirim, sistem membedakan **measurement time, transmission time, dan ingestion time**. Saat inferensi live, hanya fitur yang benar-benar sudah tersedia di rig pada waktu itu yang boleh dipakai.

**Operating state** (dipakai di semua bab berikut):

| Operating state | Ciri (bila `ACTC` tidak terisi) | Pemakaian |
|---|---|---|
| Drilling rotary | bit = hole depth, flow > batas, ROP > 0, RPM > 0 | training ECD |
| Sliding | bit = hole depth, flow > batas, ROP > 0, RPM ≈ 0 | training ECD (dipisah) |
| Reaming / back-reaming | bit < hole depth, flow & RPM > 0, block bergerak | **training & inferensi ECD (clean-out)** bila PWD tercatat; torque/overpull |
| Washing (clean-out) | bit < hole depth, flow > batas, RPM ≈ 0, block turun | **training & inferensi ECD (clean-out)**; tag/set-down |
| Sirkulasi | flow > batas, bit diam di atas bottom | training & inferensi ECD (clean-out), pack-off |
| Connection | flow ≈ 0 singkat, block di slip | ECD tidak dijadikan target |
| TIH / TOH | bit bergerak, flow ≈ 0 (atau wash) | tag/set-down, overpull, swab/surge |
| Pumps off / statis | flow ≈ 0, pipa diam | MW statis vs batas bawah; durasi diam (differential) |

### 6.4 EDA dan interpretasi engineering [PHR 6.4]

- Distribusi dan korelasi dianalisis **per section dan operating state**: ECD–flow, ECD–SPP, ECD–MW, ECD–ROP, ECD–RPM.
- Plot ECD vs TVD/MD dilengkapi PPFG envelope, casing shoe, batas formasi, dan perubahan mud properties.
- Analisis lag/hysteresis dipakai untuk melihat dampak cuttings loading, pump transitions, dan stand connection.
- Korelasi tidak langsung diterjemahkan menjadi mekanisme penyebab tanpa pemeriksaan engineering.
- Perbandingan antar area (Beka vs Minas vs Gulamo vs Balam) dipakai untuk menilai kebutuhan model per cluster.

### 6.5 Contoh output pengolahan data [PHR 6.5]

Deliverables Bab 6: **data readiness matrix**, data quality dashboard (Data & Upload), data lineage diagram, synchronized feature table, **missingness map**, **outlier review log**, EDA plots, dan **engineer sign-off**.

---

## Bab 7 — Model Development, Validation & Benchmarking

### 7.1 Eksperimen pemodelan [PHR 7.1]

| Eksperimen | Model | Catatan |
|---|---|---|
| A | hydraulic baseline (+ MW-only dan persistence sebagai pembanding) | butuh reologi/geometri. Bila belum ada, A dilaporkan sebagai MW-only dan ditandai |
| B | Random Forest | |
| C | XGBoost | |
| D | LightGBM | |
| E | LSTM | hanya bila time series stabil |
| F | hybrid residual ML (`ECD_hydraulic + ML_residual`) | setelah A tersedia |

- Semua eksperimen memakai **well split dan feature availability policy yang sama** agar perbandingannya adil.
- Pengujian bertahap: within-well retrospective diagnostic → blind-well generalization → shadow-mode prospective assessment.
- Kinerja dilaporkan **terpisah untuk 12.25", 8.5", dan section lain** (6-1/8") bila data ada.
- **Konfigurasi input:** *surface-only* (produk utama, dipakai di sumur tanpa PWD) dan *sensor-enhanced* (riset) selalu dilaporkan terpisah.

### 7.2 Pelaporan kinerja [PHR 7.2]

Tabel hasil diisi setelah pengujian:

| Model | Train wells | Blind wells | Section | MAE | RMSE | R² | P95 error | Bias | Latency | OOD rate |
|---|---|---|---|---|---|---|---|---|---|---|
| *(diisi setelah uji)* | | | | | | | | | | |

Grafik wajib: actual-vs-predicted, residual by depth, residual by flow/section, error distribution, calibration, dan SHAP.

### 7.3 Pencegahan leakage dan overclaim [PHR 7.3]

- PWD/ECD aktual tidak pernah menjadi fitur di produk yang ditujukan untuk sumur tanpa sensor.
- Tidak ada random split per baris untuk klaim generalisasi antar sumur.
- Angka pada mockup Model ML (mis. RMSE 0,08 ppg atau R² 0,97) adalah **ilustrasi UI**.
- Klaim di laporan dan narasi AI **dibatasi pada metrik yang benar-benar diuji** (Bab 9.3).

### 7.4 Model promotion [PHR 7.4]

```
kandidat ─► data QC ✓ ─► blind-well test ✓ ─► engineering review ✓ ─► shadow monitoring ✓
        ─► threshold terdokumentasi ✓ ─► rollback terverifikasi ✓ ─► PROMOTE (Production)
```

- **Re-training dipicu oleh** drift yang terukur, perubahan mud system/section, atau performa yang menurun. **Perubahan PPFG saja bukan pemicu**, karena PPFG adalah layer terpisah.
- Setiap sumur yang selesai (rig pindah) menambah data kandidat. Status model: Candidate → Shadow → Production, dan versi lama bisa di-rollback.

---

## Bab 8 — ECD Monitoring & Drilling Risk Analytics

### 8.1 Pressure window surveillance [PHR 8.1]

ECD prediksi/aktual dibandingkan dengan PP, collapse limit, dan FG yang **berlaku pada depth dan versi data saat itu**. **FG tidak diprediksi** oleh model ECD. Record 03 menjadi sumber batas geomekanika terpisah yang dapat diperbarui dan diaudit.

```
PPFG(d)            = lookup Rec 03 (versi berlaku saat t) pada TVD(d) → PP, SFG, FG_min
MW(t)              = Rec 04 as-of bit depth + aturan effective-from (disetujui engineer)
ECD_ref(t)         = ECD aktual valid (Rec 02) bila ada; jika tidak → ECD_pred ⓥ
batas_bawah(d)     = max(PP, SFG)  ← usulan default; final mengikuti model geomekanika (Lampiran H B1)

margin_atas_bit    = FG_min(bit) − ECD_ref
margin_atas_OH     = min_{d ∈ [shoe, bit]} [ FG_min(d) − ECD_est(d) ]       ← open-hole exposed interval
margin_bawah       = ECD_ref − batas_bawah(bit)                              (pumps on)
margin_statis      = MW − max_{d ∈ [shoe, bit]} batas_bawah(d)              (pumps off / trip)
```

- **ECD_est(d)** di titik open hole di atas bit diestimasi dari profil hidraulik bila baseline hidraulik sudah tersedia. Pada tahap awal dipakai pendekatan konservatif (ECD bit dikoreksi ke TVD titik tersebut, ditandai "estimasi"). Pendekatan final dikonfirmasi di Lampiran H B12.
- **Ketidakpastian** ditampilkan sebagai interval. Contoh: `margin atas 2,6 ppg (2,3–2,8)`. Interval ini menggabungkan interval prediksi model (dari residual blind-well per operating state) dan uncertainty FG bila Rec 03 menyediakannya. Bila tidak tersedia, label "uncertainty FG: tidak tersedia" ditampilkan.
- **MW statis vs batas bawah** saat pumps off dimasukkan sesuai mekanisme sloughing yang dijelaskan klien. Outputnya berupa **rekomendasi verifikasi**, mis. "MW 10,0 < SFG 10,6 di 5.348–5.651 ft, tinjau dengan Mud Eng/Geomechanics". Sistem tidak memerintahkan perubahan MW [PHR 8.4].
- **Mode Rencana MW** (opsional): engineer memasukkan MW rencana per interval, lalu sistem menandai interval di luar window. Mode ini hanya bersifat informasi, sebagai pengganti istilah "pre-drill" dari klien.

### 8.2 Loss / influx early warning [PHR 8.2]

**Rule-based warning** menggabungkan:
1. kedekatan ECD ke FG (margin atas);
2. perubahan **pit volume** (active pit, dari `TVA` atau tank aktif);
3. **flow out − flow in** (`MFOP`, `MFIA`);
4. SPP;
5. event yang sudah direview engineer.

| Pola | Logika awal (diuji, bukan final) | Label tampilan |
|---|---|---|
| Kandidat loss | flow out % turun di flow in tetap **dan/atau** active pit turun, ± margin atas kecil | "indikasi loss, perlu verifikasi" |
| Kandidat influx | flow out % naik, active pit naik, ± ECD rendah relatif PP | "indikasi influx, ikuti prosedur well control rig" |
| Paparan risiko loss | margin atas ≤ batas, tanpa bukti pit/flow | "paparan risiko loss (bukan loss)" |

- Loss **tidak** dikonfirmasi hanya dari ECD > FG. Loss juga dapat terjadi di bawah FG nominal.
- Untuk influx, sistem **tidak menggantikan** primary well control indicators dan prosedur rig.
- Jika channel pit/flow tidak tersedia, warning loss/influx **nonaktif dan diberi penanda**.

### 8.3 Stuck pipe early warning — modul tambahan [PHR 8.3]

> **PHR-H4 (hipotesis).** Engine ini terpisah dari regresi ECD. Targetnya adalah **onset insiden yang diverifikasi engineer dan precursor window**, bukan label "stuck" yang diturunkan dari threshold ECD. Pendekatannya dimulai dari **anomaly scoring + engineering rules**. Supervised classification baru dibuat bila event berlabel cukup.

**Kandidat fitur:** PU/SO/ROT hookload, torque trend, SPP, flow, ROP, RPM, inclination, DLS, hole size, cuttings/formation, stationary time, pipe movement state, dan margin ECD.

**Tahapan engine** (selaras dengan [GW §5]):

| Tahap | Isi |
|---|---|
| A — Baseline | SPP, torque, P/U–S/O–RO normal untuk depth, flow, MW, BHA, dan operating state yang sama, dari periode normal sumur itu atau baseline "take baseline" rig |
| B — Anomali | residual positif yang **menetap**, kenaikan torque/drag, tag berulang, flow out/pit berubah, dievaluasi per operating state |
| C — Skor | gabungan indikator menjadi **risk score 0–100**, **waktu mulai** tiap indikator, dan **kategori dugaan** |
| D — Keputusan | tren pendukung & ketidakpastian ditampilkan. Keputusan tetap pada personel operasi |

**Detektor awal** (semua hipotesis, perlu verifikasi lapangan [PHR 8.3]):

| Pola | Channel | Logika awal | Kategori |
|---|---|---|---|
| Tag / set-down berulang (TIH) | WOB, hookload, bit depth, block | slack-off turun ≥ N klb dari baseline, ≥ 2× dalam T jam | mechanical / tight hole |
| Overpull / drag naik | hookload, block | P/U − baseline(depth, pump state) > batas | mechanical |
| Torque spike / stall | torque, RPM | torque > baseline + kσ, RPM → 0 saat torque naik | mechanical / pack-off |
| Pack-off / poor hole cleaning | SPP, flow, flow out %, torque | SPP naik ≥ x % di flow tetap + torque naik, ± flow out turun | **pack-off** |
| Residual ECD positif menetap | ECD aktual − ECD pred | residual > batas selama durasi tertentu (hanya bila ada label ECD) | pack-off / hole cleaning |
| **Lonjakan / kenaikan mendadak ECD ⓥ** 🆕 (run tanpa PWD, mis. PDSI 53.2 BHA #4) | tren ECD prediksi ⓥ + flow, RPM, MW | ECD ⓥ naik ≥ x ppg dalam y menit **pada flow/RPM/MW yang sama**, menetap ≥ durasi minimum; diabaikan N menit pertama setelah pompa hidup, saat perubahan flow, connection, atau perubahan MW | **pintu masuk** pack-off / hole problem → dicek silang dengan SPP, torque, overpull, flow out |
| Pipa diam lama di formasi permeabel | block, bit depth, durasi | stationary time > batas + overbalance (MW − PP) besar | **differential** |
| MW statis < batas bawah + pumps off lama | MW, SFG, durasi pumps off | lalu fill/tag saat pompa hidup | wellbore instability (sloughing) |

- **Metode:** z-score robust terhadap baseline, EWMA/CUSUM untuk perubahan bertahap, hysteresis, dan durasi minimum. Isolation Forest/autoencoder pada residual baru dipakai setelah label cukup.
- **Diferensiasi wajib:** pack-off/poor hole cleaning vs differential vs mechanical, karena polanya tumpang tindih dan perlu verifikasi lapangan.
- **Mode Cut-off (analisis retrospektif).** Pengguna memilih waktu T (mis. 7 Nov 12:00). Baseline, fitur, dan skor dihitung **hanya dari data ≤ T**, tanpa menghapus baris file (prinsip no look-ahead, Bab 5.4). Data setelah T ditampilkan abu-abu untuk verifikasi dan menghitung **lead time** terhadap onset yang dikonfirmasi. Replay maju dari T juga tersedia.
- **Metrik modul:** event recall, false alarm per 24 jam, warning lead time, dan utilitas bagi engineer [PHR 8.3]. Modul baru dipromosikan ke operasional bila lead time dan beban false alarm layak bagi RTO [PHR 12.3].

### 8.4 Alert policy dan human factors [PHR 8.4]

Tingkat alert berbasis **margin, confidence, persistence, dan corroborating signals**:

| Tingkat | Kondisi (usulan default, disetujui Drilling Eng + HSE) | Tampilan |
|---|---|---|
| 🟢 **Normal** | tidak ada kondisi di bawah ini. Artinya "**tidak ada anomali terdeteksi pada data yang tersedia**", **bukan** "aman untuk lanjut" [GW §6] | hijau |
| 🟡 **Advisory** | margin atas/bawah ≤ 0,5 ppg, **atau** ECD naik cepat (> 0,2 ppg / 5 mnt), **atau** satu indikator anomali tanpa korroborasi | kuning |
| 🟠 **Warning** | margin ≤ 0,25 ppg yang bertahan ≥ durasi minimum, **atau** ≥ 2 indikator anomali saling menguatkan (mis. SPP↑ + torque↑), **atau** MW statis < batas bawah saat pumps off | oranye |
| 🔴 **Critical** | margin atas ≤ 0 dengan confidence OK, **atau** indikasi loss/influx dari pit/flow, **atau** beberapa indikator stuck-pipe bersamaan dengan risk score tinggi | merah + bunyi |
| ⚫ **Unavailable** | data stale, input kritis tidak valid, sensor invalid. Atau ditampilkan badge **Low confidence** bila OOD | abu-abu |

Setiap alert menampilkan:
- data quality status;
- alasan (indikator + nilai vs baseline);
- affected depth;
- **rekomendasi verifikasi** (mis. "cek flow out & pit", "bandingkan P/U dengan baseline");
- **acknowledgment log** (siapa, kapan, catatan).

Aturan lain:
- **Hysteresis & durasi minimum** (usulan 60 dtk).
- **Suppression** saat pumps off (untuk ECD dinamis) atau saat sensor invalid.
- **Tidak ada perintah otomatis** mengubah flow rate, mud weight, atau well control tanpa persetujuan engineer.

### 8.5 Alur logika setiap kali data masuk

Urutan ini sama untuk mode live, replay, dan cut-off. Karena itu, hasil analisis retrospektif sama dengan hasil yang akan muncul bila sistem berjalan live saat itu.

```
DATA BARU (upload zip / folder pantau)
 │
 ├─① DATA ASSURANCE ── umur data > batas (usulan 30 mnt)? ──ya──► ⚫ Unavailable "data tertunda"
 │                     input kritis hilang/invalid? ─────────ya──► ⚫ / Low confidence + penanda
 ├─② OPERATING STATE ── drilling · sliding · reaming · sirkulasi · connection · TIH · TOH · pumps off
 ├─③ KONTEKS DEPTH ── PP, SFG, FG_min (Rec 03 versi berlaku) · MW (Rec 04 effective-from) · shoe · open hole
 ├─④ ECD ── label PWD valid? ──ya──► ECD ⓜ
 │                          └tidak─► model (versi aktif) ─► ECD ⓥ + interval + confidence (OOD → Low confidence)
 ├─⑤ MARGIN ── pumps on : atas (bit & open hole), bawah        pumps off : statis (MW vs batas bawah)
 ├─⑥ LOSS/INFLUX RULES ── margin + pit + flow out−in + SPP (Bab 8.2)
 ├─⑦ STUCK-PIPE ENGINE ── baseline per state → indikator → mulai sejak → risk score (Bab 8.3)
 ├─⑧ TINGKAT ALERT ── kondisi terberat + persistence + korroborasi (Bab 8.4)
 └─⑨ ALERT & AUDIT ── alert + event baru di Riwayat Event · ack log · semua output membawa
                       timestamp, well/section, model version, completeness, quality, PPFG version
```

**Contoh membaca output (ilustrasi GW339, 20 Nov 19:30):**

| Langkah | Hasil |
|---|---|
| ② State | sirkulasi/cleanout, 231 gpm, RPM 20 |
| ③ Konteks | bit 5.540 ft (rathole, shoe 7" 5.348 ft): PP 8,7 · SFG 10,6 · FG_min 13,3 · MW 10,0 ppg *(angka PPFG ilustrasi)* |
| ④ ECD | tanpa PWD → ECD ⓥ 10,7 ppg (10,5–10,9), model `ecd-xgb v1 (Shadow)`, fitur valid 11/12 |
| ⑤ Margin | atas 2,6 (2,4–2,8) 🟢 · bawah 0,1 🟡 · statis −0,6 (relevan saat pompa mati) 🟠 |
| ⑥ Loss/influx | flow out % & pit stabil → tidak aktif |
| ⑦ Stuck engine | SPP +18 % di flow sama (sejak 19:12), torque 7→15 kft·lb (sejak 19:20) → risk score 62, kategori dugaan pack-off |
| ⑧–⑨ | 🟠 **Warning** "indikasi pack-off sejak 19:12 @5.540 ft, verifikasi SPP/torque vs baseline & returns" |

---

## Bab 9 — System Architecture & Dashboard

### 9.1 Arsitektur logis [PHR 9.1]

| Lapisan proposal | Isi | Service Docker |
|---|---|---|
| 1 — Ingest | IDS Rig / MWD / PPFG / MW / survey (zip Navita) | `etl` |
| 2 — Validation & store | validasi, alignment timestamp–depth, canonical data store, lineage | `etl`, `db` (PostgreSQL + TimescaleDB + Parquet) |
| 3 — Feature & registry | feature service, model registry | `ml`, `mlflow` |
| 4 — Inference & risk | ECD inference, kalkulasi margin PPFG, drilling risk engine | `ml` (inference), `api`, `anomaly` |
| 5 — RTO dashboard | dashboard, event review, alerts, audit, export | `dashboard`, `report`, `api` |

```
┌──────────────────────────────────── Docker Compose ─────────────────────────────────────┐
│  [etl]  zip LAS/CSV · alias · QC · sync · state ──► [db] TimescaleDB + Parquet + versi   │
│     ▲ zip Navita                                         │                               │
│                                   [ml] training · inference ─► [mlflow] registry          │
│                                   [anomaly] baseline · rules · score · cut-off           │
│  browser ◄── [dashboard] ◄── [api] FastAPI: data, prediksi, margin, alert, audit         │
│                               [report] PDF/PPTX/DOCX (+ AI eksternal untuk narasi)        │
│                               [jupyter] (dev)                                             │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

API utama: `POST /ingest`, `GET /wells`, `GET /wells/{id}/timeseries`, `POST /predict`, `GET/PUT /wells/{id}/ppfg` (+ approval), `GET/PUT /wells/{id}/mudweight`, `POST /anomaly/run?cutoff=`, `GET/POST /events` (+ review), `POST /backtest`, `POST /models/{id}/promote|rollback`, `POST /report`, `GET /audit`.

### 9.2 Pemetaan dashboard [PHR 9.2]

**Enam dashboard inti (proposal)**, dengan tambahan kebutuhan production:

| # | Dashboard | Fungsi | Tambahan kebutuhan production [PHR 4.3, 9.2] | Masukan klien yang ditampung |
|---|---|---|---|---|
| 1 | **Live Monitor** | ECD aktual/prediksi, margin, alert card | timestamp freshness, latency, stale-data badge, confidence, source quality, no-data state, model version, operational state, **last valid prediction vs current estimate** | track multi-channel satu sumbu ala template Navita, skala per channel bisa diatur, Picker/Realtime/Latest Scroll/Show All, log format + kolom ALERT, flow out %/pit/gain-loss |
| 2 | **Profil Depth** | ECD, MW, PP, FG (+ SFG) vs depth | switch MD/TVD, PPFG berversi, batas section/shoe, exposure interval, uncertainty, depth reference | evaluasi MW statis vs SFG (MWW), mode Rencana MW |
| 3 | **Riwayat Event** | kelola label engineer | engineer confirmation, incident type, **label confidence**, review workflow, evidence traceability, audit | label pack-off / tight hole / sloughing / loss / influx / stuck / noise |
| 4 | **Data & Upload** | ingest Record 01–07 | Rec 01/02 time/depth, 03/04/07 depth, schema QC, source lineage, clock drift, target availability | upload zip apa adanya, folder pantau, room otomatis |
| 5 | **Formasi & FG** | versi PPFG | effective date, **approver**, interval applicability, TVD datum, uncertainty | import Rec 03/04, bandingkan versi |
| 6 | **Model ML** | eksperimen, benchmark, SHAP | blind-well metrics, data lineage, **promotion gate**, rollback, group split, confidence, registry | penjelasan ekspektasi "≈100 %" vs blind-well |

**Halaman pendukung** (permintaan klien, tidak bertentangan dengan proposal):

| Halaman | Alasan | Acuan |
|---|---|---|
| Login | akun lokal (keputusan klien 21 Nov) dan pembatasan hak akses | [PHR 9.3] |
| Overview multi-room | 10+ rig bersamaan, room tidak dibatasi | chat klien |
| Analisis Anomali | UI modul stuck-pipe (Bab 8.3): cut-off, baseline, indikator "sejak jam", lead time. Label tampilan "modul tambahan · hipotesis H4" | [PHR 1.6, 8.3] |
| Laporan | laporan & slide studi kasus dengan narasi dibantu AI. Mendukung deliverable *pilot report* | [PHR 1.5], chat klien |
| Pengaturan | ambang (dengan approval), preset skala, user, AI | [PHR 8.4, 9.3] |

**Backlog di luar proposal** (tidak dibangun tanpa persetujuan, Lampiran H C6): panel what-if, proyeksi ECD per depth, citra cutting (CNN cavings), dan notifikasi WhatsApp/Telegram.

### 9.3 Reliability dan keamanan [PHR 9.3]

| Kebutuhan proposal | Implementasi |
|---|---|
| **Degraded mode** saat telemetry MWD hilang | ECD ⓥ menggantikan ⓜ secara otomatis dengan label jelas. Jika input rig juga hilang → ⚫ Unavailable |
| Membedakan **last valid prediction** dari **current estimate** | Live Monitor menampilkan "terakhir valid 19:42 (18 mnt lalu)" terpisah dari angka saat ini |
| Membatasi hak akses | **Login akun lokal** (password ter-hash), peran per Bab 10.2, hak akses per room. Integrasi akun PHR (SSO) belum ada tetapi disiapkan |
| Menyimpan versi model/data & audit trail | MLflow registry, versi PPFG/MW, audit log setiap aksi (upload, ack, label, approval, promote) |
| Kebijakan keamanan data PHR; data transfer disetujui pemilik sistem | Deployment di server yang ditentukan PHR (Lampiran H F1). **Narasi laporan memakai layanan AI eksternal** (disetujui klien 21 Nov 2026): yang dikirim hanya **ringkasan hasil analisis** (waktu, depth, indikator, angka ringkas), bukan file mentah Navita. Fitur dapat dimatikan, kunci API disimpan di server, narasi selalu diedit/dikonfirmasi manusia, dan bisa diganti ke AI lokal bila kebijakan berubah |

---

## Bab 10 — Implementation Roadmap

| Fase [PHR 10] | Aktivitas | Gate | Rencana waktu (usulan, Lampiran H G2) |
|---|---|---|---|
| **0 — Scoping** | owner, akses data, daftar sumur, KPI, use case. **Persetujuan dokumen ini** | **Scope approved** | sekarang (Nov 2026) |
| **1 — Data readiness** | record mapping (5 record), QC, time–depth alignment, data dictionary, operating state, katalog event awal | **Data QC sign-off** | akhir Nov |
| **2 — Offline modeling** | baselines, RF/XGB/LGBM (± LSTM, hybrid), blind-well test, margin PPFG. **Studi kasus retrospektif PDSI 53.2 & GW339** (modul stuck offline, K4) | **Model performance reviewed** | akhir Nov – awal Des |
| **3 — Shadow mode** | inferensi live **tanpa tindakan operasional** di GW339, GW337 (+ sumur berjalan berikutnya) | **Alarm/latency/quality acceptable** | mulai awal Des (setelah gate Fase 2) |
| **4 — Controlled pilot** | alert dibantu RTO engineer | **Pilot review & HSE approval** | menyusul |
| **5 — Scale-up** | lebih banyak rig/section, monitoring drift, governance | **Production change approval** | menyusul |

> Klien meminta fokus dua kasus sebelum operasional awal Desember. Studi kasus itu ditempatkan di **Fase 2 sebagai analisis offline**. Hal ini sesuai prinsip proposal: data readiness dan audit label diprioritaskan, dan classifier stuck pipe tidak dibangun sebelum label cukup [PHR 12.3]. Shadow mode baru dimulai setelah gate Fase 2 terpenuhi.

### 10.1 Deliverables per fase [PHR 10.1]

| Fase | Deliverables |
|---|---|
| 0 | dokumen desain disetujui, daftar sumur prioritas, daftar keputusan (Bab 12.2) |
| 1 | **source-to-target mapping**, **data dictionary**, **QC report**, data readiness matrix, missingness map |
| 2 | **EDA report**, **trained model registry**, **validation pack** (Appendix B per sumur), laporan studi kasus 53.2 & GW339 |
| 3 | **dashboard configuration**, **event taxonomy**, log alarm/latency, feedback engineer |
| 4 | **SOP/response guide**, **pilot report** |
| 5 | **handover package** (manual pengguna tanpa Python, manual instalasi Docker, runbook retraining) |

Durasi dan jumlah sumur pilot ditetapkan bersama PHR sesuai akses data dan kesiapan infrastruktur.

### 10.2 Peran dan tanggung jawab [PHR 10.2]

| Peran proposal | Tanggung jawab | Peran di aplikasi | Hak utama di sistem |
|---|---|---|---|
| **Drilling Engineering** | acceptance criteria & technical review | Engineer (reviewer) | review evaluation report, setujui ambang (bersama HSE) |
| **RTO** | operational monitoring, event verification, usability | RTO | semua room, upload, ack alert, label event, laporan |
| **Mud Engineering** | validasi mud properties/rheology | Engineer (Mud) | setujui aturan effective-from MW, input reologi |
| **Geomechanics** | version control PPFG | Engineer (Geomech) | **approve versi PPFG** |
| **Directional/MWD** | survey, label ECD, telemetry QC | Engineer (MWD) | konfirmasi provenance label ECD, validasi survey |
| **Data/ML team** | pipeline, reproducibility, deployment, drift | Admin | training, promote/rollback, user, konfigurasi |
| **HSE/Well Control** | review alarm boundaries & escalation | Reviewer HSE | setujui batas alert & eskalasi |
| *(rig, dari chat klien)* | melihat kondisi rig sendiri | Viewer rig | lihat room rig-nya, acknowledge |

---

## Bab 11 — Expected Benefits & KPIs

### 11.1 Manfaat yang ditargetkan [PHR 11.1]

Manfaat potensial: visibilitas ECD saat PWD tidak tersedia, evaluasi tren ECD lebih cepat, transparansi uncertainty, dukungan penilaian loss risk, dan konsolidasi data RTO. **Reduksi NPT atau insiden belum dapat diklaim** sebelum pilot dan baseline historis yang sebanding tersedia.

| KPI | Definisi | Sumber bukti | Dicatat di |
|---|---|---|---|
| ECD MAE/RMSE | error pada blind wells (ppg) | label PWD + prediction log | Model ML |
| P95 absolute error | ekor error, termasuk interval narrow-margin | evaluasi blind-well | Model ML |
| Inference latency | delay source-to-display | system log | Live Monitor (badge latency) |
| Data availability | % waktu fitur kritis valid | QC dashboard | Data & Upload |
| Loss alert recall | event loss terverifikasi terdeteksi / semua event terverifikasi | event review engineer | Riwayat Event |
| False alarm burden | false alert per rig-day | alert + review log | Riwayat Event |
| Stuck warning lead time | waktu antara warning dan onset terverifikasi | incident review | Analisis Anomali |
| Adoption | acknowledgment / review completion | RTO usage log | audit log |

### 11.2 Evaluasi nilai ekonomi [PHR 11.2]

Skenario dihitung terpisah: avoided event duration × validated cost rate, waktu monitoring yang dihemat, dan biaya inkremental sistem. **Tidak diasumsikan setiap alarm mencegah NPT.** Dipakai before–after dengan kontrol untuk perbedaan sumur, hole size, formasi, dan praktik operasi. Evaluasi ini dilakukan di Fase 4–5.

---

## Bab 12 — Conclusions & Recommendations

### 12.1 Kesimpulan [PHR 12.1]

Empat studi memberi dasar ilmiah untuk menguji prediksi ECD dengan ML dan untuk integrasi batas geomekanika. Kontribusi spesifik PHR adalah:
- pipeline multi-record dengan dua representasi (time/depth);
- blind-well validation;
- pemisahan prediksi ECD dari batasan PPFG;
- integrasi monitoring dan event review.

Semua hasil lapangan masih menunggu eksperimen terkontrol.

### 12.2 Keputusan yang diperlukan [PHR 12.2]

| Keputusan proposal | Status per 21 Nov 2026 | Lampiran H |
|---|---|---|
| Persetujuan data owner Record 01, 02, 03, 04, 07 | data 9 sumur + 2 sumur uji sudah diterima; persetujuan formal? | A15 |
| Daftar sumur prioritas & interval PWD | prioritas: PDSI 53.2, GW339; shadow: GW339, GW337; blind: BDSI 60. Interval PWD per sumur perlu konfirmasi | A16, E3 |
| Definisi ECD label | usulan: ECD Rec 02 lolos quality flag, pumps on, provenance terkonfirmasi | A13, A17 |
| Baseline hydraulic yang berlaku | **belum ada**: butuh reologi/geometri atau model hidraulik PHR | A14 |
| Data loss/stuck incident terverifikasi | PDSI 53.2 (laporan PPTX) ada; GW339 & 9 sumur training diminta | A10, A11 |
| Persetujuan threshold alarm & pilot acceptance criteria | usulan default di Bab 8.4, menunggu Drilling Eng + HSE | B2–B5, E2 |

### 12.3 Prioritas langkah pertama [PHR 12.3]

1. **Data readiness dan audit label** pada satu atau dua area/well families (Balam SE: GW339 & PDSI 53.2; Minas: BDSI 18/19/21).
2. **Tunjukkan perbaikan blind-well** terhadap baseline (MW-only, hidraulik), lalu jalankan shadow mode.
3. **Modul stuck-pipe** tetap analisis offline (studi kasus) dan shadow. Modul baru dipromosikan bila lead time dan beban false alarm layak bagi RTO.

---

## Referensi Utama

1. Alsaihati, A., Elkatatny, S., & Abdulraheem, A. (2021). Real-Time Prediction of Equivalent Circulation Density for Horizontal Wells Using Intelligent Machines. *ACS Omega*, 6, 934–942. DOI: 10.1021/acsomega.0c05570
2. Ekechukwu, G., & Adejumo, A. (2024). Explainable machine-learning-based prediction of equivalent circulating density using surface-based drilling data. *Scientific Reports*, 14, 17780. DOI: 10.1038/s41598-024-66702-w
3. Chen, Y., et al. (2025). Prediction of Mud Weight Window Based on Geological Sequence Matching and a Physics-Driven Machine Learning Model for Pre-Drilling. *Processes*, 13, 2255. DOI: 10.3390/pr13072255
4. Leerojanaprapa, K., Suttaloon, S., Bhundarak, K., & Sirikasemsuk, K. (2026). Modeling Equivalent Circulating Density During Drilling Operations in the Gulf of Thailand. *International Journal of Technology*, 17(2), 357–375. DOI: 10.14716/ijtech.v17i2.7897
5. PHR. Technical Proposal: Machine Learning-Based Real-Time ECD Prediction, Bab 1–12 (revised technical draft, 20 Nov 2026). **Acuan utama.**
6. Proposal Prognosis ECD Berbasis Machine Learning — Kasus GW-339/BLSE-0056 (draf kajian teknis, 21 Nov 2026).
7. Chronology Stuck 8-1/2" TCB on Rotary BHA, Well Balam SE-57 HW MSF, Rig PDSI #53.2 (7 Nov 2026).

---

## Appendix A — Data Dictionary

Template mengikuti [PHR Appendix A], diisi dengan tag Navita yang ditemukan di file. Daftar lengkap (semua channel, alias antar rig, aturan download) ada di **`CHANNELS.md`**.

| Field (canonical) | Unit | Record | Tag asli Navita (alias) | Validasi |
|---|---|---|---|---|
| `well_id` | text | All | `WID`, header `WELL` | canonical ID (koreksi `Kopar-52`, `P_BLSE27_0003HW_MSF`) |
| `event_time` | ISO 8601 (UTC) | 01/02 | `dtsrv` (PDSI 53.2: `TIME` epoch) | timezone, clock offset, gap flag |
| `bit_depth_md` | ft | 01/02 | `DBTM` (`DEPTBITM`) | monotonik per operasi; LAS `.m` = ft |
| `hole_depth_md` | ft | 01/02 | `DMEA` (`DEPTMEAS`) | ≥ bit depth |
| `ecd_actual` | ppg | 02 | `ECD` | kualitas sensor PWD, rentang fisik 7–20 ppg (usulan), pumps on |
| `annular_pressure` | psi | 02 | `ANP` | cek ECD ≈ ANP/(0,052×TVD_sensor) |
| `flow_in` | gpm | 01 | `MFIA` | pump state |
| `flow_out_pct` | % | 01 | `MFOP` | 0–100 |
| `active_pit` | bbl | 01 | `TVA` (`TVOLACT`, jumlah tank aktif GW339) | pemetaan tank aktif per rig |
| `spp` | psi | 01 | `SPP` (`SPPA`) | validitas sensor, offset negatif |
| `hookload` | klb | 01 | `HKLA` (`HOOKLOAD`) | rentang fisik |
| `torque` | kft·lb | 01 | `TORQUE` (`TORQA`) | frozen/spike |
| `rpm` | rpm | 01 | `RPM` (`RPMA`) | ≥ 0 |
| `wob` | klb | 01 | `WOB` | offset negatif |
| `rop` | ft/h | 01 | `ROP` | ≥ 0 |
| `block_pos` | ft | 01 | `BPOS` (`BLKPOS`) | rentang |
| `mud_weight` | ppg | 04 | `MUDWEIGHT` | effective depth / version / effective-from |
| `pp`, `sfg`, `fg_min` | ppg | 03 | `PP`, `SFG`, `FGMIN` | versi PPFG approved, TVD datum |
| `tvd` | ft | 07 | `DSVV` (cek `DVER` Rec 02) | interpolasi survey |
| `inclination` | degree | 07 | `SINC` | validitas survey |
| `dls` | °/100 ft | 07 | `SDLS` | — |
| `operating_state` | kode | turunan | `ACTC` bila terisi, atau aturan Bab 6.3 | konsistensi dengan flow/depth |

---

## Appendix B — Evaluation Report Template

Satu laporan per well/section [PHR Appendix B]. **Tidak ada angka hasil aktual sebelum validasi.**

| Bagian | Isi |
|---|---|
| Identitas | well identifier, hole size/section, mud system, peran (training / blind) |
| Data | label coverage (% waktu dengan ECD valid), operating states tercakup, data availability, eksklusi & alasan |
| Model | versi model, konfigurasi input (surface-only / sensor-enhanced), versi data & PPFG |
| Metrik regresi | MAE, RMSE, R², P90/P95 error, bias, % dalam toleransi, per operating state; perbandingan dengan baseline A |
| Grafik | actual vs predicted, residual by depth/flow/section, distribusi error, kalibrasi, SHAP |
| Alarm | jumlah alarm per tingkat, false alerts per rig-day, recall/precision event, lead time (hanya untuk event warning) |
| Review | catatan engineering review, keputusan (lolos/tidak), **sign-off** (nama, peran, tanggal) |

---

## Appendix C — Formulas & Interpretation

```
ECD (ppg)          = MW (ppg) + ΔP_annular (psi) / [0.052 × TVD (ft)]
ESD (pumps off)    ≈ MW
Hidrostatik (psi)  = 0.052 × MW × TVD
ECD dari PWD       = ANP (psi) / [0.052 × TVD_sensor (ft)]
Upper margin (ppg) = FG_min − ECD_pred
Lower margin (ppg) = ECD_ref − batas_bawah   (batas_bawah = max(PP, SFG), usulan)
Static margin (ppg)= MW − batas_bawah         (pumps off)
Hybrid             : ECD_pred = ECD_hydraulic + ML_residual
```

- Formula mengasumsikan tekanan dan referensi kedalaman yang konsisten. Operasi transien, swab/surge, dan efek termal memerlukan interpretasi tambahan [PHR App. C].
- **Margin kecil atau negatif adalah *screening signal***. Respons formasi aktual memerlukan evaluasi uncertainty, interpretasi FIT/LOT, dan bukti dari returns/pit/flow.

---

## Lampiran D — Studi Kasus Awal

Atas permintaan klien, dua kasus dikerjakan terlebih dahulu. Keduanya adalah uji awal hipotesis, **bukan bukti** sistem mampu memprediksi stuck pipe. Pemetaan lengkap ada di Bab 4.4.

| Kasus | Status sumur | Jenis uji | Hipotesis |
|---|---|---|---|
| D.1 PDSI 53.2 | **selesai (statis)** | retrospektif offline, mode cut-off (Fase 2, K4) | PHR-H4 |
| D.2 GW339 | **berjalan (dinamis)**; run 6-1/8" rotary BHA tanpa tool ECD karena isu sloughing | retrospektif untuk data yang sudah ada + **shadow mode** live (Fase 3) | PHR-H1–H3 (nilai ECD prediksi tanpa PWD), H4 pendukung |

### D.1 PDSI 53.2 — Balam SE-57 HW MSF (past, stuck pipe)

**Pendekatan utama H4 untuk kasus ini (usulan klien, 21 Nov 2026):** run BHA #4 tidak punya ECD terukur. Sistem memplot **tren ECD prediksi ⓥ** sepanjang run (berbasis waktu, di bit depth). **Spike atau kenaikan ECD ⓥ mendadak** pada flow/RPM yang sama dijadikan **pintu masuk** indikasi pack-off / hole problem, lalu dicek silang dengan indikator mekanik (tabel detektor Bab 8.3). Hasilnya dibandingkan dengan **report PHR yang sudah dirilis** sebagai ground truth: jam spike pertama vs kronologi kejadian → lead time.

**Kronologi (laporan PPTX, 7 Nov 2026, TIH 8-1/2" TCB Rotary BHA #4):**

| Waktu (WIB) | Kejadian |
|---|---|
| 08:10 | Tag 8 klb @3.341 ft MD; wash down 200 gpm, wash up 600 gpm; baseline TIH pump off OK. Foto spot cutting @3.341 ft |
| 09:15 | Tag 8 klb @3.796 ft; ream down 20 rpm, 200–400 gpm |
| 10:20 | Tag 8 klb @3.746 ft, tag lagi @3.705 ft; wash down 180–400 gpm |
| 11:55 | Tag 8 klb @4.566 ft; reaming up/down |
| 12:46 | Tag 8 klb @4.606 ft; cutting sedikit, ada **medium sloughing** (ukuran kecil) |
| 13:51 | Tag 8 klb @5.076 ft; wash down 200 gpm / 230 psi; back reaming 20 rpm, torque 2,8–3 kft·lb, 600 gpm / 1.060 psi |
| ±14:30 | **Overpull** saat back reaming @5.093 ft, **rotasi berhenti mendadak, torque naik**; pick up 580–600 gpm / 1.170 psi, **MFO turun (losses)**; flow 100 gpm, string tidak bisa diputar |
| 14:50 | **Stuck @5.051 ft MD** |

Konteks:
- MW in/out 10,2 ppg.
- Dynamic loss 13–15 bph; static loss 0,8 bph saat trip sebelumnya.
- Baseline PU/SO/RO pump on: 130/110/120 dan 133/112/93 klb.
- Caliper fluida AHS 9,6".

**Rencana analisis (mengikuti Bab 8.3 & 4.5A):**
1. Ingest LAS/CSV lewat alias mnemonic. Karena ECD = 0, dipakai **ECD prediksi ⓥ** tanpa klaim akurasi.
2. Susun **katalog event** dari laporan: onset, MD, mode, kategori (mechanical/tight hole → stuck), dan confidence label.
3. Buat baseline mekanik dari periode normal (6 Nov – pagi 7 Nov) dan dari baseline PU/SO/RO laporan.
4. **Cut-off 7 Nov 12:00**: engine hanya memakai data ≤ 12:00. Hasilnya: indikator aktif, **sejak jam berapa**, dan risk score.
5. Verifikasi dengan data sesudah cut-off dan kronologi. Hasilnya: **lead time** terhadap 14:50 dan eskalasi; **false alarm per hari** di periode normal.
6. Bila tersedia, integrasikan Rec 01–07 versi Navita (resolusi 1 dtk, TVD, PPFG, MW).
7. Hasil disajikan dalam laporan dan slide yang ditandai *hipotesis penelitian*.

**Kerangka studi kasus H4 dari klien:**
- Data historis **7–9 Nov 2026** dipakai untuk merekonstruksi perubahan hookload, torque, RPM, SPP, flow rate, dan ECD (bila ada), dengan integrasi Record 01, 02, 03, 04, dan 07.
- Yang dievaluasi: apakah ada pola hidraulik dan mekanik yang konsisten sebelum stuck, dan apakah pola itu layak dijadikan indikator peringatan dini.
- Validasi lanjutan memakai beberapa sumur historis **dengan kejadian normal dan stuck**.
- Tujuan jangka panjang: **integrated drilling risk monitoring** untuk RTO dan Drilling Engineering.
- Kalimat final dikonfirmasi klien bersama koordinator jaga malam.

### D.2 GW339 — BLSE-056 (present, sloughing / partial pack-off)

> Mengintegrasikan **Proposal Prognosis ECD-ML Kasus GW-339/BLSE-0056, 6-1/8"** [GW §1–10]. Proposal ini merupakan bahan diskusi teknis, bukan hasil model atau instruksi operasi.

**a. Ringkasan [GW §1].**
- Drilling 8-1/2" mencapai TD 5.651 ft MD. Shoe casing 7" ada di 5.348 ft MD, sehingga tersisa **rathole ±303 ft**.
- Saat cleanout dengan BHA 6-1/8" muncul **dugaan sloughing dan indikasi partial pack-off**.
- **Belum ada bukti** model mampu memprediksi kejadian ini.

**b. Fakta operasional dari snapshot [GW §2].**

| Indikator | Nilai |
|---|---|
| TD 8-1/2" | 5.651 ft MD; MW 10,4 ppg |
| Shoe 7" | 5.348 ft MD; open hole 303 ft |
| Cleanout rotary BHA 6-1/8" | s.d. 5.534 ft; MW 10,0 ppg |
| Cleanout MWD BHA 6-1/8" | s.d. 5.558 ft; MW 10,0 ppg |
| Progres | +24 ft; indikasi partial pack-off |
| P/U | normal 106 klb, tercatat 150 klb → **overpull +44 klb** |
| Tekanan | spike 2.025 psi; baseline tidak tersedia |
| Torque | spike 7–15 kft·lb |

**Riwayat MW** (snapshot):
- 10,1 ppg di 4.183–4.687 ft
- 10,2 ppg di 4.876–5.351 ft
- 10,3 ppg di 5.414–5.477 ft
- 10,4 ppg di 5.651 ft

**Waktu perubahan MW tidak diketahui**, sehingga aturan effective-from (Bab 4.2A) perlu data waktu efektif.

**c. Hipotesis mekanisme [GW §3]:**

| Kode | Hipotesis | Bukti yang dicari |
|---|---|---|
| GW-H1 | instabilitas shale: cavings menumpuk di rathole | MW vs SFG di open hole, durasi pumps off, cavings, caliper |
| GW-H2 | akumulasi cutting | tren P/U–S/O & torque naik bertahap, residual SPP positif, flow/RPM rendah |
| GW-H3 | restriksi annulus / partial pack-off | SPP spike di flow tetap, flow out % turun, torque spike, overpull |
| GW-H4 | kondisi operasi (MW 10,4 → 10,0, flow, RPM, ROP); **kausalitas belum terbukti** | perbandingan sebelum/sesudah per operating state |
| Alternatif | ledge, debris semen, tight hole, geometri BHA, differential sticking | depth vs shoe/top semen, tag berulang di depth sama, pipa diam lama, perubahan BHA |

**d–e. Rancangan prognosis & alur deteksi [GW §4–5].** Model dasar hidraulik/reologi + ML residual; tahap Baseline → Anomali → Prognosis → Keputusan. Rancangan ini diadopsi di Bab 8.3. Horizon prognosis: proposal GW339 menyebut 5/15/30 mnt, sedangkan proposal PHR menyebut 5–15 mnt sebagai fase terpisah [PHR 5.1] (Lampiran H B11).

**f. Dukungan keputusan lapangan [GW §6]:**

```
Cek sloughing tanpa pompa s.d. 5.558 ft
  └► terkonfirmasi? ─► POOH motor + MWD BHA ─► run kembali rotary BHA 6-1/8"
        └► berhasil s.d. 5.558 ft? ─► washdown terkontrol s.d. 5.651 ft (pantau ketat + RTO)
              └► berhasil? ─► lanjut drilling 180 ft untuk RSS pad
  Setelah cleanout: lanjut BHA #2/#3 ATAU sidetrack
```

Peran sistem di tiap langkah:
1. Margin statis MW vs SFG dan durasi pumps off.
2. Baseline P/U–S/O–torque–SPP per depth, dengan warning tag/overpull/pack-off secara live (shadow).
3. Laporan tren dan risk score per interval sebagai bahan keputusan.

**Keluaran ML tidak boleh diperlakukan sebagai izin otomatis melanjutkan operasi** [GW §6, PHR 4.6].

**g. Validasi retrospektif [GW §7] (selaras [PHR 4.5A]):**
1. Siapkan data **≥ 24–48 jam sebelum indikasi abnormal pertama sampai POOH**, dengan anotasi kronologi dan operating state.
2. Tandai onset dari DDR, catatan RTO, dan sensor. Fitur pasca-kejadian tidak boleh dipakai (cut-off).
3. Bandingkan **baseline hidraulik vs residual ML vs anomali multivariat**.
4. Laporkan lead time, recall, false alarm per hari, precision, kalibrasi, dan hasil per operating state.
5. Uji sensitivitas MW 10,0 vs 10,4 ppg **hanya setelah** reologi, PPFG, dan model hidraulik tervalidasi. MW lebih tinggi tidak otomatis menurunkan risiko.

**h. Kesenjangan data [GW §8], status 21 Nov:**

| Data | Status |
|---|---|
| Log depth–time | ✅ Rec 01/02 s.d. 20 Nov |
| TVD & survey | ✅ |
| PPFG (SFG sebagai collapse) | ✅ |
| MW | ✅ |
| **ECD/PWD run 6-1/8"** | ❌ kosong |
| Baseline SPP/flow | diturunkan dari periode normal |
| Laporan casing/cementing, waktu efektif MW, reologi & temperatur, BHA tiap run, foto cavings/returns, DDR | **diminta** |

**i. Usulan narasi kepada PHR [GW §9]** (kerangka laporan; kalimat final dikonfirmasi klien/koordinator):

> *"Kasus GW-339/BLSE-0056 memberikan kesempatan validasi nyata bagi hipotesis sistem peringatan dini ECD Machine Learning. Setelah casing 7 inci tertahan pada sekitar 5.348 ft MD, tersisa interval terbuka 303 ft hingga TD seksi 8-1/2 inci. Pada cleanout BHA 6-1/8 inci, ditemukan indikasi sloughing/partial pack-off, dengan overpull 44 kip serta spike tekanan dan torque. Kami mengusulkan evaluasi retrospektif gabungan ECD, SPP, torque, drag, mud weight, dan kondisi operasi untuk menguji apakah sistem mampu mengenali perubahan risiko sebelum gangguan teridentifikasi secara operasional. Hasilnya akan dinilai berdasarkan lead time, tingkat deteksi, dan alarm palsu, bukan hanya akurasi prediksi ECD."*

Karena run 6-1/8" tanpa ECD terukur, kata "ECD" pada narasi di atas berarti ECD prediksi ⓥ ditambah indikator SPP/torque/drag/MW.

**j. Sumber [GW §10].** Proposal disusun dari dua snapshot operasional, 21 Nov 2026. Seluruh interpretasi masih hipotesis.

**k. Gambaran operasi 20 Nov dari data Navita:**

| Jam | Aktivitas (dibaca dari data) | Catatan |
|---|---|---|
| 00:00–04:17 | bit di 78 ft, pompa mati | trip tank 6–41 bbl |
| 04:17–06:01 | **tidak ada data** | gap |
| 06:00–14:00 | TIH 78 → ±5.400 ft, wash berkala 230–300 gpm, SPP s.d. ±1.400 psi | |
| 14:00–19:00 | wash/ream sekitar shoe (5.348 ft) s.d. 5.537 ft; SPP s.d. **2.846 psi**, RPM s.d. 32 | Flow Out % s.d. 65 % |
| 19:00–24:00 | sirkulasi ±231 gpm, cleanout hole depth **5.539 → 5.559 ft**, torque s.d. **15 kft·lb**, hookload s.d. **149 klb** | cocok dengan snapshot |

**l. Rencana analisis sistem:**
1. **Data readiness**: Rec 01/02 (27 Okt – 20 Nov + harian) dan Rec 03/04/07; QC sesuai Bab 6.2 no. 11–14.
2. **Pressure window**: MW 10,0 vs batas bawah di rathole 5.348–5.651 ft, dibandingkan periode MW 10,4. Tidak ada klaim kausal.
3. **Baseline (Tahap A)**: P/U, S/O, RO, torque, SPP vs flow per depth dan state (P/U normal 106 klb).
4. **Anomali (Tahap B)**: GW-H2/H3 → indikator dan waktu mulainya; uji alternatif (ledge/debris di shoe, differential).
5. **Skor (Tahap C)**: risk score restriksi. Prognosis horizon belum dilaporkan.
6. **Validasi** sesuai butir g, lalu **shadow mode** live dengan data harian (Fase 3).

---

## Lampiran E — Alur Pengguna (Tutorial)

Lampiran ini menggambarkan cara sistem dipakai dari login sampai output, supaya klien bisa membayangkan sistem sebelum dibangun. Semua dilakukan lewat browser tanpa menulis kode. Nama halaman mengikuti Bab 9.2 dan `UI_MOCKUP.md`.

### E.1 Peta tutorial

```
 [Login] ─► Overview ─┬─► T-B Siapkan sumur baru (Data & Upload → Formasi & FG [approve Geomech])
                      ├─► T-C Pantau harian (Live Monitor: track, Picker, skala, log format)
                      ├─► T-D Tindak lanjut alert (Live Monitor → Profil Depth → Riwayat Event)
                      ├─► T-E Studi kasus retrospektif (Analisis Anomali → Cut-off → lead time)
                      ├─► T-F Laporan / slide (Laporan)
                      ├─► T-G Update & approve PPFG / MW (Formasi & FG)
                      └─► T-H Sumur selesai → model kandidat → promotion gate (Model ML)
```

### E.2 Tutorial A — Login & Overview *(semua peran)*

| Langkah | User | Sistem |
|---|---|---|
| 1 | buka alamat sistem di browser | halaman **Login** |
| 2 | isi username & password **akun lokal** (dibuat Admin) → **Masuk** | cek akun, peran, dan room yang boleh dilihat |
| 3 | — | **Overview**: kartu semua room aktif, paling berisiko di kiri |
| 4 | baca kartu | tingkat alert 🟢🟡🟠🔴⚫, indikasi aktif + "sejak jam", ECD ⓜ/ⓥ vs FG_min, **umur data**, versi model |
| 5 | klik kartu | masuk **Live Monitor** room itu |

```
┌──────────────── Login ────────────────┐
│  ECD Monitor — PHR Drilling / RTO     │
│  Username [______________]            │
│  Password [______________]            │
│  [ Masuk ]   (akun lokal dari Admin)  │
└───────────────────────────────────────┘
```

**Output:** dalam < 1 menit user tahu sumur mana yang perlu perhatian.

### E.3 Tutorial B — Menyiapkan sumur baru *(RTO; approval Geomechanics & Mud Eng)*

| Langkah | User | Sistem |
|---|---|---|
| 1 | di Navita: download Rec 01 & 02 (time + depth), Rec 03, 04, 07 → `.zip` | — |
| 2 | **Data & Upload** → tarik semua zip | membuka zip, mengenali record & basis, alias mnemonic |
| 3 | konfirmasi "Buat room GW339 / BLSE-056?" | room dibuat |
| 4 | baca **laporan QC** | kelengkapan record, cek channel ✅/⚠/❌, gap, clock offset, **target availability** ("ECD kosong → ECD ⓥ"), lineage |
| 5 | **Formasi & FG** | PPFG & MW terisi dari Rec 03/04 dengan status **"draft, menunggu approval"** |
| 6 | Geomechanics: **Approve versi PPFG**. Mud Eng: setujui aturan effective-from MW | versi aktif tercatat (approver, tanggal) |

**Output:** room siap, Live Monitor aktif, dan laporan QC (deliverable Fase 1).

### E.4 Tutorial C — Pemantauan harian *(RTO, viewer rig)*

| Langkah | User | Sistem |
|---|---|---|
| 1 | upload data terbaru (atau folder pantau) | data disambung, overlap dibuang, prediksi & alert dihitung |
| 2 | **Live Monitor → Realtime** | track multi-channel satu sumbu ala Navita: ROP, Flow, RPM, Hookload, Block, SPP, Torque, WOB, ECD ⓜ/ⓥ + interval, FG_min, SFG, MW, Flow Out %, Active Pit, Gain/Loss, marker alert |
| 3 | pilih **Preset** atau atur skala channel (ketik / Auto / kunci skala ppg) | resolusi channel berubah |
| 4 | geser **Picker**, **Latest Scroll**, **Show All** | rentang waktu berubah |
| 5 | baca **header status** | freshness/latency, versi model & PPFG, completeness, operating state, last valid vs current |
| 6 | (opsional) **log format** (waktu ↓) | track vertikal + kolom ALERT |

**Output:** kondisi sumur saat ini dan beberapa jam ke belakang dalam satu layar.

### E.5 Tutorial D — Menindaklanjuti alert *(RTO)*

| Langkah | User | Sistem |
|---|---|---|
| 1 | menerima alert (kartu berubah 🟠/🔴, bunyi, atau email bila diaktifkan) | mis. "GW339 🟠 Warning: indikasi pack-off sejak 19:12 @5.540 ft" |
| 2 | klik alert | detail: indikator, **mulai sejak**, nilai vs baseline, channel bukti, data quality, **rekomendasi verifikasi** |
| 3 | **Profil Depth** | margin di bit & open hole, MW vs batas bawah, versi PPFG |
| 4 | verifikasi lapangan dengan tim; **keputusan tetap di tim drilling** | sistem tidak memberi perintah |
| 5 | **Acknowledge** + catatan | ack log |
| 6 | **Riwayat Event** → kategori + **label confidence** → kirim ke review | event menunggu konfirmasi engineer |

**Output:** event terdokumentasi dengan bukti, tindakan, dan label yang sudah direview.

### E.6 Tutorial E — Studi kasus retrospektif *(RTO/Engineer)*, contoh PDSI 53.2

| Langkah | User | Sistem |
|---|---|---|
| 1 | upload data 53.2 | dikenali "tanpa sensor ECD" → ECD ⓥ |
| 2 | **Analisis Anomali → Mode Cut-off = 07 Nov 12:00** | hanya data ≤ 12:00 dipakai |
| 3 | baseline **Auto** atau manual | baseline P/U, S/O, torque, SPP per depth/state |
| 4 | **Jalankan** | risk score vs waktu, tabel indikator & sejak jam berapa, kategori dugaan |
| 5 | tampilkan data setelah cut-off | verifikasi + **lead time** terhadap onset terkonfirmasi |
| 6 | geser cut-off (09:00, 10:00, 11:00) | kapan sistem pertama kali memberi tanda |
| 7 | **Simpan studi kasus** | masuk validation pack |

**Output:** "indikasi pertama jam X, eskalasi jam Y, lead time Z, false alarm/hari di periode normal", ditandai sebagai hipotesis.

### E.7 Tutorial F — Laporan / slide *(RTO/Engineer)*

| Langkah | User | Sistem |
|---|---|---|
| 1 | **Laporan** → pilih studi kasus / room + rentang | — |
| 2 | centang isi: kronologi, log + alert, tabel indikator & lead time, pressure window, metrik, keterbatasan | pratinjau |
| 3 | narasi **dibantu AI** (eksternal, hanya ringkasan hasil) atau manual | draf narasi + catatan "hipotesis penelitian" |
| 4 | edit → **Buat** → PDF / PPTX / DOCX | file |

**Output:** laporan yang dikirim **setelah dikonfirmasi** klien/koordinator.

### E.8 Tutorial G — Update PPFG / MW *(RTO → Geomechanics)*

| Langkah | User | Sistem |
|---|---|---|
| 1 | upload Rec 03/04 revisi | versi baru berstatus draft |
| 2 | **Bandingkan versi** | perbedaan per depth |
| 3 | Geomechanics **Approve** | margin memakai versi baru. **Model tidak dilatih ulang**. Event lama tetap dinilai dengan versi lamanya |

### E.9 Tutorial H — Sumur selesai & model baru *(Admin Data/ML → Drilling Eng)*

| Langkah | User | Sistem |
|---|---|---|
| 1 | data lengkap terupload, label event direview | room diarsipkan |
| 2 | **Model ML → Latih kandidat** | grouped CV + blind-well + evaluation report |
| 3 | Drilling Eng review laporan → setujui | gate: QC ✓ blind ✓ review ✓ |
| 4 | Admin **Promote ke Shadow** → setelah monitoring, **Production** | versi tercatat, rollback tersedia |

### E.10 Ringkasan

| Siapa | Halaman | Aksi | Output |
|---|---|---|---|
| Semua | Login → Overview | lihat room | sumur yang perlu perhatian |
| RTO | Data & Upload | upload zip | room + QC report |
| Geomech / Mud Eng | Formasi & FG | approve versi | batas berversi approved |
| RTO / viewer rig | Live Monitor | pantau | ECD, margin, alert, freshness |
| RTO | Profil Depth | cek window | margin bit & open hole |
| RTO | Riwayat Event | label + review | event terverifikasi |
| RTO / Engineer | Analisis Anomali | cut-off | lead time studi kasus |
| RTO | Laporan | buat laporan | PDF/PPTX/DOCX |
| Admin / Drilling Eng | Model ML | train, review, promote | model tervalidasi |
| Drilling Eng + HSE | Pengaturan | setujui ambang | ambang terdokumentasi |

---

## Lampiran F — Keterlacakan Proposal & Masukan Klien

### F.1 Proposal PHR → dokumen ini

| Proposal | Isi | Di dokumen ini | Di `UI_MOCKUP.md` / `TODO.md` |
|---|---|---|---|
| Bab 1 | ringkasan, scope, deliverables, stuck scope | Bab 1 | TODO §0 |
| Bab 2 | ECD, window, faktor, data, risiko, stuck | Bab 2 | — |
| Bab 3 | literatur & matriks bukti | Bab 3 | — |
| 4.1–4.2A | gap, Layer A–E, source register | Bab 4.1–4.2 | `CHANNELS.md` §1 |
| 4.3 | enam dashboard | Bab 4.3, 9.2 | UI §1–6 |
| 4.4 | H1–H4 | Bab 4.4 | — |
| 4.5 / 4.5A | validasi 5 tahap, stuck validation | Bab 4.5, 5.7 | TODO Fase 2 |
| 4.6 / 4.6A | advisory, atribut output, fase kapabilitas | Bab 4.6, 8.4 | UI header Live Monitor |
| Bab 5 | metodologi | Bab 5 | TODO Fase 1–2 |
| Bab 6 | data dictionary, QC, sinkronisasi 7 langkah, EDA, deliverables | Bab 6, App. A | `CHANNELS.md`, TODO Fase 1 |
| Bab 7 | eksperimen A–F, pelaporan, leakage, promotion | Bab 7, App. B | UI Model ML |
| Bab 8 | pressure window, loss/influx, stuck, alert policy | Bab 8 | UI Live Monitor, Analisis Anomali |
| Bab 9 | arsitektur, dashboard, reliability | Bab 9 | UI seluruh |
| Bab 10 | roadmap & roles | Bab 10 | TODO §1 |
| Bab 11 | KPI | Bab 11 | TODO Fase 3–4 |
| Bab 12 | keputusan & prioritas | Bab 12 | Lampiran H |
| App. A–C | dictionary, eval template, formula | App. A–C | `CHANNELS.md` |

### F.2 Masukan klien (chat & dokumen) → dokumen ini

| # | Masukan klien | Ditangani di | Status vs proposal |
|---|---|---|---|
| 1 | Sloughing saat pumps off (hanya MW menahan), umumnya di shale; saat pumps on mekanis | Bab 2.2, 8.1 (margin statis), 8.3 | sesuai (collapse limit [PHR 2.2]) |
| 2 | "Pre-drill" diganti MWW, aplikatif: MW terlalu rendah/tinggi | Bab 8.1 (MW statis, mode Rencana MW), Profil Depth | sesuai. Output berupa **rekomendasi verifikasi** [PHR 8.4] |
| 3 | FG Min = angka model reservoir saat akan drilling | Bab 2.2, Formasi & FG berversi | sesuai [PHR 2.5] |
| 4 | MW ada di record Navita (klien menyebut Record03) | Bab 4.2A (MW = Rec 04, sesuai proposal & file) | sesuai; Lampiran H A1 |
| 5 | Record 01, 02, 03, 07 (+04 MW, 08 di BDSI 18/19) | Bab 4.2A | 5 record proposal; Rec 08 opsional (A13) |
| 6 | Sumur berjalan GW339, GW337 (tanpa ECD); BDSI 60 sudah selesai → sumur testing (21 Nov) | Bab 4.4, 5.2, 10 Fase 3 | sesuai (shadow + blind) |
| 7 | Stuck pipe tanpa ECD: bisa memprofilkan bahaya? | Bab 8.3, Lampiran D.1 | modul tambahan H4 |
| 8–9 | Parameter permukaan diplot seperti ECD; template monitoring Navita; skala bisa diatur | Bab 9.2 #1, UI §1 | tambahan UI, sesuai |
| 10 | Data sejak Navita tersambung sampai rig pindah | `CHANNELS.md` §7 | sesuai |
| 11 | Picker waktu | Bab 9.2 #1 | sesuai |
| 12 | Proposal PHR Bab 1–12 | **acuan utama v3.0** | — |
| 13–14 | Anomali ECD sebagai alert awal; loss/stuck tidak dijelaskan jurnal | Bab 3.8, 8.2, 8.3 | sesuai [PHR 3.8] |
| 15 | Klien tidak memprogram Python | Lampiran E, handover Fase 5 | sesuai |
| 16 | Kemampuan menafsirkan personel berbeda | Bab 8.4 (alasan + rekomendasi verifikasi) | sesuai [PHR 8.4] |
| 17 | Tank volume & flow out = indikasi loss/gain | Bab 8.2 | sesuai |
| 18 | Download selalu .zip | Bab 4.2A, `CHANNELS.md` §7 | sesuai |
| 19 | 53.2: prediksi seolah jam 12:00, review mundur | Bab 8.3 (cut-off), Lampiran D.1, E.6 | sesuai (no look-ahead [PHR 5.4]) |
| 20 | GW339 time based s.d. tengah malam | Lampiran D.2 k | — |
| 21 | Room unlimited (10 rig, ±3 minggu) | Bab 9.2 (Overview) | tambahan, sesuai |
| 22 | Teks studi kasus H4 53.2 | Lampiran D.1 | sesuai [PHR 4.4A] |
| 23 | Output berupa alert, bukan log yang perlu tafsir | Bab 8.4, UI log format + ALERT | sesuai |
| 24 | Early sign "sejak jam berapa", bukan prediksi stuck | Bab 8.3 | sesuai (risk score + onset) |
| 25 | Proposal prognosis GW339 | Lampiran D.2 | horizon 30 mnt → B11 |
| 26 | Laporan + presentasi pakai AI | Bab 9.2 (Laporan), 9.3 | tambahan; AI eksternal disetujui 21 Nov |
| 27 | Narasi dikonfirmasi koordinator jaga malam | Lampiran D, E.7 | sesuai |
| 28 | 2 case: present & past, fokus 2 sumur | Bab 10 (Fase 2 offline), Lampiran D | disesuaikan [PHR 12.3] |
| 29 | 9 sumur "pasti mendekati 100 %" | Bab 2.5, 5.7 | dijelaskan: blind-well (E1) |
| 30 | Analisa realtime mulai awal Desember | Bab 10 Fase 3 | setelah gate Fase 2 (G2) |
| 31 | File GW339 20 Nov | Bab 6.2 no. 11–14, Lampiran D.2 k | — |
| 32 | Login akun lokal; AI eksternal boleh (21 Nov) | Bab 9.3 | sesuai [PHR 9.3] |
| 33 | Dokumen difix dulu mengikuti proposal sebelum sistem dibangun | seluruh v3.0 | — |

---

## Lampiran G — Glosarium

| Istilah | Arti |
|---|---|
| ECD / ESD | Equivalent Circulating / Static Density |
| ECD ⓜ / ⓥ | ECD terukur (PWD) / ECD prediksi model (nowcast) |
| Nowcast | estimasi nilai pada waktu t, bukan ramalan ke depan |
| MW | Mud Weight (Rec 04) |
| PP / SFG / FG_min | Pore Pressure / Shear Failure Gradient (collapse) / Fracture Gradient minimum (Rec 03) |
| PPFG | Pore Pressure & Fracture Gradient |
| MWW | Mud Weight Window: rentang MW antara batas bawah dan FG_min |
| Margin atas / bawah / statis | FG_min − ECD / ECD − batas bawah / MW − batas bawah |
| Open-hole exposed interval | interval tanpa casing dari shoe sampai bit |
| Operating state | drilling, sliding, reaming, sirkulasi, connection, TIH, TOH, pumps off |
| Advisory / Warning / Critical | tingkat alert [PHR 8.4] |
| Unavailable / Low confidence | status saat data tidak valid / input di luar data latih |
| Hydraulic baseline | ECD dari rumus hidraulik + reologi |
| Hybrid residual | ECD_hydraulic + koreksi ML |
| Blind well | sumur yang tidak dipakai di training/tuning |
| Grouped CV / LOWO | cross-validation per sumur / leave-one-well-out |
| Rolling-origin + embargo | validasi waktu untuk forecast tanpa bocoran masa depan |
| Shadow mode | sistem berjalan live tanpa dipakai untuk keputusan |
| Promotion gate | syarat sebelum model dipakai di production |
| OOD | input di luar rentang data latih |
| SHAP | metode penjelasan kontribusi fitur (bukan kausal) |
| Cut-off | waktu batas analisis retrospektif; data sesudahnya tidak dipakai |
| Lead time | selang waktu warning → onset event terverifikasi |
| Pack-off / tight hole / differential / mechanical sticking | jenis gangguan stuck pipe [PHR 8.3] |
| Tag / overpull · P/U, S/O, RO | set-down saat TIH / tarikan berlebih · pick-up, slack-off, rotating-off-bottom |
| Sloughing / cavings | runtuhnya dinding lubang / potongan batuan runtuhan |
| LAS | Log ASCII Standard |

---

## Lampiran H — Daftar Pertanyaan Konfirmasi Klien

Mohon dijawab atau dikoreksi sebelum pembangunan sistem dimulai. Kolom **Usulan kami** adalah nilai default yang dipakai bila klien setuju, jadi klien cukup menjawab "setuju" atau memberi koreksi. Pertanyaan bertanda 🆕 baru ditambahkan di v3.0 karena penyesuaian dengan proposal PHR.

### A. Data & Record

| No | Pertanyaan | Kenapa penting | Usulan kami |
|---|---|---|---|
| A1 | Mud Weight ada di **Record 04** (bukan Record 03), benar? | sumber fitur terpenting | Rec 04 = MW, Rec 03 = PPFG (sesuai proposal & file) |
| A2 | Arti kode **ACTC / Drilling Condition**? (GW339 20 Nov semuanya 0) | operating state | state diturunkan dari flow, RPM, depth, block |
| A3 | `FORMATION` Rec 03 Gula010 kosong. Ada file **formation tops**? | nama formasi | pakai formation tops bila ada |
| A4 | `P_BLSE27_0003HW_MSF` (Rec 02) = **GW339 / BLSE-056**? | identitas sumur | dianggap sama setelah dikonfirmasi |
| A5 | Tank mana yang termasuk **sistem aktif** GW339 & satuannya? | active pit & loss/influx | tank aktif yang dikonfirmasi; bbl |
| A6 | Arti 2 kolom `SPARE` di Rec 01 GW339 | mapping eksplisit [PHR 6.1] | diabaikan sampai jelas |
| A7 | Run 6-1/8" GW339 memang **tanpa PWD/ECD**? Gap 04:17–06:01 memang tidak ada data? | label & QC | ECD ⓥ; gap ditandai |
| A8 | PDSI 53.2: bisa download **Rec 01–07 versi Navita** (time 6–9 Nov, 1 dtk) + survey, PPFG, MW? Jam laporan WIB = jam server? | resolusi studi kasus | pakai file sekarang (±1 mnt) bila tidak ada |
| A9 | Frekuensi download/upload saat shadow mode | latency [PHR 11.1 KPI] | tiap 1 jam saat drilling aktif |
| A10 | **Daftar kejadian historis** (loss, influx, tight hole, pack-off, stuck: waktu, MD, mode) di 9 sumur training dari DDR? | katalog event [PHR 4.5A] | minimal yang tercatat di DDR |
| A11 | GW339: DDR cleanout 6-1/8", laporan casing & cementing, **waktu efektif MW 10,4 → 10,0**, BHA tiap run | Lampiran D.2 h | sebisanya |
| A12 | Contoh **format log** (.rar di Google Drive Navita) | acuan log format | dikirim bila memungkinkan |
| A13 🆕 | Proposal memakai **5 record** (01, 02, 03, 04, 07). **Record 08 (LWD, BDSI 18/19)** ikut dipakai sebagai label/caliper, atau tidak? | scope data [PHR 5.3] | dipakai **opsional** hanya sebagai cek label & caliper |
| A14 🆕 | **Baseline hidraulik yang berlaku di PHR** [PHR 12.2]: ada software/model hidraulik (mis. dari mud company)? Bisa dikirim **reologi PV/YP harian, ukuran hole/casing, BHA tally**? | baseline wajib (Eksperimen A, F) | bila tidak ada → Eksperimen A sementara MW-only + ditandai |
| A15 🆕 | **Persetujuan data owner** formal untuk Record 01–07 [PHR 12.2]: siapa? | governance | dicatat di dokumen Fase 0 |
| A16 🆕 | **Interval PWD** per sumur training (section/periode dengan tool ECD) | label coverage | dibaca dari data, lalu dikonfirmasi |
| A18 🆕 | Di sumur training, apakah tool PWD **juga merekam saat clean-out / reaming / back-reaming / wiper trip** (bukan hanya saat drilling)? Sumur mana yang punya interval seperti itu? | label untuk use case clean-out | dibaca dari data (Rec 02 vs state Rec 01), lalu dikonfirmasi |
| A19 🆕 | Daftar **run BHA tanpa tool ECD** yang akan datang (sumur, section, BHA, ukuran hole/casing, tanggal) | sumur shadow & fitur geometri | dikirim per run |
| A17 🆕 | **Provenance ECD Rec 02**: dari PWD sub? kedalaman sensor (offset dari bit)? sudah dikonversi dari tekanan oleh vendor? kalibrasi? | definisi label [PHR 2.4] | ECD Rec 02 = PWD vendor; offset sensor diminta |

### B. Logika & Ambang

| No | Pertanyaan | Usulan kami |
|---|---|---|
| B1 | Batas bawah memakai **max(PP, SFG)** dari Rec 03, atau ada collapse pressure terpisah dari Geomechanics? [PHR 8.1] | max(PP, SFG) |
| B2 | Ambang margin **Advisory** (atas & bawah) | ≤ 0,5 ppg |
| B3 | ECD naik cepat (Advisory) | > 0,2 ppg / 5 menit |
| B4 | Ambang anomali awal: tag, overpull, torque, SPP, flow out, pit | tag 5 klb · overpull 20 klb · torque 3σ · SPP 10 % · flow out 10 % · pit 5 bbl |
| B5 | Durasi minimum alert | 60 detik |
| B6 | Tingkat alert diganti mengikuti proposal: **Normal / Advisory / Warning / Critical + Unavailable/Low confidence** (menggantikan Aman/Waspada/Anomali/Bahaya/No Data). Setuju? | setuju |
| B7 | Batas umur data sebelum ⚫ Unavailable | 30 menit |
| B8 | Baseline normal: otomatis dari periode tanpa event, atau ditentukan engineer ("take baseline")? | otomatis, bisa diubah engineer |
| B9 | Penamaan hipotesis **GW-H1..H4** (mekanisme GW339) dan **PHR-H1..H4** (penelitian) | setuju |
| B10 | Batas ECD valid untuk flag outlier | 7–20 ppg |
| B11 🆕 | Horizon forecast: proposal PHR **5–15 mnt** (fase terpisah setelah nowcast), proposal GW339 **5/15/30 mnt**. Mana yang dipakai? | 5–15 mnt, setelah uji prospektif |
| B12 🆕 | Margin di **open-hole exposed interval** [PHR 2.2]: setuju dihitung di bit **dan** di titik FG_min terendah antara shoe–bit (ECD diestimasi konservatif sampai baseline hidraulik ada)? | setuju |
| B13 🆕 | Ambang **Warning** margin dan definisi **Critical** (Bab 8.4) | Warning ≤ 0,25 ppg bertahan; Critical margin ≤ 0 atau bukti pit/flow |
| B14 🆕 | Aturan **effective-from MW** (Rec 04 per depth → per waktu): MW berlaku sejak bit melewati depth itu, atau dari waktu mud report? | sejak bit melewati depth, kecuali ada waktu mud report |

### C. Tampilan

| No | Pertanyaan | Usulan kami |
|---|---|---|
| C1 | Default Live Monitor: horizontal (template GW-339) atau log format? | horizontal; log format satu klik |
| C2 | Preset skala mengikuti template Navita (ROP 0–1200, Flow 0–800, RPM 0–80, Hookload 0–150, Block 0–75, SPP 0–2400, Torque 0–15, WOB 0–22,5, ECD 8–14, Flow Out 0–100)? | ya |
| C3 | Channel tambahan wajib di layar (STICK, Trip Tank, Active Pit, Gain/Loss)? | Active Pit, Gain/Loss, Trip Tank |
| C4 | Bahasa antarmuka | Indonesia + istilah drilling Inggris |
| C5 | Satuan ppg, ft, psi, klb, kft·lb, gpm, bbl | ya |
| C6 🆕 | Fitur **di luar proposal**: what-if, proyeksi ECD per depth, citra cutting. Masuk backlog (tidak dibangun dulu)? | ya, backlog |
| C7 🆕 | Zona waktu: data disimpan UTC, ditampilkan **WIB**? | ya |

### D. Output & Laporan

| No | Pertanyaan | Usulan kami |
|---|---|---|
| D1 | Bentuk output warning: kolom ALERT di log, tabel indikator "sejak jam", grafik risk score. Perlu semua? | semua; tabel indikator sebagai ringkasan utama |
| D2 | Notifikasi: layar, email, WA/Telegram? | layar + email (WA/Telegram backlog) |
| D3 | Format laporan | PDF + PPTX |
| D4 🆕 | **Kategori event & label confidence** di Riwayat Event: loss, influx, pack-off/poor hole cleaning, tight hole/sloughing, differential sticking, mechanical sticking, stuck, noise; confidence tinggi/sedang/rendah. Setuju? | setuju |

### E. Model & Validasi

| No | Pertanyaan | Usulan kami |
|---|---|---|
| E1 | Akurasi dilaporkan **per sumur blind** (lebih rendah tapi jujur), bukan split acak (~100 % tapi semu)? | ya [PHR 2.5, 7.3] |
| E2 | Target akurasi ECD: proposal menyebut target ditetapkan PHR **setelah studi distribusi data**. Siapa yang menetapkan & kapan? | Drilling Eng/RTO setelah Fase 1 |
| E3 | Sumur blind pertama | LOWO untuk diagnosis + 1 sumur blind tetap. 🆕 Klien (21 Nov): **BDSI 60 sudah selesai, bisa jadi sumur testing atau sumur model ke-10**. Usulan: **BDSI 60 = blind tetap** (belum pernah dilihat model, uji paling jujur); baru digabung ke training setelah hasil blind dilaporkan. ACS26 kembali ke training. Final setelah audit data BDSI 60 |
| E4 | Model baru dipakai sebelum disetujui engineer? | tidak; promotion gate [PHR 7.4] |
| E5 🆕 | **Engineering tolerance** untuk "% prediksi dalam toleransi" [PHR 4.5] | ±0,1 ppg (usulan untuk dibahas) |
| E6 🆕 | Uji ekstrapolasi **12.25" → 8.5"** tanpa retraining dilaporkan terpisah [PHR 4.4]? | ya |
| E7 🆕 | Karena use case utama adalah **clean-out run tanpa tool ECD**, apakah akurasi di **state clean-out** (sirkulasi/reaming/back-reaming/washing) dijadikan KPI utama, terpisah dari akurasi drilling? | ya, dilaporkan per state |

### F. Akses, Deploy & Keamanan

| No | Pertanyaan | Usulan kami |
|---|---|---|
| F1 | Sistem dipasang di mana (server kantor/RTO, laptop, cloud internal)? Akses dari rig? Kebijakan keamanan data PHR yang berlaku? [PHR 9.3] | server kantor/RTO, browser |
| F2 | Narasi laporan dengan AI eksternal atau lokal? | ✅ **Dijawab klien (21 Nov): boleh layanan AI eksternal** untuk saat ini |
| F3 | Login akun lokal atau SSO PHR? | ✅ **Dijawab klien (21 Nov): akun lokal**; akun PHR belum ada |
| F4 | Daftar user & perannya mengikuti Bab 10.2 (Drilling Eng, RTO, Mud Eng, Geomechanics, Directional/MWD, Data/ML, HSE, viewer rig)? | ya |
| F5 | Room dibuat otomatis dari nama sumur & diarsipkan saat rig pindah? | dibuat otomatis, diarsipkan manual |
| F6 | Data masuk: upload, folder pantau, atau WITSML nanti? | upload + folder pantau |
| F7 🆕 | **Siapa approver** tiap peran: versi PPFG (Geomechanics), aturan MW (Mud Eng), ambang alert (Drilling Eng + HSE), promote model (Drilling Eng)? | nama dicatat di Fase 0 |

### G. Jadwal, Prioritas & Governance

| No | Pertanyaan | Usulan kami |
|---|---|---|
| G1 | Prioritas: (1) data readiness 5 record + QC, (2) model ECD & studi kasus 53.2/GW339 offline + laporan, (3) dashboard inti untuk shadow — setuju? | ya [PHR 12.3] |
| G2 | Shadow mode awal Desember dimulai **setelah gate Fase 2 "Model performance reviewed"**. Dashboard minimum: Live Monitor, Data & Upload, Formasi & FG, Riwayat Event, Analisis Anomali | ya; Model ML & Profil Depth menyusul |
| G3 | Siapa yang menyetujui dokumen ini (gate Fase 0 "Scope approved")? | Drilling Engineering + RTO |
| G4 🆕 | **Durasi dan jumlah sumur pilot** (Fase 4) [PHR 10.1] | ditetapkan setelah review shadow mode |
| G5 🆕 | Evaluasi nilai ekonomi [PHR 11.2]: ada **validated cost rate** (biaya NPT/jam) yang bisa dipakai di Fase 4–5? | dibahas setelah pilot |
