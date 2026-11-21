# UI Mockup — ECD Monitor (Proposal PHR: ML-Based Real-Time ECD Prediction)

> Dashboard web (container `dashboard`) dibuka lewat browser, mis. `http://<server>:8501`.
> Mockup berupa denah ASCII. **Semua angka = ilustrasi** (bukan hasil uji/KPI [PHR 4.3, 7.3]).
>
> **v3.0 (21 Nov 2026): acuan utama = *Technical Proposal PHR Bab 1–12*.**
> - **Enam dashboard inti** mengikuti proposal [PHR 4.3, 9.2]: **Live Monitor, Profil Depth, Riwayat Event, Data & Upload, Formasi & FG, Model ML**. Masing-masing dilengkapi kontrol production dari proposal (freshness, latency, confidence, model version, PPFG version + approver, review workflow, promotion gate).
> - **Halaman pendukung** dari permintaan klien: Login (akun lokal), Overview multi-room, Analisis Anomali (UI modul stuck-pipe, Fase 4), Laporan (narasi AI eksternal), Pengaturan.
> - Tingkat alert mengikuti proposal [PHR 8.4]: **🟢 Normal · 🟡 Advisory · 🟠 Warning · 🔴 Critical · ⚫ Unavailable** (+ badge *Low confidence*).
> - Tampilan ala template Navita tetap dipertahankan: multi-channel satu sumbu, skala per channel bisa diatur, Picker/Realtime/Latest Scroll/Show All, dan log format + kolom ALERT.
> - **Dipindah ke backlog (di luar proposal):** what-if, proyeksi ECD, citra cutting.
> - Sistem **tidak memberi perintah**. Yang tampil adalah **rekomendasi verifikasi** [PHR 8.4].

---

## 0. Peta Halaman

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ECD Monitor                                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│  DASHBOARD INTI (proposal PHR 4.3 / 9.2)                                      │
│  1. Live Monitor     ← [TIME] ECD ⓜ/ⓥ + margin + alert + freshness/confidence │
│  2. Profil Depth     ← [DEPTH] ECD·MW·PP·SFG·FG vs depth, exposure interval    │
│  3. Riwayat Event    ← label engineer + review workflow + label confidence     │
│  4. Data & Upload    ← zip Navita Rec 01·02·03·04·07, QC, lineage, clock drift │
│  5. Formasi & FG     ← Rec 03/04 berversi + approver + effective date          │
│  6. Model ML         ← blind-well, SHAP, registry, promotion gate, rollback    │
├──────────────────────────────────────────────────────────────────────────────┤
│  PENDUKUNG (permintaan klien)                                                 │
│  L. Login (akun lokal) · 0. Overview multi-room · A. Analisis Anomali (H4)    │
│  R. Laporan (PDF/PPTX/DOCX, narasi AI) · S. Pengaturan (ambang + approval)    │
└──────────────────────────────────────────────────────────────────────────────┘
```

Alur utama:

```
 Data & Upload (4) ─► QC report ─► Formasi & FG (5): approve PPFG/MW ─► Model ML (6): model aktif
        │                                                                     │
        └──────────────► Live Monitor (1) ◄── Profil Depth (2) ◄──────────────┘
                              │ alert
                              ▼
                 Riwayat Event (3) ─► review engineer ─► katalog event ─► validasi / retraining
                              │
                 Analisis Anomali (A, cut-off) ─► Laporan (R)
```

**Atribut wajib di setiap output prediksi** [PHR 4.6]: timestamp · well/section · model version · input completeness · uncertainty/quality status · versi formation limit.

---

## L. Login (akun lokal)

```
┌──────────────── Login ────────────────┐
│  ECD Monitor — PHR Drilling / RTO     │
│  Username [______________]            │
│  Password [______________]            │
│  [ Masuk ]   (akun lokal dari Admin)  │
└───────────────────────────────────────┘
```

- Akun dibuat Admin. Password disimpan ter-hash. Hak akses per peran dan per room [PHR 9.3].
- Peran mengikuti [PHR 10.2]: Drilling Eng, RTO, Mud Eng, Geomechanics, Directional/MWD, Data/ML (Admin), HSE reviewer, viewer rig.
- Integrasi akun PHR (SSO) belum ada, tetapi disiapkan.

---

## 0. Overview (multi-room, tidak dibatasi)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ECD Monitor — Overview   🔍 [cari sumur/rig]  Filter: [Aktif ▾][Area ▾][Tingkat ▾]  🔔 3│
│ Room aktif: 10 · Arsip: 9 · [+ Room baru]                     Tampilan: (●)Kartu ( )Tabel│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐ ┌──────┐│
│ │ GW339 · BLSE-056      │ │ BDSI 60 · …           │ │ GW337 · …             │ │ …    ││
│ │ 6-1/8" · sirkulasi    │ │ 8.5" · drilling       │ │ 12.25" · drilling     │ │      ││
│ │ 🟠 WARNING pack-off   │ │ 🟢 NORMAL             │ │ ⚫ UNAVAILABLE        │ │      ││
│ │   sejak 19:12 (38 mnt)│ │                       │ │   data 47 mnt lalu    │ │      ││
│ │ ECD ⓥ 10.7 / FG 13.3  │ │ ECD ⓜ 10.4 / FG 13.6  │ │ terakhir valid 10.2 ⓥ │ │      ││
│ │ MW 10.0 · SFG 10.6 ⚠  │ │ MW 10.0 · SFG 9.4     │ │ MW 9.8 · SFG 9.6      │ │      ││
│ │ data 3 mnt lalu ✅    │ │ data 1 mnt lalu ✅    │ │ ⚠ stale               │ │      ││
│ │ model v1 Shadow       │ │ model v1 Shadow       │ │ model v1 Shadow       │ │      ││
│ └───────────────────────┘ └───────────────────────┘ └───────────────────────┘ └──────┘│
│ ⓜ = ECD terukur PWD   ⓥ = ECD prediksi model (sumur/run tanpa PWD)                     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- Room dibuat otomatis saat upload sumur baru dan diarsipkan saat rig pindah. Jumlah room tidak dibatasi.
- Kartu diurutkan dari tingkat alert tertinggi. Viewer rig hanya melihat room rig-nya.

---

## 1. Live Monitor (Time Based) — dashboard inti #1

Fungsi proposal: ECD aktual vs prediksi dan alert card. Kontrol production yang ditambahkan: **latency, stale-data badge, operational state, confidence, source quality, no-data state, model version, last valid vs current** [PHR 4.3, 9.2, 9.3]. Tampilan grafik mengikuti **template monitoring Navita** atas permintaan klien.

### 1a. Header status + track multi-channel satu sumbu (horizontal)

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ ☰ Room: [GW339 · BLSE-056 ▾] Section: [6-1/8" ▾]   20 Nov 19:30 WIB · data 3 mnt lalu ✅ │
│ State: SIRKULASI · latency 2 mnt · model ecd-xgb v1 (Shadow) · fitur valid 11/12 (TORQUE⚠)│
│ PPFG: Rec 03 v2 (approved Geomech, 19 Nov) · MW: Rec 04 (effective-from: bit depth)       │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ ECD ⓥ 10.71 (10.5–10.9) · confidence OK │ FG_min bit 13.3 · OH min 13.1 @5,360 │ SFG 10.6 │
│ MW 10.0 │ Margin atas bit 2.6 (2.4–2.8) · OH 2.4 │ bawah 0.1 │ 🟠 WARNING                  │
├────────────────────────────┬─────────────────────────────────────────────────────────────┤
│ CHANNEL     min  ─  max  👁 │ 18:35     18:45     18:55     19:05     19:15     19:25        │
│ ▌ROP  ft/h    0 ─ 1200  ☑  │                                     ▲A1    ▲A2               │
│ ▌Flow gpm     0 ─  800  ☑  │ ▁▁▁▁╱▔▔▔╲▁▁╱▔▔▔╲▁▁▁▁╱▔▔▔╲▁▁▁▁▁▁▁╱▔▔▔╲▁▁╱▔▔▔╲▁▁▁              │
│ ▌RPM          0 ─   80  ☑  │ ▁▁▁▁▁▁▁▁▁▁▁▁╱▔▔╲▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁              │
│ ▌Hookload klb 0 ─  150  ☑  │ ▔▔▔▔╲▁▁▁▁▁╱▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔╱▔▔▔▔▔▔▔▔▔▔▔╲▁▁╱▔▔▔               │
│ ▌Block ft     0 ─   75  ☑  │ ╲▁╱╲▁╱╲▁╱╲▁╱╲▁╱╲▁╱  ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁              │
│ ▌SPP psi      0 ─ 2400  ☑  │ ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁╱▔╲╱▔▔╲╱▔▔▔╲╱▔▔╲▁▁              │
│ ▌Torque kft·lb 0 ─  15  ☑  │ ▁▁▁▁▁▁▁▁▁▁▁╱╲▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁╱╲╱╲▁▁▁▁╱╲╱╲▁▁▁▁▁▁              │
│ ▌WOB klb      0 ─ 22.5  ☑  │ ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁              │
│ ▌ppg 🔒  8 ─ 14            │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  FG_min      │
│   ECD ⓜ ☐ · ECD ⓥ ☑ (+pita)│ ─────╮╭───────────────────────╭╮╭──╮╭──╮─────── ECD ⓥ ░pita░ │
│   SFG ☑ · MW ☑             │ ═════════════════════════════════════════════  SFG   ─── MW   │
│ ▌Flow Out %   0 ─  100  ☑  │ ▁▁▁╱▔▔╲▁▁▁╱▔▔╲▁▁▁▁╱▔▔╲▁▁▁▁▁▁╱▔╲▁▁▁╱▔╲▁▁▁▁▁                   │
│ ▌Active Pit bbl 0 ─ 700 ☑  │ ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔                │
│ ▌Gain/Loss bbl -50 ─ 50 ☑  │ ─────────────────────────────────────────────────            │
│ [+ Channel] [Preset ▾]     │ ▒▒ = periode data invalid/gap (tidak diinterpolasi)          │
├────────────────────────────┴─────────────────────────────────────────────────────────────┤
│ ⚙ 🕒 ⏬ │ [Realtime] [Picker] [🖨] [📏] │ ◀━━━━━━━━[████ 18:33–19:32 ████]━━━━▶ │ [Show All] [Latest Scroll] │
└──────────────────────────────────────────────────────────────────────────────────────────┘
 ▲A1 19:12 🟠 WARNING SPP +18 % di flow sama + torque 7→15 kft·lb (sirkulasi) → indikasi pack-off
          Rekomendasi verifikasi: bandingkan SPP/torque dengan baseline, cek returns & cavings
 ▲A2 19:20 🟡 ADVISORY torque spike tunggal (belum terkorroborasi)
```

**Aturan skala & navigasi** (dari template Navita):
- **Skala per channel:** tiap channel punya min–max sendiri di panel kiri. Klik angka untuk mengetik, atau pakai **Auto** / **Auto ±10 %**.
- **Skala ppg bersama:** ECD ⓜ/ⓥ, FG_min, SFG, dan MW memakai satu skala ppg yang bisa dikunci 🔒.
- **Preset:** "Navita default", "Hidraulik", "Mekanik", "Loss/Influx". Opsi track terpisah tersedia bila satu sumbu terlalu ramai.
- **Navigasi waktu:**
  - **Picker** (5 mnt – 7 hari)
  - **Realtime** (auto-follow)
  - **Latest Scroll**
  - **Show All**
  - crosshair (nilai semua channel + depth + state)
  - penggaris 📏
  - cetak 🖨

**Degraded mode** [PHR 9.3]:
- Bila PWD hilang, ECD ⓥ otomatis menggantikan ⓜ dengan label jelas.
- Bila input rig stale, tampil ⚫ **UNAVAILABLE** dan **"terakhir valid 19:42 (18 mnt lalu)"** terpisah dari estimasi saat ini.
- Bila input OOD, tampil badge **LOW CONFIDENCE** dan pita melebar.

### 1b. Log format (waktu ↓) + kolom ALERT

```
┌──────────────┬─────────┬──────────────────┬──────────────────┬──────────────────┬───────────────────────────┐
│ Bit Depth ft │  WAKTU  │ Torque · RPM     │ Flow · SPP       │ Active Pit · SPM │ ALERT                     │
│ ROP · Block  │         │ Hookload · WOB   │ Flow Out % · ECD │ Gain/Loss        │                           │
├──────────────┼─────────┼──────────────────┼──────────────────┼──────────────────┼───────────────────────────┤
│  │3,341      │ 08:10 ──│  ╲  WOB tag 8 klb│  ▏200→600 gpm    │  │              │ 🟡 08:10 tag @3,341 (TIH)  │
│   │3,796     │ 09:15 ──│  ╲ tag 8 klb     │  ▏ream 200-400   │  │              │ 🟡 09:15 tag berulang (2×) │
│   │3,746     │ 10:20 ──│  ╲ tag 8 klb     │  ▏               │  │              │ 🟠 10:20 tag ke-3 dlm 2 j  │
│    │4,566    │ 11:55 ──│  ╲ tag 8 klb     │  ▏               │  │              │ 🟠 11:55 pola tight hole   │
│     │5,093   │ 14:30 ──│  ▲torque ⟋ RPM→0 │  ▏MFO turun      │  ╲ pit turun     │ 🔴 14:30 overpull + indikasi│
│     │5,051   │ 14:50 ──│  ━ overpull      │                  │                  │    loss (perlu verifikasi)│
│              │         │                  │                  │                  │ ⛔ 14:50 STUCK (DDR)       │
└──────────────┴─────────┴──────────────────┴──────────────────┴──────────────────┴───────────────────────────┘
 Contoh PDSI 53.2 (ilustrasi). Event ⛔ berasal dari katalog event (DDR), bukan dari sistem.
```

### 1c. Panel pressure window & alert card

```
┌─────────────────────────────────────────────────────┬────────────────────────────────────────┐
│ PRESSURE WINDOW  (PPFG v2 approved · TVD datum RKB)   │ ALERT TERBARU                           │
│  batas bawah max(PP,SFG) 10.6 ── MW 10.0 ── ECD ⓥ10.7 │ 🟠 19:12 indikasi pack-off @5,540 ft     │
│  ── FG_min bit 13.3 / open hole min 13.1 @5,360 ft    │   SPP +18 %, torque 7→15 · data OK       │
│  Margin atas  bit : 2.6 (2.4–2.8)   🟢                │   rekomendasi verifikasi: …  [Ack ✍]     │
│  Margin atas  OH  : 2.4 (estimasi)  🟢                │ 🟡 18:40 margin bawah 0.1 ppg            │
│  Margin bawah     : 0.1             🟡                │ [Riwayat Event →] [Analisis Anomali →]   │
│  Margin statis (pumps off): −0.6 → 🟠 rekomendasi     │                                         │
│   verifikasi MW vs SFG dengan Mud Eng / Geomech       │                                         │
│  uncertainty FG: tidak tersedia di Rec 03             │                                         │
└─────────────────────────────────────────────────────┴────────────────────────────────────────┘
```

**Tingkat alert** [PHR 8.4] (usulan default, disetujui Drilling Eng + HSE):

| Tingkat | Kondisi | Warna |
|---|---|---|
| 🟢 Normal | tidak ada kondisi di bawah. Artinya "tidak ada anomali terdeteksi pada data yang tersedia", **bukan** "aman lanjut" | hijau |
| 🟡 Advisory | margin ≤ 0,5 ppg, **atau** ECD naik > 0,2 ppg/5 mnt, **atau** 1 indikator anomali tanpa korroborasi | kuning |
| 🟠 Warning | margin ≤ 0,25 ppg bertahan, **atau** ≥ 2 indikator saling menguatkan, **atau** MW statis < batas bawah saat pumps off | oranye |
| 🔴 Critical | margin atas ≤ 0 (confidence OK), **atau** indikasi loss/influx dari pit/flow, **atau** beberapa indikator stuck + risk score tinggi | merah + bunyi |
| ⚫ Unavailable | data stale / input kritis invalid. Badge *Low confidence* untuk OOD | abu |

> **Pumps off:** ECD dinamis disuppress. Yang dibandingkan adalah **MW vs batas bawah** (mekanisme sloughing saat pompa mati, dari klien).
> **Pumps on:** sloughing umumnya **mekanis**, sehingga dipantau lewat torque, overpull, dan SPP.

---

## 2. Profil Depth — dashboard inti #2

Kontrol production [PHR 4.3, 9.2]: **switch MD/TVD, PPFG berversi, batas section/shoe, exposure interval, uncertainty, depth reference**. Permintaan klien yang ditampung di sini: evaluasi MW statis vs SFG (istilah klien "MWW", pengganti "pre-drill").

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Profil Depth — Gula010   Section: [☑12.25"][☑8.5"]   Sumbu: (●)TVD ( )MD   Datum: RKB  │
│ PPFG: Rec 03 v2 (approved, 19 Nov) [Bandingkan versi ▾] · MW: Rec 04 · ECD: Rec 02 + ⓥ │
├──────────┬──────────────────────────────────────────────────────┬────────────────────┤
│ FORMASI  │ ppg → 8     9     10    11    12    13    14    15    │ RINGKASAN          │
│ / SHOE   │ ft ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐  │                    │
│          │1600│ ┃    ═══ ┊ ●             │      ║           │  │ Interval MW < SFG: │
│ ─ shoe ─ │2400│  ┃      ┊═══●            │        ║         │  │ 3,180–3,420 ft     │
│          │3200│  ┃       ═┊══●  ◄ MW<SFG │       ║          │  │ MW 11.0 vs SFG 11.2│
│ ░ open   │4000│  ┃    ═══ ┊  ●           │         ║        │  │ → rekomendasi      │
│ ░ hole   │4800│ ┃ ═══     ┊ ●            │      ║           │  │   verifikasi       │
│ ░ (expo- │5600│  ┃    ═══ ┊  ●           │      ║           │  │ Margin atas min OH:│
│ ░ sed)   │6400│  ┃     ═══┊  ●           │         ║        │  │ 2.4 ppg @ 4,870 ft │
│          │    └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘  │                    │
│          │ ┃ PP ═══ SFG ┊ MW ● ECD ⓜ ◆ ECD ⓥ ║ FG_min ░ uncertainty │ [Lompat ke waktu]│
├──────────┴──────────────────────────────────────────────────────┴────────────────────┤
│ Mode: (●) Aktual  ( ) Rencana MW (informasi; tandai interval di luar window)          │
│ Tabel: | Depth | Formasi | PP | SFG | MW | ECD | FG_min | MW−bawah | FG−ECD | Catatan |[CSV]│
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- **Exposure interval** (shoe → bit) diarsir. Margin atas dihitung di bit **dan** di titik terlemah open hole [PHR 2.2].
- **Caliper Rec 08** hanya tampil bila Rec 08 disetujui sebagai data opsional.

---

## 3. Riwayat Event — dashboard inti #3

Kontrol production [PHR 4.3, 9.2]: **engineer confirmation, incident type, label confidence, review workflow, evidence traceability, audit**. Label engineer disimpan **terpisah dari flag noise sensor** [PHR 6.2].

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Riwayat Event   Room: [Semua ▾] Kategori: [Semua ▾] Review: [Semua ▾] Tgl: [__ – __]   │
├──────┬─────────────┬──────────┬────────┬──────────────────┬──────────────┬─────┬────────┤
│Tingk.│ Onset       │ Room     │ MD ft  │ Bukti            │ Kategori     │Conf.│ Review │
├──────┼─────────────┼──────────┼────────┼──────────────────┼──────────────┼─────┼────────┤
│ ⛔   │07 Nov 14:50 │PDSI 53.2 │ 5,051  │ DDR / laporan    │ Stuck (mech.)│ T   │ ✅ RTO  │
│ 🟠   │07 Nov 08:10 │PDSI 53.2 │ 3,341  │ tag berulang     │ Tight hole   │ S   │ ✅ DE   │
│ 🟠   │20 Nov 19:12 │GW339     │ 5,540  │ SPP↑ torque↑     │ Pack-off     │ S   │ ⏳ menunggu│
│ 🔴   │07 Nov 14:30 │PDSI 53.2 │ 5,093  │ MFO↓ pit↓        │ Loss         │ T   │ ✅ RTO  │
│ ▒    │30 Okt 03:15 │Gula010   │ 2,940  │ ECD 30.17 spike  │ Noise sensor │ —   │ ✅ MWD  │
├──────┴─────────────┴──────────┴────────┴──────────────────┴──────────────┴─────┴────────┤
│ ▼ Detail: log format ±2 j · nilai vs baseline · versi model & PPFG saat itu · ack log │
│   lampiran (DDR, foto cavings) · riwayat review (siapa, kapan, ubah apa)              │
│   [Konfirmasi] [Ubah kategori] [Tolak]                                                │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- **Kategori:** Loss · Influx · Pack-off/poor hole cleaning · Tight hole/sloughing · Differential sticking · Mechanical sticking · Stuck · Noise sensor · Belum.
- **Confidence:** T (tinggi) / S (sedang) / R (rendah).
- **Status review:** Draft → Menunggu review → Dikonfirmasi / Ditolak. Hanya event **dikonfirmasi** yang masuk **katalog event** untuk validasi [PHR 4.5A, 8.3].

---

## 4. Data & Upload — dashboard inti #4

Kontrol production [PHR 4.3, 9.2]: **Rec 01/02 time/depth; 03/04/07 depth; schema QC; source lineage; clock drift; target availability**.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Data & Upload   Room: [GW339 · BLSE-056 ▾] [+ Room baru]                              │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ 📁 Tarik zip hasil download Navita (boleh banyak) — record, basis, format dikenali     │
│ ☐ Folder dipantau: /data/navita_download   Mode: (●) Tambah (inkremental) ( ) Ganti   │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ KELENGKAPAN 5 RECORD           Time based              Depth based                    │
│ Rec 01 IDS Rig                 ✅ 27 Okt – 20 Nov       ✅                             │
│ Rec 02 MWD/PWD                 ✅ 27 Okt – 20 Nov       ✅                             │
│ Rec 03 PPFG                    —                        ✅ v2 (approved)               │
│ Rec 04 Mud Weight              —                        ✅                             │
│ Rec 07 Survey                  —                        ✅                             │
│ (Rec 08 LWD — opsional, tidak ada)                                                    │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ TARGET AVAILABILITY (label ECD)  ███████████░░░░░░░ 62 % waktu pumps-on punya ECD valid │
│                                  20 Nov run 6-1/8": ECD kosong → ECD ⓥ (inferensi)      │
│ TIMELINE COVERAGE  27 Okt ████████████████░██████████████ 20 Nov  (gap 20 Nov 04:17–06:01)│
│ SCHEMA QC Rec 01: ✅ fitur wajib · ⚠ ACTC=0 (state diturunkan) · ⚠ TVA/GL kosong →     │
│                   active pit dari tank aktif (pemetaan menunggu konfirmasi)            │
│ SAMPLING: Rec 01 1–14 dtk (median 7) → resample 5 dtk · Rec 02 30 dtk                 │
│ CLOCK DRIFT Rec01↔Rec02: offset +3 dtk (cross-corr SPP) ✅ · match depth 99.2 %        │
│ OUTLIER: ECD > 20 / < 7 ppg: 37 titik [Review log]   Nilai negatif SPP/WOB Rec 02 [⚠]  │
│ LINEAGE: file → raw table → canonical → feature table  [Lihat diagram]  [Unduh QC ⬇]   │
│ ALIAS mnemonic dipakai: tank GW339 (ACTIVESLUG, TANK3–5…)                             │
│ Sign-off QC: [Belum] → [✍ Sign-off RTO]                                               │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Formasi & FG — dashboard inti #5

Kontrol production [PHR 4.3, 9.2]: **version effective date, approver, interval applicability, TVD datum, uncertainty**. Data diisi dari Rec 03 (PP, SFG, FG Min/Max) dan Rec 04 (MW). Setiap perubahan menjadi **versi baru berstatus draft** sampai di-approve.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Formasi & FG — Gula010    Versi: [v2 ▾] [Bandingkan v1↔v2]                            │
│ Status v2: ✅ APPROVED oleh Geomechanics (…), 19 Nov · effective date 19 Nov          │
│ TVD datum: RKB · berlaku: 1,600–6,500 ft MD (section 12.25" & 8.5") · sumber: Rec 03  │
├────────────┬────────┬────────┬───────┬───────┬────────┬────────┬────────┬────────────┤
│ Interval   │ Top MD │ Bot MD │ PP    │ SFG   │ MW     │ FG_min │ FG_max │ Cek        │
├────────────┼────────┼────────┼───────┼───────┼────────┼────────┼────────┼────────────┤
│ …          │ 1,600  │ 2,400  │ 8.33  │ 9.1   │ 10.0   │ 13.6   │ 15.0   │ ✅          │
│ …          │ 2,400  │ 3,200  │ 8.66  │ 10.8  │ 10.4   │ 13.6   │ 15.4   │ ⚠ MW<SFG    │
│ …          │ 3,200  │ 4,000  │ 8.66  │ 11.2  │ 11.0   │ 13.3   │ 15.6   │ ⚠ MW<SFG    │
│ …          │ 4,000  │ 4,900  │ 8.66  │ 9.4   │ 9.8    │ 13.7   │ 16.7   │ ✅          │
├────────────┴────────┴────────┴───────┴───────┴────────┴────────┴────────┴────────────┤
│ Uncertainty FG: [tidak tersedia di Rec 03] · Batas bawah: max(PP,SFG) (usulan)        │
│ MW effective-from: [sejak bit melewati depth ▾] (disetujui Mud Eng: …)                 │
│ [⬆ Import ulang Rec 03/04] [✎ Koreksi → draft v3] [✅ Approve (Geomech)] Riwayat: v2·v1│
└──────────────────────────────────────────────────────────────────────────────────────┘
```

> FG Min adalah angka model reservoir saat sumur akan dibor. Perubahannya masuk lewat import Rec 03 sebagai versi baru. **Model ECD tidak dilatih ulang** [PHR 7.4], dan event lama tetap dinilai dengan versi saat itu.

---

## 6. Model ML — dashboard inti #6

Kontrol production [PHR 4.3, 9.2]: **blind-well metrics, data lineage, promotion gate, rollback, group split, confidence, model registry**.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Model ML        Aktif: ecd-xgb v1 · status SHADOW 🟡 · konfigurasi: surface-only       │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ DATASET & SPLIT (grouped per sumur)                                                   │
│ │ Sumur            │ Section     │ Label ECD │ Peran          │ Coverage label │       │
│ │ BDSI61 Gula010   │ 12.25 · 8.5 │ Rec 02    │ train          │ …              │       │
│ │ BDSI18 / BDSI19  │ …           │ Rec 02    │ train          │ …              │       │
│ │ BDSI21 · GW336   │ …           │ Rec 02    │ train          │ …              │       │
│ │ ACS26 MANGGA0004 │ …           │ Rec 02    │ BLIND (tetap)  │ …              │       │
│ │ BEKA-253/254/255 │ 12.25 · 8.5 │ template  │ train          │ …              │       │
│ │ GW339 · PDSI 53.2│ …           │ ✗ / parsial│ studi kasus   │ —              │       │
│ Split: (●) Grouped CV per sumur + blind tetap  ( ) LOWO diagnostik   [Reset split]    │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ HASIL BLIND (pumps on, data valid) — diisi setelah uji                                │
│ │Eksp│ Model      │ Section│ MAE │ RMSE │ R² │ P95 │ Bias │ Latency │ OOD % │ vs A   │ │
│ │ A  │ hidraulik* │ 8.5    │ …   │ …    │ …  │ …   │ …    │ …       │ …     │ —      │ │
│ │ B  │ RF         │ 8.5    │ …   │ …    │ …  │ …   │ …    │ …       │ …     │ …      │ │
│ │ C  │ XGBoost    │ 8.5    │ …   │ …    │ …  │ …   │ …    │ …       │ …     │ …      │ │
│ │ D  │ LightGBM   │ 8.5    │ …   │ …    │ …  │ …   │ …    │ …       │ …     │ …      │ │
│ │ E/F│ LSTM / hybrid (bila memenuhi syarat)                                          │ │
│ * bila reologi belum ada: MW-only (ditandai). Kinerja per section & per operating state│
│ ℹ Akurasi split acak per baris terlihat ~100 % karena bocor; yang dilaporkan blind-well│
├──────────────────────────────────┬───────────────────────────────────────────────────┤
│ Actual vs predicted · residual    │ SHAP (asosiasi, bukan kausal): MW · SPP · Hookload │
│ by depth/flow · kalibrasi         │ · Flow · TVD · RPM                                │
├──────────────────────────────────┴───────────────────────────────────────────────────┤
│ PROMOTION GATE: QC ✅ · blind-well ✅ · engineering review ⏳ · shadow ⏳ · threshold ⏳ │
│                 · rollback teruji ⏳   [Promote → Production] (nonaktif)  [Rollback v0] │
│ LINEAGE: data v2025-11-21 · code a1b2c3 · hyperparams · approval log [Lihat]          │
│ DRIFT: feature drift 0.08 (OK) · error drift (shadow) …                               │
│ Modul stuck-pipe (H4): event dikonfirmasi 2 → mode rules + anomaly scoring (offline)  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## A. Analisis Anomali (pendukung — UI modul stuck-pipe, PHR-H4)

> Label halaman: **"Modul tambahan · hipotesis H4 · offline/shadow"** [PHR 1.6, 8.3]. Fungsinya bukan memprediksi stuck, melainkan menampilkan **kondisi abnormal sejak jam berapa** beserta bukti channel.

Pertanyaan klien: *"Data 53.2 ada 3 hari, bagaimana menganalisis seolah jam 12 siang 7 Nov?"* File tidak perlu dihapus. Pilih **Cut-off**, dan sistem hanya memakai data ≤ cut-off (no look-ahead [PHR 5.4]).

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Analisis Anomali — PDSI 53.2 · BLSE-57 HW MSF   [modul tambahan · H4]  ( )Live (●)Cut-off│
│ Cut-off: [07 Nov 2026] [12:00] ◀ 15 mnt ▶   Data dipakai: 06 Nov 07:45 → 07 Nov 12:00   │
│ Baseline: [06 Nov 07:45 – 07 Nov 06:00 ▾] (auto: periode tanpa event)                  │
│ Setelah cut-off: (●) tampilkan abu-abu (verifikasi) ( ) sembunyikan  [▶ Jalankan]       │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ TREN ECD ⓥ (tanpa PWD · run BHA #4 · basis waktu · di bit depth)        skala 8–14 ppg │
│  FG_min ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ 13.3      │
│  ECD ⓥ  ▁▁▂▁▁▂▁▁▁▂▁▁▁▂▂▂▃▃▅▆│░░░  ±pita ketidakpastian   ▲ spike 13:10, 14:00     │
│  SFG    ·····························································  10.8     │
│  MW     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  10.0     │
│  (pompa mati / tripping → ECD ⓥ disuppress, garis putus)                              │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ RISK SCORE 0–100   ▁▁▁▁▁▁▁▁▂▃▃▅▅▄▅▆▆▆│░░░░███ ⛔ (DDR)                                 │
│                    06 Nov ── 07 Nov 08:10 ── 10:20 ── 12:00 ── 14:50                   │
│ Hasil s.d. cut-off: 🟠 Warning sejak 10:20 · indikasi pertama 08:10                     │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ │ Indikator                 │ Mulai │ Nilai vs baseline     │ z    │ Tingkat │ State │ │
│ │ Tag / set-down berulang    │ 08:10 │ 4× tag 8 klb dlm 4 j  │ —    │ 🟠      │ TIH   │ │
│ │ Overpull P/U               │ 10:20 │ 141 vs 133 klb        │ +2.4 │ 🟡      │ ream  │ │
│ │ Torque saat reaming        │ 11:55 │ 2.8–3.0 vs 2.1 kft·lb │ +2.1 │ 🟡      │ ream  │ │
│ │ SPP / flow (pack-off)      │  —    │ normal                │ +0.6 │ 🟢      │       │ │
│ │ Flow out % / pit (loss)    │  —    │ normal s.d. cut-off   │ +0.3 │ 🟢      │       │ │
│ │ Lonjakan ECD ⓥ (BHA #4)    │ 13:10 │ +0.3 ppg/10 mnt, flow sama │ +2.2 │ 🟡  │ ream  │ │
│ Kategori dugaan: tight hole/sloughing → mechanical sticking (bukan differential)       │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ VERIFIKASI (abu-abu): 14:30 overpull + torque + RPM stop + MFO turun · 14:50 stuck     │
│ → Lead time vs onset DDR: indikasi pertama 6 j 40 mnt · Warning 4 j 30 mnt (ilustrasi) │
│ → False alarm di periode normal: … /hari                                              │
│ [Simpan studi kasus → validation pack]  [Buat laporan →]                              │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

| Pola | Channel | Logika awal (hipotesis, diuji) |
|---|---|---|
| Tag / set-down berulang | WOB, hookload, bit depth, block | slack-off turun ≥ N klb dari baseline, ≥ 2× dalam T jam |
| Overpull / drag | hookload, block | P/U − baseline(depth, pump state) > batas |
| Torque spike / stall | torque, RPM | torque > baseline + kσ; RPM → 0 |
| Pack-off / hole cleaning | SPP, flow, flow out %, torque | SPP naik di flow tetap + torque naik ± flow out turun |
| **Lonjakan ECD ⓥ** 🆕 (run tanpa PWD) | ECD ⓥ, flow, RPM, MW | naik ≥ x ppg dalam y mnt **pada flow/RPM/MW sama**, menetap; abaikan N mnt setelah pompa hidup, connection, perubahan flow/MW → **pintu masuk** pack-off/hole problem, dicek silang SPP/torque/overpull |
| Residual ECD positif | ECD ⓜ − ECD ⓥ | hanya bila label ECD ada |
| Differential (pipa diam lama) | block, durasi, MW − PP | stationary time > batas + overbalance besar |
| MW statis < batas bawah | MW, SFG, durasi pumps off | lalu fill/tag saat pompa hidup |

**Tren ECD ⓥ untuk run tanpa PWD (usulan klien, 21 Nov 2026).** Di run BHA tanpa tool ECD (mis. PDSI 53.2 BHA #4, cleanout run), halaman menampilkan track **ECD ⓥ + pita ketidakpastian** terhadap SFG, FG_min, dan MW. Spike/kenaikan mendadak ditandai ▲ dan masuk tabel indikator. Ground truth = **report PHR yang sudah dirilis**; lead time dihitung dari spike pertama ke kronologi report. Label tetap "estimasi, akurasi dibuktikan di sumur blind".

Semua pola dihitung **per operating state**. Pack-off, differential, dan mechanical sticking dievaluasi terpisah [PHR 4.5A].

---

## R. Laporan (pendukung)

Untuk kebutuhan klien: *"laporan analisa deteksi anomali stuck pipe 53.2 dengan presentasi pakai AI"*. Laporan ini juga mendukung deliverable *pilot report* dan *validation pack* [PHR 1.5, 10.1].

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Laporan   Sumber: [Studi kasus: PDSI 53.2 cut-off 07 Nov 12:00 ▾]                     │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Isi: ☑ Kronologi (katalog event)  ☑ Log + alert  ☑ Tabel indikator & lead time         │
│      ☑ Risk score  ☑ Pressure window (PPFG versi)  ☑ Metrik & false alarm  ☑ Keterbatasan│
│ Narasi: (●) AI (layanan eksternal) dari ringkasan hasil (bisa diedit)  ( ) manual      │
│ Format: [📄 PDF] [📊 PPTX] [📝 DOCX]                                  [▶ Buat laporan]  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- AI hanya menerima **ringkasan hasil** (waktu, depth, indikator, angka ringkas), bukan data mentah Navita.
- Narasi selalu menyertakan catatan: *hipotesis penelitian, bukan bukti sistem mampu memprediksi stuck pipe*. Klaim dibatasi pada metrik yang benar-benar diuji [PHR 7.3].
- Kalimat final dikonfirmasi klien/koordinator sebelum dikirim.

---

## S. Pengaturan (pendukung)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Pengaturan                                                                            │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ AMBANG ALERT (versi v1 · disetujui: Drilling Eng ⏳ · HSE ⏳)  [Ajukan perubahan]       │
│  Advisory margin ≤ [0.5] ppg · ECD naik > [0.2] ppg / [5] mnt                          │
│  Warning  margin ≤ [0.25] ppg bertahan · ≥ [2] indikator terkorroborasi                │
│  Critical margin atas ≤ [0] · indikasi loss/influx pit/flow                            │
│  Anomali: tag ≥ [5] klb · overpull ≥ [20] klb · torque > baseline+[3]σ ·                │
│           SPP naik ≥ [10]% · flow out turun ≥ [10]% · pit Δ ≥ [5] bbl                   │
│  Durasi minimum [60] dtk · hysteresis [on] · umur data maks [30] mnt                   │
│  Batas ECD valid [7.0]–[20.0] ppg · pumps off bila flow < [100] gpm                    │
│ TAMPILAN: preset skala [Navita default ▾] · orientasi (●)Horizontal ( )Log format      │
│           zona waktu tampilan [WIB]                                                   │
│ SUMBER DATA: (●) Upload zip ( ) Folder pantau ( ) WITSML (nanti)                      │
│ NOTIFIKASI: [☐ Email]                                                                  │
│ AKUN LOKAL: [+ Tambah user] [Reset password] [Nonaktifkan]  peran: [▾ Bab 10.2]        │
│ LAYANAN AI LAPORAN: [☑ Aktif] kunci API [••••••] (hanya ringkasan hasil dikirim)       │
│ AUDIT LOG: [Lihat] (upload, ack, label, approval, promote, perubahan ambang)           │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Perubahan ambang menghasilkan **versi baru** yang baru berlaku setelah disetujui Drilling Eng + HSE [PHR 8.4, 10.2].

---

## Backlog di luar proposal (tidak dibangun tanpa persetujuan — Desain Lampiran H C6)

| Fitur | Asal | Alasan ditunda |
|---|---|---|
| Panel **what-if** (ubah flow/RPM/ROP/MW → ECD) | desain v1–v2 | tidak ada di proposal. Model pohon tidak bisa ekstrapolasi, dan berisiko dibaca sebagai perintah [PHR 8.4] |
| **Proyeksi ECD** per depth ke depan | desain v1–v2 | forecast adalah fase terpisah setelah uji prospektif [PHR 5.1] |
| **Citra cutting** (CNN cavings) | chat klien | tidak ada di proposal; butuh SOP foto & label |
| Notifikasi WhatsApp/Telegram | desain v2 | menunggu kebijakan keamanan PHR [PHR 9.3] |

---

## Catatan Implementasi UI

- **Grafik:** Plotly WebGL atau komponen log-track. Skala per channel memakai sumbu-y tersembunyi per trace dengan label min–max di panel kiri.
- **Downsampling:** min/max per bucket agar spike tidak hilang. Gap ditampilkan sebagai ▒, tidak disambung garis.
- **Teknologi:** MVP Streamlit + Plotly. Live Monitor & Analisis Anomali memakai React + FastAPI bila picker/drag berat.
- **Grafik depth:** sumbu-y terbalik.
- **Layar:** layar rig (TV) & laptop, dengan mode full-screen.
- **Badge wajib di setiap angka prediksi:** freshness, model version, confidence.
- Urutan implementasi ada di `TODO.md` §4 (per fase roadmap).
