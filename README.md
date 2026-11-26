# ECD Monitor — Prediksi ECD Real-Time Berbasis Machine Learning

Sistem monitoring **Equivalent Circulating Density (ECD)** untuk operasi pengeboran. ECD diestimasi dari parameter permukaan rig (flow, SPP, RPM, hookload, kedalaman, MW, survey). Estimasi ini disebut **ECD ⓥ** (virtual ECD) dan dipakai pada run tanpa sensor PWD/ECD downhole, misalnya clean-out, reaming, dan BHA rotary. Hasilnya dibandingkan dengan PPFG untuk margin dan alert, dan dilengkapi detektor indikasi masalah lubang (pack-off, tight spot, loss, influx, stuck pipe).

> **Posisi aplikasi:** lapisan **analisa** di atas Navita, bukan pengganti tampilan realtime Navita. Aplikasi fokus pada yang tidak ada di Navita: ECD ⓥ, estimasi bending / side force / hookload model, margin PPFG, deteksi anomali, studi kasus, dan laporan. Data masuk dari file ekspor Navita, sehingga sifatnya **near-realtime**: tertinggal sebesar interval ekspor.

> Sistem ini **alat bantu keputusan**, bukan pengganti engineer. Setiap alert adalah *indikasi* yang wajib diverifikasi. Threshold hanya berlaku setelah disetujui Drilling Engineer + HSE.

Semua komponen berjalan di **Docker**. Server tidak perlu Python, Node, atau PostgreSQL.

---

## Daftar isi

1. [Fitur](#1-fitur)
2. [Arsitektur](#2-arsitektur)
3. [Alur kerja sistem](#3-alur-kerja-sistem)
4. [Setup di server dengan Docker](#4-setup-di-server-dengan-docker)
5. [Cara menggunakan](#5-cara-menggunakan)
6. [Backup & restore (import backup)](#6-backup--restore-import-backup)
7. [Migrasi ke server lain](#7-migrasi-ke-server-lain)
8. [Publikasi lewat domain (nginx + Cloudflare)](#8-publikasi-lewat-domain-nginx--cloudflare)
9. [Konfigurasi `.env`](#9-konfigurasi-env)
10. [Operasi harian & troubleshooting](#10-operasi-harian--troubleshooting)
11. [Struktur repo & pengembangan](#11-struktur-repo--pengembangan)

---

## 1. Fitur

| Area | Isi |
|---|---|
| **Ingest data** | LAS 2.0 & CSV/ASCII export Navita (Rec 01 rig, 02 ECD, 03 PPFG, 04 mud weight, 07 survey), LAS/CSV rig, file `.zip`. Masuk lewat upload browser, folder pantau, atau baris perintah. QC otomatis per file. |
| **Operating state** | DRILL_ROT, SLIDE, REAM, WASH, CIRC, TRIP, STATIC, diturunkan dari flow, RPM, bit vs hole depth, dan pergerakan block. |
| **Model ML** | Nowcast ECD dari fitur permukaan saja. Eksperimen A (MW-only, persistence), B Random Forest, C XGBoost, D LightGBM. Validasi grouped per sumur: *leave-one-well-out* (LOWO) + sumur blind tetap. Interval prediksi, deteksi out-of-distribution, promotion gate 6/6, dan status candidate → shadow → production + rollback. |
| **Margin & alert** | Margin terhadap FG_min (di bit dan titik terlemah open hole) dan batas bawah max(PP, SFG). Level **NORMAL / ADVISORY / WARNING / CRITICAL / UNAVAILABLE**, plus badge *low confidence*. |
| **Detektor anomali** | Pack-off (SPP naik di flow sama), torque spike/stall, overpull, tag/set-down, lonjakan ECD ⓥ, residual ECD, loss, influx, pipa diam lama (differential), MW statis < batas bawah. Semua baseline memakai data masa lalu saja (tanpa *look-ahead*). |
| **Mode cut-off** | Analisis retrospektif: engine hanya melihat data ≤ waktu T. Hasilnya dibandingkan dengan event terkonfirmasi untuk menghitung *lead time*. |
| **PPFG berversi** | Rec 03 masuk sebagai *draft*. Margin hanya memakai versi yang sudah **approved**; koreksi dibuat sebagai salinan versi baru. |
| **Zona rathole & studi kasus** | Zona open hole di bawah shoe (mis. casing di-set lebih awal) per sumur: diarsir di Profil Depth, ditandai di Live Monitor, dan setiap indikasi diberi label zona. Halaman Studi Kasus Rathole membagi analisis jadi dua fase: fase 1 menguji ECD ⓥ terhadap ECD terukur, fase 2 memantau tren hidraulik dan indikasi di zona rathole. |
| **Laporan** | Harian, event/studi kasus, evaluasi model, QC data, studi kasus rathole. Ekspor Excel/cetak. Narasi dibuat otomatis: **dibantu AI bila `ANTHROPIC_API_KEY` diisi**, atau dari templat angka laporan (tanpa AI) bila kosong / AI gagal. Ke AI hanya dikirim ringkasan angka. |
| **Ramalan ECD (roadmap)** | Ramalan ECD ke depan berbasis rencana operasi, seperti roadmap T&D tetapi berbasis waktu. Model ECD ⓥ / hidraulika annulus power-law (aktif bila PV & YP diisi; string dari katalog bending) dikalibrasi ke ECD terukur 1 jam terakhir, + respons RPM dan WOB → ROP → cutting. Sambung pipa disisipkan dari statistik sumur. Uji mundur 5 sumur: ECD tertinggi 6 / 12 jam meleset median 0,29 / 0,42 ppg (vs 0,35 / 0,50 bila "ECD tetap"). |
| **Estimasi bending & side force** | Bending moment (E·I·κ dari survey), bending stress vs **batas bending sambungan**, side force per joint, dan hookload model pick-up/slack-off (broomstick, friction factor dikalibrasi ke hookload terukur). Untuk drill string, run casing, dan run liner. Konfigurasi dari **katalog komponen + preset per section**, dipilih per run "mulai hole depth X" seperti MW Rec 04. Saat ini lewat script `tools/bending` (output CSV/LAS per 30 detik); rencana masuk aplikasi ada di [`docs/BENDING_INTEGRATION.md`](docs/BENDING_INTEGRATION.md). **Estimasi, bukan pengukuran sensor downhole.** |
| **Panduan di aplikasi** | Menu Panduan berisi alur kerja, fungsi setiap menu & tombol (beserta peran yang boleh memakainya), langkah "cara melakukan…", dan istilah, plus **kolom pencarian** berbahasa sehari-hari. |
| **Akses** | Akun lokal dengan peran (Admin, Drilling Eng, RTO, HSE, Geomechanics, Viewer) dan audit log untuk setiap perubahan. |

---

## 2. Arsitektur

```
 browser ──HTTPS──► (opsional) Cloudflare ─► nginx host ─► frontend :8080/8095 ─/api─► backend :8000 ─► db
                                                            (nginx + React)        (FastAPI + ML)   (PostgreSQL 16
                                                                                        │             + TimescaleDB)
                                                                                        ├─ volume appdata: /data/uploads, /data/models, /data/reports
                                                                                        └─ folder pantau (host): data/inbox/<nama sumur>/
```

| Service | Image | Fungsi |
|---|---|---|
| `db` | `timescale/timescaledb:2.17.2-pg16` | data time-series (hypertable), depth, PPFG, MW, survey, model, event, user, audit |
| `backend` | build `./backend` (Python 3.12, FastAPI, scikit-learn, XGBoost, LightGBM) | API, ingest, watcher folder, training, inferensi, detektor, laporan |
| `frontend` | build `./frontend` (React + Vite + ECharts, disajikan nginx) | 13 halaman UI (tema terang); meneruskan `/api` ke backend |
| `jupyter` | opsional (`--profile jupyter`) | notebook riset |

Data disimpan dalam **UTC**. Kolom waktu di file (`dtsrv`) dibaca sebagai **WIB** (`SOURCE_TZ`), dan tampilan juga dalam WIB.

---

## 3. Alur kerja sistem

### 3.1 Alur data → alert

```
File Navita/rig (.las/.csv/.zip)
   │  upload · folder pantau · CLI
   ▼
1. INGEST     parser → mapping kanal kanonik (mnemonics.yaml) + konversi satuan (torque lbf·ft → kft·lb) → QC → simpan
              Rec 01/02 → ts_data (time) / depth_data   Rec 03 → PPFG draft   Rec 04 → MW   Rec 07 → survey
   ▼
2. FITUR      bucket 30 dtk · gabung Rec 01 + Rec 02 · operating state · MW as-of hole depth tercapai − 10 ft
              (hole tercapai tahan glitch: lubang baru hanya di bit & saat pompa hidup; reset bila koreksi depth)
              · TVD/inklinasi dari survey · fitur permukaan (flow, SPP, RPM, WOB, ROP, hookload, torque, …)
   ▼
3. ECD ⓥ      model aktif (production → shadow → candidate) memprediksi ΔECD = ECD − MW, lalu ECD = MW + Δ
              + interval prediksi per state · flag OOD · pompa mati → ECD dinamis tidak dihitung
   ▼
4. MARGIN     terhadap PPFG approved: FG_min − ECD (bit & open hole), ECD − max(PP,SFG), MW vs batas bawah saat pumps off
   ▼
5. DETEKTOR   pack-off · torque · overpull · tag · lonjakan ECD ⓥ · residual · loss · influx · differential · MW statis
   ▼
6. ALERT      level per waktu + alasan + rekomendasi verifikasi → Live Monitor, Overview, Riwayat Event, Laporan
```

ECD acuan = **ECD terukur** (PWD) bila ada; selain itu **ECD ⓥ**. Bila pompa hidup tetapi ECD tidak bisa dihitung (misalnya MW Rec 04 belum ada), level menjadi **UNAVAILABLE**, bukan NORMAL.

### 3.2 Alur model ML

```
Sumur peran "train" (ber-label ECD PWD)          Sumur peran "blind" (tidak pernah ikut training)
          │                                                 │
          ▼                                                 │
  Baris berlabel: ECD 7–20 ppg, pompa hidup, flow & SPP ada, MW ada, tanpa glitch depth
          │                                                 │
          ├─► LOWO: tiap sumur ditahan bergantian → MAE per sumur, CI bootstrap, metrik per state
          │        (dipakai untuk MEMILIH model)            │
          ├─► fit final pada semua sumur train ─────────────┴─► uji blind (hanya DILAPORKAN)
          ▼
  Kandidat → isi promotion gate (QC, blind, review Drilling Eng, shadow, threshold, rollback)
          → Shadow → Production (6/6) · rollback = arsipkan & aktifkan versi lain
```

Peran sumur: `train` (training), `blind` (uji tetap), `case` (studi kasus, hanya inferensi), `shadow` (real-time, alert UNAVAILABLE bila data > 10 menit).

---

## 4. Setup di server dengan Docker

### 4.1 Kebutuhan

- Linux (Ubuntu 22.04+ atau sejenis), **Docker Engine 24+** dan **Docker Compose v2** (`docker compose version`)
- RAM ≥ 8 GB (disarankan 16 GB; ingest file Rec 01 400 MB memakai ±1,5 GB), disk ≥ 50 GB
- Build pertama mengunduh ±400 MB (paket Python ML + Node). Di jaringan lambat bisa 20–40 menit; build berikutnya memakai cache.

Instal Docker (Ubuntu):

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # logout/login ulang
```

### 4.2 Instalasi

```bash
# 1) ambil kode
git clone https://github.com/abdulfalaq5/ml-ecd.git ecd
cd ecd

# 2) konfigurasi
cp .env.example .env
nano .env
#   WAJIB diganti: DB_PASSWORD, SECRET_KEY (openssl rand -hex 32), ADMIN_PASSWORD
#   opsional: WEB_PORT (default 8080), WEB_BIND, HOST_INBOX_DIR

# 3) build & jalankan
docker compose up -d --build

# 4) cek
docker compose ps                         # db & backend "healthy", frontend "Up"
curl http://localhost:8080/api/health     # {"ok":true}
```

Buka `http://<ip-server>:8080`, lalu login dengan `ADMIN_USERNAME` / `ADMIN_PASSWORD` dari `.env`. Akun admin hanya dibuat sekali, saat tabel user masih kosong. **Segera ganti password** di menu Pengaturan, lalu buat akun per peran.

Tabel database dibuat dan diperbarui otomatis saat backend start.

### 4.3 Update versi aplikasi

```bash
./scripts/backup.sh            # selalu backup dulu
git pull
docker compose up -d --build
```

---

## 5. Cara menggunakan

> **Bingung cara melakukan sesuatu?** Buka menu **? · Panduan** lalu ketik pertanyaannya, misalnya "cek hasil training", "upload file besar", atau "menu A tombol jalankan" (lihat [5.4](#54-menu-panduan-bantuan-di-aplikasi)).

### 5.1 Halaman

| Menu | Kegunaan |
|---|---|
| **0 · Overview** | Kartu semua sumur aktif: level alert, ECD, margin, state, sparkline (refresh 60 dtk) |
| **1 · Live Monitor** | Track multi-kanal (horizontal / log format), ECD terukur vs ECD ⓥ + interval, FG & batas bawah, pressure window, alert terbaru + Ack. Mode realtime / picker waktu. Near-realtime: tertinggal sebesar interval ekspor Navita; tampilan realtime tetap di Navita |
| **2 · Profil Depth** | ECD, PPFG, MW, dan survey terhadap kedalaman, posisi shoe, dan arsir zona rathole |
| **3 · Riwayat Event** | Label event (stuck, pack-off, loss, …) dengan alur review Draft → Dikonfirmasi |
| **4 · Data & Upload** | Tambah sumur, upload file, hasil QC per file, kelengkapan record, edit sumur (section, shoe MD, peran, zona rathole), **data section depth-based** (lubang, casing, string katalog, PV/YP; dipakai Ramalan ECD), QC sign-off |
| **5 · Formasi & FG** | Versi PPFG (Rec 03): lihat, koreksi (salinan), **approve** oleh Geomechanics; aturan MW |
| **7 · Ramalan ECD** | Ramalan ECD beberapa jam ke depan (mis. 6–12 jam) dari **rencana operasi** (segmen bor / sirkulasi / pompa mati: target MD, jam, flow, RPM, WOB, ROP, MW), dengan sambung pipa (tekanan statis saat pompa mati), margin ke FG/PP, dan alert pertama. Tombol coba-coba flow / RPM / WOB / MW. Jam mulai di masa lalu = **mode uji coba**: data sesudahnya disembunyikan, lalu "Buka data asli" untuk membandingkan |
| **6 · Model ML** | Dataset per sumur, mulai training, perbandingan eksperimen, LOWO per sumur, metrik per state/clean-out, feature importance, promotion gate, status model |
| **A · Analisis Anomali** | Rentang waktu + **cut-off**: deteksi yang terlihat sampai T, data sesudah T (abu-abu), lead time vs event terkonfirmasi |
| **K · Studi Kasus Rathole** | Untuk sumur yang punya zona rathole. **Fase 1** menguji ECD ⓥ terhadap ECD terukur (MAE, bias, % masuk interval). **Fase 2** menampilkan per hari: jam pompa di rathole, SPP per 100 gpm, torque, ECD ⓥ, dan indikasi per zona. Dilengkapi timeline event, catatan interpretasi, dan tombol *Buat laporan (Excel)* |
| **R · Laporan** | Buat laporan harian/event/model/QC/studi kasus rathole, unduh Excel, cetak. Narasi otomatis (dibantu AI bila API key diisi) + label sumber narasi |
| **S · Pengaturan** | User & peran, ganti password, threshold alert & parameter detektor (usul → setujui), audit log, info sistem |
| **? · Panduan** | Alur kerja, fungsi setiap menu & tombol, cara melakukan sesuatu, istilah, dan pencarian |

### 5.2 Langkah kerja umum

1. **Buat sumur & masukkan data**
   - Data & Upload → `+ Sumur`, lalu upload `.las` / `.csv` / `.zip`; atau
   - taruh file di `data/inbox/<nama sumur>/…`. File di-scan otomatis tiap 60 detik, dan nama folder = nama sumur; atau
   - impor massal dari baris perintah:
     ```bash
     docker compose exec backend python -m app.cli import "/data/inbox/GW339" --well "GW339"
     docker compose exec backend python -m app.cli import "/data/inbox/GW339" --well "GW339" --mode replace --force  # proses ulang
     docker compose exec backend python -m app.cli scan   # scan folder pantau sekarang
     ```
   File yang sama (hash identik) tidak diproses dua kali. Rec 08 dan file kosong dilewati dengan keterangan.
2. **Lengkapi sumur** (Data & Upload → Edit sumur): section, **shoe MD**, dan **peran** (`train` / `blind` / `case` / `shadow`). Bila ada open hole di bawah shoe, isi juga **zona rathole** (top MD, base MD, berlaku sejak). Periksa hasil QC, lalu QC sign-off.
3. **Approve PPFG** (Formasi & FG). Tanpa PPFG approved dan shoe MD, margin tidak dihitung.
4. **Training** (Model ML → Mulai training). Pilih "Semua (A–D)": model terbaik dipilih dari LOWO dan dilaporkan pada sumur blind. Model baru berstatus `candidate` dan langsung dipakai untuk ECD ⓥ bila belum ada model shadow/production.
5. **Promosi model**: centang promotion gate. Shadow → Production butuh 6/6, dan engineering review oleh Drilling Eng.
6. **Monitoring**: pantau di Live Monitor/Overview, Ack alert, dan label event di Riwayat Event.
7. **Studi kasus / cut-off**: di Analisis Anomali, pilih rentang dan waktu cut-off untuk melihat indikasi apa yang sudah terlihat sebelum kejadian. Untuk masalah rathole, buka **Studi Kasus Rathole**.
8. **Laporan**: buat di menu Laporan, unduh Excel.

### 5.3 Catatan data

- MW wajib untuk ECD ⓥ (ECD = MW + komponen hidraulik). Sumur tanpa Rec 04 tidak ikut training dan statusnya UNAVAILABLE saat pompa hidup. MW bisa ditambahkan dengan CSV kecil berformat Rec 04:
  ```
  DEPTH,MUDWEIGHT,REMARK
  0,10.2,sumber: laporan harian ...
  ```
  dengan nama file mengandung `record_04`, misalnya `MW_manual_record_04.csv`.
- ECD = 0 di file berarti tidak ada sensor, dan disimpan sebagai kosong.
- Export LAS rig (tab) menulis nilai 0 sebagai `-999.25`. Parser mengisi 0 untuk kanal operasional (flow, RPM, WOB, …).

### 5.4 Menu Panduan (bantuan di aplikasi)

Menu **? · Panduan** (paling bawah di menu kiri) punya enam tab:

| Tab | Isi |
|---|---|
| **Alur kerja** | Langkah bernomor untuk alur utama (file data → laporan), alur harian RTO/Drilling Eng, dan alur Data/ML (data baru → model baru). Tiap langkah punya tautan ke menunya |
| **Menu & tombol** | Untuk setiap menu: fungsinya, kapan dipakai, dan tabel semua tombol/kontrol beserta fungsinya dan **peran yang boleh memakainya** |
| **Cara melakukan…** | Panduan langkah demi langkah, mis. cara training, cek hasil training, upload file besar, approve PPFG, konfirmasi event, analisis cut-off, isi zona rathole, ganti password, backup, dan menghitung estimasi bending moment (script terpisah) |
| **Batasan sistem** | Apa yang **tidak** bisa dilakukan sistem dan seberapa jauh hasilnya bisa dipercaya: lingkup (bukan sistem kontrol, NORMAL ≠ aman, bukan peramal, bukan simulator hidraulik, bending moment hanya estimasi), akurasi model per sumur blind, interval yang terlalu sempit di sumur baru, input yang belum dipakai model (ukuran lubang, BHA, reologi), kualitas data, PPFG, dan keterbatasan operasional |
| **Syarat Live Monitor** | Alur data realtime (Navita → ekspor berkala → folder pantau → analisis → layar) dan checklist syarat wajib/opsional, beserta gejalanya bila tidak terpenuhi |
| **Istilah** | ECD ⓥ, LOWO, sumur blind, MAE, OOD, interval prediksi, promotion gate, rathole, DLS, bending moment, side force, friction factor, dll. |

**Pencarian** (kolom di atas tab):
- Bisa memakai bahasa sehari-hari, dan sinonim umum dikenali. Contoh: "gimana cara latih ulang model" tetap menemukan *Cara melakukan training model*.
- Mengenali kode menu dan kata "tombol". Contoh: "menu A tombol jalankan" menampilkan tombol **Jalankan** di Analisis Anomali paling atas, dan "menu K" menampilkan isi menu Studi Kasus Rathole.
- Kata yang cocok di-*highlight*, dan setiap hasil punya tautan **Buka menu →**.
- Pencarian tersimpan di alamat halaman (`/panduan?q=...`), jadi bisa dibagikan ke rekan.

Isi panduan ada di satu file, [`frontend/src/lib/guide.ts`](frontend/src/lib/guide.ts). Bila menambah menu atau tombol baru, tambahkan juga deskripsinya di file ini supaya ikut tampil dan bisa dicari. Daftar peran di file itu mengikuti `PERM` di `backend/app/security.py`.

---

## 6. Backup & restore (import backup)

### 6.1 Membuat backup

```bash
./scripts/backup.sh
```

Hasilnya berupa folder `backups/<YYYYmmdd_HHMMSS>/`:

| File | Isi |
|---|---|
| `ecd.dump` | seluruh database (`pg_dump -Fc`): sumur, data time/depth, PPFG, MW, survey, event, model, setting, user, audit |
| `appdata.tgz` | volume `/data`: file mentah yang di-upload, file model `.joblib`, laporan (folder inbox tidak ikut) |
| `env.backup` | salinan `.env` (berisi password, **simpan dengan aman**) |

Backup terjadwal, misalnya tiap jam 01:00 (`crontab -e`):

```
0 1 * * * cd /opt/ecd && ./scripts/backup.sh >> backups/backup.log 2>&1
```

Simpan salinan folder backup di luar server, misalnya dengan `rsync`/`scp` ke NAS atau storage lain. Folder `backups/` tidak masuk git.

### 6.2 Restore / import backup

> **Perhatian:** restore **menimpa** seluruh data di instalasi tujuan.

```bash
# folder backup harus berada di dalam folder proyek, mis. backups/20261122_010000
cp backups/20261122_010000/env.backup .env     # bila instalasi baru / pindah server
docker compose build                            # bila image belum ada
./scripts/restore.sh backups/20261122_010000
```

Skrip ini akan:
1. meminta konfirmasi;
2. menyalakan `db`;
3. membuat ulang database;
4. menjalankan `timescaledb_pre_restore()` → `pg_restore` → `timescaledb_post_restore()`;
5. mengekstrak `appdata.tgz` ke volume `/data`;
6. menjalankan semua service.

Setelah restore, periksa:
- login dengan akun lama (butuh `SECRET_KEY` dan password yang sama dari `env.backup`);
- Overview: semua sumur muncul;
- Model ML: model aktif masih ada;
- Pengaturan → Audit log: riwayat masih utuh.

---

## 7. Migrasi ke server lain

**Server lama**

```bash
cd ecd
./scripts/backup.sh                                   # mis. backups/20261122_010000
scp -r backups/20261122_010000 user@server-baru:/opt/ecd-backup
# (opsional) file sumber di folder pantau
rsync -a data/inbox/ user@server-baru:/opt/ecd-inbox/
```

**Server baru** (cukup Docker + Compose)

```bash
cd /opt && git clone https://github.com/abdulfalaq5/ml-ecd.git ecd && cd ecd
mkdir -p backups && mv /opt/ecd-backup backups/20261122_010000
cp backups/20261122_010000/env.backup .env            # sesuaikan WEB_PORT / HOST_INBOX_DIR bila perlu
docker compose build
./scripts/restore.sh backups/20261122_010000
```

Setelah server baru terverifikasi, hentikan server lama dengan `docker compose down`. **Jangan** pakai `down -v`, karena `-v` menghapus volume data.

**Server tanpa internet**: build image di mesin yang punya internet, lalu pindahkan image-nya:

```bash
docker compose build
docker save ecd-backend:latest ecd-frontend:latest timescale/timescaledb:2.17.2-pg16 | gzip > ecd-images.tgz
# di server tujuan:
gunzip -c ecd-images.tgz | docker load
docker compose up -d        # tanpa --build
```

---

## 8. Publikasi lewat domain (nginx + Cloudflare)

Contoh konfigurasi: [`deploy/nginx/dev-paningalsense.lokatali.my.id`](deploy/nginx/dev-paningalsense.lokatali.my.id). Alurnya: Cloudflare (HTTPS) → cloudflared → nginx host :80 → `127.0.0.1:<WEB_PORT>`.

1. `.env`: `WEB_BIND=127.0.0.1`, `DOCS_ENABLED=false`, `SECRET_KEY` acak, lalu `docker compose up -d`.
2. Pastikan password admin **bukan** bawaan.
3. Pasang konfigurasi nginx:
   ```bash
   sudo cp deploy/nginx/dev-paningalsense.lokatali.my.id /etc/nginx/sites-available/
   sudo ln -s /etc/nginx/sites-available/dev-paningalsense.lokatali.my.id /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```
   Sesuaikan `server_name` dan port `proxy_pass` bila berbeda.
4. Cloudflare Tunnel: arahkan hostname ke `http://localhost:80`.

Konfigurasi tersebut sudah memuat:
- batas 10 percobaan login per menit per IP;
- IP asli dari header `CF-Connecting-IP`;
- upload hingga 1 GB dan timeout 600 detik.

> Cloudflare Free/Pro membatasi upload **100 MB** per request. File Rec 01 mingguan (300–400 MB) dimasukkan lewat folder pantau atau CLI di server.

---

## 9. Konfigurasi `.env`

| Variabel | Default | Fungsi |
|---|---|---|
| `WEB_PORT` | `8080` | port web di host |
| `WEB_BIND` | `0.0.0.0` | `127.0.0.1` = hanya bisa diakses lewat reverse proxy di server |
| `DB_USER` / `DB_NAME` / `DB_PASSWORD` | `ecd` | akun database (hanya di jaringan internal Docker) |
| `SECRET_KEY` | — | kunci tanda tangan token login. **Wajib acak.** Kalau diganti, semua user harus login ulang |
| `TOKEN_HOURS` | `12` | masa berlaku sesi login |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / — | akun admin awal (dibuat sekali) |
| `HOST_INBOX_DIR` | `./data/inbox` | folder pantau di host (di container selalu `/data/inbox`) |
| `WATCH_ENABLED` / `WATCH_INTERVAL_S` | `true` / `60` | watcher folder pantau |
| `SOURCE_TZ` / `DISPLAY_TZ` | `Asia/Jakarta` | zona waktu kolom waktu file / tampilan |
| `DOCS_ENABLED` | `true` | dokumentasi API di `/api/docs` (matikan di server publik) |
| `CORS_ORIGINS` | kosong | isi hanya bila frontend di domain lain |
| `ANTHROPIC_API_KEY` / `AI_MODEL` | kosong / `claude-opus-5-5` | **Kosong** → narasi laporan dibuat otomatis tanpa AI (templat dari angka laporan). **Diisi** → narasi dibantu AI; bila AI gagal (key salah, koneksi, limit) kembali ke narasi tanpa AI dan alasannya ditampilkan. Ke AI hanya dikirim ringkasan angka, bukan data mentah. Setelah mengubah: `docker compose up -d` |
| `APP_VERSION` | `latest` | tag image |

---

## 10. Operasi harian & troubleshooting

```bash
docker compose ps                          # status
docker compose logs -f backend             # log ingest, watcher, training
docker compose restart backend
docker compose down                        # stop (data aman di volume)
docker compose up -d                       # start
docker compose exec backend pytest -q      # test otomatis
```

| Gejala | Solusi |
|---|---|
| `port is already allocated` | ganti `WEB_PORT` di `.env` |
| Login gagal setelah restore | salin `.env` dari `env.backup` (SECRET_KEY & ADMIN_*) |
| File di inbox tidak terbaca | file harus di subfolder sumur: `inbox/<sumur>/file.las`; cek `docker compose logs backend` |
| Upload 413 lewat domain | batas Cloudflare 100 MB → pakai folder pantau / CLI |
| Margin kosong | PPFG belum di-approve atau shoe MD belum diisi |
| ECD ⓥ kosong / UNAVAILABLE | MW (Rec 04) belum ada, atau belum ada model; cek Model ML |
| Alert UNAVAILABLE di sumur shadow | data terakhir > 10 menit (normal untuk data offline) |
| Halaman Studi Kasus Rathole kosong | zona rathole sumur belum diisi → Data & Upload → Edit sumur |
| Training gagal "tidak ada sumur training dengan label" | set peran `train` pada sumur yang punya Rec 02 ECD + Rec 04 MW |

---

## 11. Struktur repo & pengembangan

```
backend/                 FastAPI + ML
  app/ingest/            parser LAS/CSV, mapping kanal (mnemonics.yaml), QC, watcher
  app/core/              data loader, operating state & fitur, margin, alert, analisis, studi kasus rathole,
                         bending.py (estimasi bending / side force / hookload model, dipakai tools/bending)
                         forecast.py (ramalan ECD berbasis rencana: sambung pipa, respons flow/RPM/WOB, margin, uji mundur)
                         hydraulics.py (rugi gesek annulus power-law dari PV/YP + geometri string katalog + tool joint)
                         sections.py (data section per sumur depth-based: lubang, casing, string, PV/YP)
  app/bending_catalog.json  katalog komponen string + preset per section (nominal API, menunggu konfirmasi klien)
  app/ml/pipeline.py     dataset, training A–D, LOWO/blind, inferensi
  app/anomaly/           detektor anomali
  app/reports/           laporan + narasi AI
  app/routers/           endpoint API
  tests/                 pytest (test parser memakai fixture data klien yang tidak di-commit → otomatis dilewati)
frontend/                React + Vite + ECharts, disajikan nginx
  src/pages/             satu file per menu (Panduan.tsx = menu Panduan)
  src/lib/guide.ts       isi menu Panduan (alur, menu & tombol, cara, istilah)
scripts/                 backup.sh, restore.sh
tools/bending/           script estimasi bending / side force (run.sh, contoh runs per section) → CSV/LAS; lihat README di folder itu
deploy/nginx/            contoh reverse proxy untuk domain
docs/                    SETUP, desain sistem, data dictionary (CHANNELS), mockup UI, TODO/roadmap, BENDING_INTEGRATION
docker-compose.yml
.env.example
```

Data sumur, dokumen klien, `.env`, backup, dan file model **tidak** disimpan di git (lihat `.gitignore`).

Dokumentasi rinci: [`docs/SETUP.md`](docs/SETUP.md) (instalasi), [`docs/DOKUMEN_DESAIN_SISTEM_ECD.md`](docs/DOKUMEN_DESAIN_SISTEM_ECD.md) (desain), [`docs/CHANNELS.md`](docs/CHANNELS.md) (kamus kanal), [`docs/TODO.md`](docs/TODO.md) (status & roadmap).
