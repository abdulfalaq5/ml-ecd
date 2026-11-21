# Data Dictionary & Record Navita untuk Sistem ECD ML

Dokumen ini adalah **data dictionary lengkap** sistem, yaitu implementasi **Appendix A** dan **Bab 6.1** *Technical Proposal PHR Bab 1–12* (acuan utama). Isinya: record dan channel yang di-download dari Navita, nama kanonik, satuan, validasi, alias antar rig, dan aturan download supaya ingest tidak error. Berlaku untuk **Time Based** dan **Depth Based**.

> **Update 21 Nov 2026 (v3.0, mengikuti proposal PHR):**
> - Sumber data inti = **lima record** [PHR 1.2, 5.3]: **01 IDS Rig, 02 MWD/PWD, 03 PPFG, 04 Mud Weight, 07 Survey**. Record 05 & 06 tidak diasumsikan ada. **Record 08 (LWD)** hanya **opsional** dan menunggu konfirmasi (Desain Lampiran H A13).
> - Mode time-based dan depth-based Rec 01/02 adalah **dua penyajian dari sumber yang sama**, bukan dua sensor independen [PHR 5.3].
> - Mapping tag dibuat **eksplisit**, tidak berdasarkan kemiripan nama [PHR 6.1].
> - Hasil download Navita **selalu `.zip`** (per record), isinya ASCII LAS atau CSV.

---

## 0. Kolom Data Dictionary [PHR 6.1]

Setiap channel kanonik di database menyimpan atribut berikut. Diisi di `config/mnemonics.yaml` dan ditampilkan di halaman Data & Upload.

| Atribut | Contoh (`spp`) |
|---|---|
| canonical field name | `spp` |
| original tag (per rig/vendor) | `SPP` (Navita), `SPPA` (PDSI 53.2 LAS), `SPP` (CSV) |
| unit | psi |
| sensor origin | IDS Rig (Rec 01); cadangan `SPPMWD` (Rec 02) |
| sampling rate | 1 dtk (Gula010), 1–14 dtk (GW339 20 Nov), ±1 mnt (PDSI 53.2) |
| source time zone | server (`dtsrv`) → dinormalisasi ke UTC, tampil WIB |
| missing-value convention | `-999.25` → NaN |
| expected physical range | 0–5.000 psi (nilai negatif = offset sensor → flag) |
| valid section | semua |
| owner | RTO / IDS Rig |

### 0.1 Ringkasan canonical fields (Appendix A proposal + tambahan)

| Field | Unit | Record | Tag asli (alias) | Validasi | Peran |
|---|---|---|---|---|---|
| `well_id` | text | All | `WID`, header `WELL` | canonical ID; koreksi nama salah | kunci |
| `event_time` | ISO 8601 UTC | 01/02 | `dtsrv` (`TIME` epoch) | timezone, clock offset rig–MWD, gap flag | indeks |
| `bit_depth_md` | ft | 01/02 | `DBTM` (`DEPTBITM`, `BIT DEPTH`) | monotonik per operasi; LAS `.m` = ft | as-of join |
| `hole_depth_md` | ft | 01/02 | `DMEA` (`DEPTMEAS`) | ≥ bit depth | state, open hole |
| `ecd_actual` | ppg | 02 | `ECD` | provenance PWD, 7–20 ppg (usulan), pumps on | **target saja** |
| `annular_pressure` | psi | 02 | `ANP` | cek ECD ≈ ANP/(0,052×TVD_sensor) | QC label |
| `flow_in` | gpm | 01 | `MFIA` | pump state | fitur |
| `flow_out_pct` | % | 01 | `MFOP` | 0–100 | loss/influx |
| `active_pit` | bbl | 01 | `TVA` (`TVOLACT`, Σ tank aktif) | pemetaan tank per rig | loss/influx |
| `gain_loss` | bbl | 01 | `GL` (`TVOLCACT`) | — | loss/influx |
| `spp` | psi | 01 | `SPP` (`SPPA`) | offset negatif → flag | fitur, pack-off |
| `hookload` | klb | 01 | `HKLA` | rentang | fitur, overpull |
| `torque` | kft·lb | 01 | `TORQUE` (`TORQA`) | frozen/spike | fitur, stall |
| `rpm` | rpm | 01 | `RPM` (`RPMA`) | ≥ 0 | fitur, state |
| `wob` | klb | 01 | `WOB` | offset negatif → flag | fitur, tag |
| `rop` | ft/h | 01 | `ROP` | ≥ 0 | fitur |
| `block_pos` | ft | 01 | `BPOS` (`BLKPOS`) | rentang | state |
| `mud_weight` | ppg | 04 | `MUDWEIGHT` | effective depth/version; aturan effective-from | fitur |
| `pp`, `sfg`, `fg_min`, `fg_max` | ppg | 03 | `PP`, `SFG`, `FGMIN`, `FGMAX` | versi approved, TVD datum, uncertainty | batas (bukan label) |
| `tvd` | ft | 07 | `DSVV` (cek `DVER` Rec 02) | interpolasi min. curvature | hidrostatik, datum |
| `inclination` / `azimuth` / `dls` | ° / ° / °/100 ft | 07 | `SINC` / `SAZC` / `SDLS` | validitas survey | fitur, exposure |
| `operating_state` | kode | turunan | `ACTC` bila terisi, atau aturan (Desain Bab 6.3) | konsistensi flow/depth | segmentasi |

---

## 1. Data Source Register [PHR 4.2A, 5.3]

| Record | Sumber | Basis | Isi utama | Peran di sistem |
|---|---|---|---|---|
| **01** | IDS Rig | Time (1 dtk) & Depth (0,25 ft) | Bit/Hole Depth, Block Position, ROP, Hookload, WOB, Torque, RPM, SPP, Flow In, **Flow Out %**, **Tank Volume Active**, **Gain/Loss**, SPM1–3, Total Stroke | **fitur model ECD**, operating state, loss/influx, modul stuck-pipe |
| **02** | MWD / PWD (SLB / Halliburton) | Time (30 dtk) & Depth | **ECD**, Annular Pressure (ANP), TVD, Mud Density In/Out, temperatur, RPM impeller, SPP MWD, inklinasi/azimuth kontinu | **target ECD** (hanya bila sensor & kualitas terkonfirmasi), TVD |
| **03** | PPFG Geomechanics | Depth (ada juga time) | **PP, FG Min, FG Max, SFG**, SHMax, OBG, Formation, MD/TVD | **batas risiko berversi** (atas: FG Min; bawah: PP/collapse). **Bukan label ECD** |
| **04** | Mud Weight | Depth | **MUDWEIGHT (ppg)**, REMARK | fitur MW + MW statis vs batas bawah; perlu aturan effective-from |
| **07** | Directional Survey | Depth | MD, TVD, Inclination, Azimuth, DLS, N/S, E/W | TVD, DLS, exposure geometrik |
| 08 *(opsional)* | LWD (hanya BDSI 18 & BDSI 19) | Time & Depth | ECD, Annular Pressure, PWD depth, **Caliper**, GR, resistivitas | di luar 5 record proposal; cek label & caliper **bila disetujui** |
| 05, 06 | — | — | — | tidak diasumsikan ada (bila ter-download: disimpan mentah, diabaikan) |

**Time vs Depth based — dipakai dua-duanya**

| | Time Based | Depth Based |
|---|---|---|
| Indeks | `Date time server` / `dtsrv` (Rec 01 tiap 1 dtk, Rec 02 tiap 30 dtk) | `DEPTH` (step 0,25 ft) |
| Fungsi | nowcast ECD, loss/influx, modul stuck-pipe, picker waktu & replay | profil ECD vs PP / SFG / MW / FG Min, exposure interval |
| Halaman UI | Live Monitor (track multi-channel), Analisis Anomali, Riwayat Event | Profil Depth, Formasi & FG |

Catatan format:
- Header LAS menulis satuan depth `.m`, tapi nilainya **ft** (cocok dengan MD/TVD ft). Sistem memakai ft dan memberi catatan.
- Data Rec 01/02 time based diunduh per **±1 minggu** per zip (contoh: `23-29 Oct`, `29 Oct-4 Nov`, …). Satu sumur 1–3 minggu = 3–4 zip per record.

---

## 2. Record 01 (Rig) — channel yang dipakai

Mnemonic = nama di file LAS Navita. Template "full Record 01" Navita **sudah berisi semua channel di bawah** (dicek di Gula010, MANGGA 0004, GW339).

| # | Mnemonic LAS | Nama Navita | Satuan | Untuk apa | Wajib? |
|---|---|---|---|---|---|
| 1 | `dtsrv` | Date time server | timestamp | indeks waktu | ✅ wajib |
| 2 | `DATE`, `TIME` | Date, Time | — | jam rig (selisih ±7 jam dengan server → acuan `dtsrv`) | info |
| 3 | `WID` | Well Identifier | — | nama sumur (dikoreksi otomatis bila salah, mis. "Kopar-52") | info |
| 4 | `ACTC` | Activity / Drilling Condition | kode | rig state | ✅ wajib |
| 5 | `DBTM`, `DBTV` | Bit Depth (meas / vert) | ft | posisi bit | ✅ wajib |
| 6 | `DMEA`, `DVER` | Hole Depth (meas / vert) | ft | mapping formasi | ✅ wajib |
| 7 | `BPOS` | Block Position | ft | koneksi / tripping / reaming | ✅ wajib |
| 8 | `ROP` | ROP | ft/h | fitur model | ✅ wajib |
| 9 | `HKLA`, `HKLX` | Hookload avg / max | klb | fitur dominan; **overpull / drag** (stuck pipe) | ✅ wajib |
| 10 | `WOB`, `WOBX` | WOB avg / max | klb | fitur; **tagging / set-down** | ✅ wajib |
| 11 | `TORQUE`, `TORQUEMAX` | Rotary Torque avg / max | kft·lb | fitur; **torque spike / stall** | ✅ wajib |
| 12 | `RPM`, `SURFRPM` | Surface RPM | rpm | fitur; **rotasi berhenti mendadak** | ✅ wajib |
| 13 | `SPP` | Standpipe Pressure | psi | fitur dominan; **pack-off** (SPP naik) | ✅ wajib |
| 14 | `MFIA` | Mud Flow In | gpm | fitur + pumps on/off | ✅ wajib |
| 15 | `MFOP` | **Mud Flow Out %** | % | **deteksi loss/gain** (flow out turun saat flow in tetap) | ✅ wajib (loss) |
| 16 | `TVA` | **Tank Volume Active** | bbl | **deteksi loss/gain** | ✅ wajib (loss) |
| 17 | `GL` | **Gain / Loss** | bbl | **deteksi loss/gain** | ✅ wajib (loss) |
| 18 | `SPM1`, `SPM2`, `SPM3` | Pump strokes | spm | cek pompa, lag time | disarankan |
| 19 | `TOTSTK`, `LSTK` | Total / Lag strokes | — | lag time cutting (bottoms-up) | disarankan |
| 20 | `TVOL1`–`TVOL5`, trip tank | Tank volumes | bbl | cadangan bila TVA kosong; trip tank saat POOH/TIH | opsional |
| 21 | `CASPRESS`, `MCIA`, gas, H2S | — | — | diabaikan (umumnya kosong) | opsional |

> Export lama (folder `12.25in section` / `8.5in Section`, custom 20 channel) **tidak berisi** TVA, GL, MFOP. Download full Record 01 yang baru sudah berisi semuanya.

---

## 3. Record 02 (MWD/PWD — SLB / Halliburton) — channel yang dipakai

| Mnemonic | Untuk apa | Catatan |
|---|---|---|
| `dtsrv` / `DEPTH` | indeks | |
| **`ECD`** | **target model** (tidak pernah fitur di konfigurasi surface-only) | outlier ekstrem (0,98 – 157 ppg) → flag, tidak dibuang otomatis; provenance sensor & kedalaman sensor perlu dikonfirmasi [PHR 2.4] |
| `ANP` | Annular pressure | cross-check ECD = ANP / (0,052 × TVD) |
| `DBTM`, `DBTV`, `DMEA`, `DVER` | sinkronisasi + TVD | |
| `MDIA`, `MDOA` | Mud density in/out | sering nol → **MW utama diambil dari Rec 04** |
| `MTOA`, `TEMP` | temperatur | fitur tambahan |
| `SPPMWD`, `RPMIMP` | SPP & RPM impeller MWD | fitur tambahan / cek pompa |
| `SPP`, `MFIA`, `HKLA`, `WOB`, `TORQUE`, `RPM`, `ROP` | cadangan bila Rec 01 putus | |
| `SQID`, `TOTSTK` | sinkronisasi | |

**Sumur tanpa sensor ECD** (mis. **GW337**, **PDSI 53.2**, **GW339 run 6-1/8"**; ECD = 0 / kosong): Rec 02 tidak dipakai sebagai target. Sistem tetap jalan dengan **ECD prediksi ⓥ** (inferensi tanpa klaim akurasi [PHR 5.1]) + loss/influx & modul stuck-pipe dari Rec 01. **Label tidak boleh diisi dari hydraulic baseline** [PHR 2.4].

---

## 4. Record 03 (PPFG) — batas formasi berversi

| Mnemonic | Arti | Dipakai sebagai |
|---|---|---|
| `MD`, `TVD` | kedalaman PPFG | lookup per depth |
| **`FGMIN`** | Fracture Gradient minimum | **batas atas** (loss) |
| `FGMAX` | Fracture Gradient maksimum | info |
| **`PP`** | Pore Pressure | **batas bawah** (influx/kick) |
| **`SFG`** | Shear Failure Gradient | **batas bawah** (collapse / sloughing) |
| `SHMAX`, `OBG` | tegangan horizontal maks, overburden | info / fitur geomekanik |
| `FORMATION` | nama formasi | label formasi (bila kosong → dari formation top) |

Contoh nilai Gula010 (Rec 03 depth based): PP ≈ 8,3–8,7 ppg, **SFG ≈ 9,1–11,2 ppg**, FG Min ≈ 13,2–16,5 ppg.
→ Dengan usulan batas bawah = max(PP, SFG), batas bawah Gula010 ditentukan **SFG**. Definisi final mengikuti model geomekanika dan disetujui Geomechanics [PHR 8.1].

> FG Min "baru diketahui" ketika ada drilling baru (dari model reservoir saat sumur akan dibor). Karena itu sistem **membaca Rec 03 per sumur** dan menyimpannya sebagai **versi** (effective date, approver, interval applicability, TVD datum). Versi baru berstatus draft sampai di-approve Geomechanics. Model ECD **tidak** dilatih ulang saat FG berubah [PHR 7.4].

---

## 5. Record 04 (Mud Weight) & Record 07 (Survey)

| Record | Mnemonic | Kegunaan |
|---|---|---|
| 04 | `MDPPFG`/`DEPTH`, `TVD`, **`MUDWEIGHT`**, `REMARK` | MW per depth → di-join ke data time based lewat bit depth (as-of, tanpa melihat masa depan). Depth snapshot ≠ nilai tiap timestamp → **aturan effective-from disetujui Mud Eng** [PHR 4.2A] |
| 07 | `DSVM` (MD), `DSVV` (TVD), `SINC`, `SAZC`, `SDLS`, `SNS`, `SEW` | TVD untuk hidrostatik, inklinasi & DLS untuk ECD dan risiko stuck pipe |

Contoh Gula010 Rec 04: MW 8,7 ppg (permukaan) → 10,0 (1.625 ft) → 10,4 (2.437 ft) → 11,0 (3.250 ft) → 9,8–10,1 ppg (section 8.5").

---

## 6. Record 08 (LWD — opsional, di luar 5 record proposal)

Hanya ada di **BDSI 18 (MINA26-0017)** dan **BDSI 19 (MINA-02222)**. Isi penting: `ECD`, `ANNPRESS`, `PWD` (depth sensor), **`MCLP` (Caliper)**, `MG1/MG2` (Gamma Ray), `MFTA` (temperatur), `MFPP`/`MFFP` (PP/FP dari MWD).
- Hanya dipakai bila klien menyetujui (Desain Lampiran H A13): ECD Rec 08 sebagai **cek konsistensi** label Rec 02.
- **Caliper** = bukti pembesaran lubang → pendukung validasi sloughing (bukan fitur model).

---

## 7. Aturan Download & Upload agar tidak error

1. **Nama channel / mnemonic jangan diubah** — sistem mencocokkan berdasarkan mnemonic LAS (atau nama kolom CSV).
2. Gunakan **template channel yang sama** setiap download (simpan template di Navita).
3. Format: **ASCII LAS (utama)** atau CSV, **boleh `.zip`** (hasil download Navita memang selalu zip). Satu zip boleh berisi satu record.
4. Periode: per hari atau per minggu boleh. Upload berikutnya **disambung otomatis**, overlap dibuang.
5. Nilai null `-999.25` biarkan saja.
6. Nama file/folder disarankan: `<Rig> <Sumur> <Time|Depth> <periode> Rec <NN>`, contoh `BDSI61 Gula10 TimeBased Record 01 4-10 Nov.zip` (pola ini sudah dipakai sekarang — sistem membaca nomor record dari nama file **dan** header).
7. Rec 03 & 04 & 07 cukup **depth based**; download ulang bila ada revisi PPFG / perubahan MW / survey baru.
8. Untuk sumur yang sedang dibor: download sejak Navita tersambung / sumur siap dibor **sampai rig pindah** (1–3 minggu), termasuk periode tidak drilling (tripping, sirkulasi, pumps off) — penting untuk analisis stuck pipe & sloughing.

---

## 8. Perilaku sistem jika data tidak lengkap

| Kondisi | Hasil |
|---|---|
| Channel wajib model tidak ada (SPP, Flow In, Hookload, …) | File tetap disimpan mentah; prediksi berstatus **Unavailable / Low confidence** dengan alasan "channel X tidak ditemukan" [PHR 4.6] |
| ECD tidak ada / nol (sumur tanpa sensor) | Data dipakai untuk **inferensi & anomali**, tidak untuk training; label "ECD ⓥ prediksi" |
| TVA / GL / MFOP tidak ada | Prediksi ECD tetap jalan; warning loss/influx nonaktif + penanda [PHR 8.2] |
| Rec 03 tidak ada / belum di-approve | Margin tidak dihitung ("PPFG belum tersedia / belum approved"); prediksi tetap jalan |
| Rec 04 tidak ada | Pakai Mud Density In (Rec 02) bila > 0, jika tidak → input MW manual |
| Rec 07 tidak ada | TVD dari `DBTV`/`DVER` Rec 01/02 |
| `TVA`/`GL` kosong tapi tank kompartemen ada | Active pit = jumlah tank aktif (pemetaan per rig), gain/loss dihitung dari perubahan volume |
| `ACTC` selalu 0 | Rig state diturunkan dari flow, RPM, bit vs hole depth, block |
| Interval waktu tidak tetap (1–14 dtk) | Resample ke grid tetap; gap > batas ditandai |
| Record / channel tidak dikenal (05, 06, dll.) | Disimpan mentah, diabaikan, tidak error |
| Format LAS non-standar (mis. PDSI 53.2: `TIME` epoch, `DEPTBITM`, `TVOLACT`, …) | Dipetakan lewat **tabel alias mnemonic** (lihat §9) |

---

## 9. Alias mnemonic antar-rig / vendor

Beberapa rig memakai mnemonic berbeda untuk channel yang sama. Sistem menyimpan tabel alias:

| Channel standar | Navita full record | Template BEKA | PDSI 53.2 (LAS) | PDSI 53.2 (CSV) |
|---|---|---|---|---|
| waktu | `dtsrv` | `dtsrv` | `TIME` (epoch) | `TIME` |
| bit depth | `DBTM` | `DBTM` | `DEPTBITM` | `BIT DEPTH` |
| hole depth | `DMEA` | `DMEA` | `DEPTMEAS` | `MEASURE DEPTH` |
| block position | `BPOS` | `BPOS` | `BLKPOS` | `BLOCK HEIGHT` |
| hookload | `HKLA` | `HKLA` | `HKLA` | `HOOKLOAD` |
| torque | `TORQUE` | `TORQUE` | `TORQA` | `TORQUE` |
| RPM | `RPM` | `RPM` | `RPMA` | `RPM` |
| SPP | `SPP` | `SPP` | `SPPA` | `SPP` |
| flow in | `MFIA` | `MFIA` | `MFIA` | `MUD FLOW IN` |
| flow out % | `MFOP` | `MFOP` | `MFOP` | `MUD FLOW OUT` |
| tank active | `TVA` | `TVOL1..5` | `TVOLACT` | `ACTIVE PIT` |
| tank per kompartemen (GW339 / rig PDSI) | `TVOL1..5` | `TVOL1..5` | `TVOL01..05` | `PIT 1..5` |
| — idem, template GW339 21 Nov | `ACTIVESLUG`, `TRIPTANK`, `SETLINK`, `TANK3`, `TANK4` (Active 2), `TANK5` (Active 1), `PREMIX` | | | |
| gain/loss | `GL` | — | `TVOLCACT` | `GAIN/LOSS` |
| ECD | `ECD` (Rec 02/08) | `ECD` | `SPARE2` (ppg, = 0) | `ECD` (= 0) |

---

## 10. Catatan file GW339 tanggal 20 Nov (download 21 Nov 2026)

File: `export_las_record_01_21-11-2026_120513.LAS` & `export_las_record_02_21-11-2026_120417.LAS` (header `WELL = GW-339/BLSE-056`, field BALAM SE).

| Hal | Record 01 (20 Nov 00:00–24:00) | Record 02 (20 Nov 08:21–23:59) |
|---|---|---|
| Jumlah baris | 9.581 | 1.875 |
| Interval | **tidak tetap**: 1–14 dtk (median 7 dtk) → bukan 1 dtk | 30 dtk (stabil) |
| Gap | 04:17 → 06:01 (1 j 44 mnt tanpa data) | tidak ada gap > 5 mnt |
| Channel terisi | Bit/Hole Depth, Block, Hookload, WOB, Torque, RPM, SPP, Flow In, **Flow Out %**, SPM1–3, tank per kompartemen | Bit/Hole Depth, **Hole Depth TVD**, Block, Hookload, WOB, SPP, SPM, **Inclination & Azimuth kontinu**, **Turbine RPM** |
| Channel kosong | `ACTC` (semua 0), `TVA`, `GL`, `DBTV`, `DVER`, `HKLX`, `TORQUEMAX`, `TOTSTK`, `WID` | **`ECD`**, `TORQUE`, `MFIA`, `TVA`, `GL`, `MFOP`, `TEMPERATURE`, `DBTV` |
| Catatan | tank memakai **nama rig** (`ACTIVESLUG`, `TRIPTANK`, `SETLINK`, `TANK3–5`, `PREMIX`) bukan `TVA`; ada 2 kolom `SPARE` terisi (satu identik dengan Torque, satu 0,08–31,55 belum diketahui) | `WID` di data = **`P_BLSE27_0003HW_MSF`** (beda dengan header GW-339/BLSE-056); SPP min −89 psi & WOB min −117 klb (offset sensor); Hookload maks 181 klb vs Rec 01 149 klb |

Akibatnya untuk sistem:
- **Tidak ada ECD terukur di GW339 pada run 6-1/8" (20 Nov)** → status memakai **ECD prediksi ⓥ** (tanpa klaim akurasi); label ECD GW339 hanya dari periode sebelumnya (bila ada).
- **Active pit & gain/loss harus dihitung** dari tank kompartemen (jumlah tank aktif; gain/loss = perubahan volume aktif) → perlu konfirmasi tank mana yang termasuk sistem aktif dan satuannya (`ACTIVESLUG` 242–293 kemungkinan bbl; `TANK4/TANK5` bernilai kecil).
- **Rig state tidak bisa dari `ACTC`** (semua 0) → diturunkan dari flow, RPM, bit vs hole depth, dan gerak block.
- Rec 01 di-resample ke grid tetap (mis. 5 dtk) sebelum fitur rolling; gap ditandai, tidak diinterpolasi.
- TVD diambil dari `DVER` Rec 02 / survey Rec 07 (Rec 01 TVD kosong).
- Hookload & SPP dipakai dari **Rec 01** (Rec 02 punya offset).
- Channel `STICK` (stick-slip, ada di template monitoring Navita) tersedia di template Rec 02 tetapi hampir kosong.

---

## 11. Data di luar Navita (tetap berguna)

| Data | Kenapa | Status |
|---|---|---|
| **DDR / laporan kronologi kejadian** (stuck, pack-off, tight hole, loss, influx, sloughing: timestamp, MD, mode operasi, kategori, confidence) | **Katalog event** untuk validasi & lead time [PHR 4.5A] | **Wajib untuk PHR-H4** |
| Reologi lumpur (PV, YP / Fann 600/300/3) per hari | **Hydraulic baseline wajib** (Eksperimen A) & hybrid (F) [PHR 5.5] | **diminta** (Lampiran H A14) |
| Geometri drillstring & BHA (tally), ukuran lubang/casing, shoe depth | Luas annulus (baseline hidraulik); **open-hole exposed interval** [PHR 2.2] | **diminta**; PDSI 53.2 sudah ada di presentasi |
| Baseline PU / SO / RO (pump on/off) | Pembanding drag normal | disarankan (ada di laporan PDSI 53.2) |
| **Foto cutting/cavings** + waktu + interpretasi | bukti pendukung event; citra = backlog di luar proposal | opsional |
