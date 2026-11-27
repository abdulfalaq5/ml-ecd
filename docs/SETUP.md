# Setup & Migrasi Sistem Paningal Sense

Semua komponen jalan di Docker: database (PostgreSQL + TimescaleDB), backend (FastAPI + ML), frontend (React + nginx). Server cukup punya **Docker Engine + Docker Compose v2**. Python, Node dan Postgres tidak perlu dipasang di server.

```
browser ──► frontend (nginx :8080) ──/api──► backend (:8000) ──► db (TimescaleDB)
                                               │
                                               └─ volume appdata: /data/uploads, /data/models, /data/reports
                                               └─ folder inbox (host): data/inbox/<nama sumur>/
```

---

## 1. Instalasi pertama

```bash
# 1) salin folder proyek ke server (git clone / scp / flashdisk)
cd ecd

# 2) buat konfigurasi
cp .env.example .env
nano .env        # minimal ganti: DB_PASSWORD, SECRET_KEY, ADMIN_PASSWORD
                 # SECRET_KEY acak: openssl rand -hex 32

# 3) build & jalankan
docker compose up -d --build

# 4) cek
docker compose ps                # semua "running / healthy"
curl http://localhost:8080/api/health
```

Buka `http://<ip-server>:8080`, lalu login dengan `ADMIN_USERNAME` / `ADMIN_PASSWORD` dari `.env`. Setelah itu **ganti password** di menu Pengaturan dan buat akun per peran (RTO, Drilling Eng, HSE, dll.).

> Build pertama mengunduh ±400 MB (Python ML + Node). Di jaringan lambat bisa 20–40 menit; build berikutnya memakai cache.

## 2. Memasukkan data

Ada tiga cara. Hasilnya sama.

| Cara | Langkah |
|---|---|
| **Upload di browser** | Data & Upload → pilih sumur (atau `+ Sumur`) → pilih file `.las` / `.csv` / `.zip` |
| **Folder pantau** | Taruh file di `data/inbox/<nama sumur>/…`. File di-scan otomatis tiap 60 detik (`WATCH_INTERVAL_S`). Nama folder = nama sumur. |
| **Baris perintah (impor massal)** | `docker compose exec backend python -m app.cli import "/data/inbox/PDSI 53.2" --well "PDSI 53.2"` |

Folder pantau di host bisa dipindah, misalnya ke share folder Navita: `HOST_INBOX_DIR=/mnt/navita` di `.env`, lalu jalankan `docker compose up -d`.

Setelah data masuk, lakukan langkah ini di aplikasi:

1. Data & Upload → **Edit sumur**: isi section, **shoe MD**, dan peran (`train` / `blind` / `case` / `shadow`).
2. Formasi & FG → **Approve** versi PPFG (Rec 03). Margin dan alert hanya memakai versi yang sudah approved.
3. Model ML → **Mulai training**, lalu isi promotion gate.

## 3. Operasi harian

```bash
docker compose ps                     # status
docker compose logs -f backend        # log backend (ingest, training)
docker compose restart backend        # restart backend
docker compose down                   # stop semua (data tetap aman di volume)
docker compose up -d                  # start lagi
docker compose exec backend pytest -q # uji parser
```

Update versi aplikasi:

```bash
./scripts/backup.sh                    # selalu backup dulu
# salin kode baru (git pull / timpa folder backend & frontend)
docker compose up -d --build
```

Tabel database dibuat dan diperbarui otomatis saat backend start.

## 4. Backup

```bash
./scripts/backup.sh
```

Skrip ini menghasilkan folder `backups/<tanggal_jam>/` berisi:

| File | Isi |
|---|---|
| `ecd.dump` | seluruh database: sumur, data time/depth, PPFG, event, model, setting, akun, audit |
| `appdata.tgz` | file mentah yang di-upload, file model `.joblib`, laporan |
| `env.backup` | salinan `.env` (berisi password, simpan dengan aman) |

Untuk backup terjadwal, misalnya tiap jam 01:00, tambahkan ke `crontab -e`:

```
0 1 * * * cd /opt/ecd && ./scripts/backup.sh >> backups/backup.log 2>&1
```

## 5. Migrasi ke server lain

**Di server lama:**

```bash
cd ecd
./scripts/backup.sh                         # mis. menghasilkan backups/20261121_010000
tar czf ../ecd-kode.tgz --exclude=./backups --exclude=./data --exclude=./frontend/node_modules .
scp ../ecd-kode.tgz user@server-baru:/opt/
scp -r backups/20261121_010000 user@server-baru:/opt/ecd-backup
```

Folder inbox (`data/inbox`) berisi file sumber. Ikut salin jika masih dibutuhkan; semua file yang sudah di-ingest juga tersimpan di `appdata.tgz`.

**Di server baru** (cukup Docker + Compose):

```bash
cd /opt && mkdir ecd && tar xzf ecd-kode.tgz -C ecd && cd ecd
mkdir -p backups && mv /opt/ecd-backup backups/20261121_010000
cp backups/20261121_010000/env.backup .env   # konfigurasi sama (ubah WEB_PORT/HOST_INBOX_DIR bila perlu)
docker compose build
./scripts/restore.sh backups/20261121_010000
```

Lalu periksa hasilnya:

- buka `http://<server-baru>:8080` dan login dengan akun lama;
- Overview: semua sumur muncul;
- Model ML: model aktif masih ada;
- Pengaturan → Audit log: riwayat masih utuh.

Setelah server baru terverifikasi, matikan server lama dengan `docker compose down`. Jangan pakai `down -v`, karena `-v` menghapus volume data.

**Server tanpa internet:** build image di mesin yang punya internet, lalu pindahkan image-nya:

```bash
# mesin ber-internet
docker compose build
docker save ecd-backend:latest ecd-frontend:latest timescale/timescaledb:2.17.2-pg16 | gzip > ecd-images.tgz
# server tujuan
gunzip -c ecd-images.tgz | docker load
docker compose up -d          # tanpa --build
```

## 6. Publikasi lewat domain (nginx + Cloudflare)

Contoh: `dev-paningalsense.lokatali.my.id`. Alurnya: browser → Cloudflare (HTTPS) → cloudflared → nginx host :80 → `127.0.0.1:8095` (container).

**Sebelum DNS diaktifkan:**

1. `.env`:
   ```
   WEB_BIND=127.0.0.1      # aplikasi hanya bisa diakses lewat nginx host
   DOCS_ENABLED=false      # sembunyikan /api/docs
   SECRET_KEY=<acak>       # openssl rand -hex 32 — JANGAN pakai nilai bawaan
   ```
   Lalu jalankan `docker compose up -d`.
2. Login sebagai admin, lalu **ganti password** di Pengaturan. Password bawaan `admin123` tidak boleh dipakai di server publik.
3. Pasang konfigurasi nginx host dari `deploy/nginx/dev-paningalsense.lokatali.my.id`:
   ```bash
   sudo cp deploy/nginx/dev-paningalsense.lokatali.my.id /etc/nginx/sites-available/
   sudo ln -s /etc/nginx/sites-available/dev-paningalsense.lokatali.my.id /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```
4. Di Cloudflare Tunnel, arahkan hostname ke `http://localhost:80`, sama seperti subdomain lain.

Konfigurasi nginx tersebut sudah memuat:
- batas 10 percobaan login per menit per IP;
- IP asli pengguna dari header `CF-Connecting-IP`;
- upload hingga 1 GB dan timeout 600 detik.

> **Batas upload Cloudflare.** Paket Free/Pro membatasi body request **100 MB**, jadi file Rec 01 mingguan (300–400 MB) akan gagal di-upload lewat domain (error 413). File sebesar itu dimasukkan lewat folder pantau `data/inbox/<sumur>/` atau CLI di server. Upload lewat browser tetap bisa untuk file < 100 MB, atau lewat `http://localhost:8095` dari server.

## 7. Konfigurasi penting (`.env`)

| Variabel | Fungsi |
|---|---|
| `WEB_PORT` | port web (default 8080) |
| `WEB_BIND` | `0.0.0.0` = bisa diakses dari jaringan; `127.0.0.1` = hanya lewat reverse proxy di server |
| `DOCS_ENABLED` | `false` untuk menyembunyikan dokumentasi API `/api/docs` |
| `CORS_ORIGINS` | kosongkan (frontend & API satu domain) |
| `DB_PASSWORD` | password database (hanya dipakai di dalam jaringan Docker) |
| `SECRET_KEY` | kunci tanda tangan sesi login. Kalau diganti, semua user harus login ulang. |
| `ADMIN_USERNAME/PASSWORD` | akun admin awal, hanya dibuat jika belum ada |
| `HOST_INBOX_DIR` | folder pantau di host (di dalam container selalu `/data/inbox`) |
| `SOURCE_TZ` | zona waktu kolom `dtsrv`/`TIME` di file (default Asia/Jakarta). Data disimpan dalam UTC dan ditampilkan dalam WIB. |
| `ANTHROPIC_API_KEY` | opsional, untuk narasi laporan AI. Yang dikirim hanya ringkasan angka hasil analisis, bukan data mentah. |

## 8. Masalah umum

| Gejala | Solusi |
|---|---|
| `port is already allocated` | ganti `WEB_PORT` di `.env` |
| Login gagal setelah restore | pastikan `.env` (SECRET_KEY, ADMIN_*) disalin dari `env.backup` |
| File di inbox tidak terbaca | file harus berada di dalam subfolder sumur (`inbox/<sumur>/file.las`); cek `docker compose logs backend` |
| Upload besar gagal | batas nginx 1 GB (`frontend/nginx.conf` → `client_max_body_size`); lewat Cloudflare maks 100 MB → pakai folder inbox |
| Alert selalu UNAVAILABLE | sumur berperan `shadow` dan data terakhir > 10 menit; normal untuk data offline |
| Margin kosong | PPFG belum di-approve, atau shoe MD belum diisi |
