# Rencana integrasi estimasi bending ke aplikasi

Status per 22 Nov 2026:
- **Siap:** modul hitung `backend/app/core/bending.py` + test, katalog `backend/app/bending_catalog.json`, dan script `tools/bending`.
- **Belum dibuat:** tabel DB, API, dan UI di dokumen ini. Menunggu klien menyepakati isi katalog (ukuran rig PHR, jumlah DC/HWDP per section, datasheet batas sambungan).

## 1. Posisi fitur

Aplikasi ini adalah **lapisan analisa di atas Navita**, bukan pengganti tampilan realtime Navita (keputusan klien, 22 Nov 2026). Navita sudah punya tampilan realtime. Aplikasi fokus ke yang tidak ada di Navita: ECD ⓥ, estimasi bending / side force / hookload model, margin PPFG, deteksi anomali, studi kasus, dan laporan.

Data masuk lewat ekspor file, sehingga hasil bending bersifat **near-realtime**. Delay-nya sama dengan interval ekspor Rec 01.

## 2. Alur data

```
Katalog (items + presets)  ──►  Runs per sumur ("mulai hole depth X → preset Y", seperti MW Rec 04)
                                        │
Survey Rec 07 ──► κ (min. curvature) ──►│
Rec 01 Time (bit depth, hole depth, hookload, rpm) ──► run dipilih dari hole depth tertinggi (hole_reached_robust)
Rec 04 MW ──► faktor apung              │
                                        ▼
                     app.core.bending.compute()  →  profil per kedalaman · channel per 30 s · cek batas sambungan
```

## 3. Penyimpanan (usulan tabel)

| Tabel | Kolom utama | Catatan |
|---|---|---|
| `string_items` | `id` (kode, mis. `DC_7`), `type`, `name`, `od`, `id_in`, `weight_ppf`, `tj_od`, `joint_ft`, `grade`, `connection`, `bend_limit_dls`, `bend_limit_ksi`, `active` | Isi awal dari `bending_catalog.json`. Item yang sudah dipakai tidak dihapus, hanya `active=false` |
| `string_presets` | `id`, `kind` (drill/casing/liner), `name`, `bit_size`, `friction` (json), `components` (json: item + count/length) | |
| `well_string_runs` | `well_id`, `from_hole_md`, `preset_id` atau `components` (json), `counts`/`lengths` (json), `hole_size`, `shoe_md_ft`, `setting_md_ft`, `friction`, `remark`, `created_by`, `created_at` | **Depth-based** seperti `mud_weight`. Run aktif = `from_hole_md` terbesar ≤ hole depth yang sudah dicapai |

Perubahan katalog, preset, dan runs tercatat di `audit_log`.

## 4. Hak akses (usulan, mengikuti pola `PERM` di `security.py`)

| Aksi | Peran |
|---|---|
| Lihat katalog, runs, dan hasil bending | semua peran yang login |
| Isi / ubah runs per sumur | `well_edit` (admin, data_ml, rto) |
| Ubah katalog & preset (termasuk batas sambungan) | usul: `threshold_propose`; setujui: `drilling_eng`, admin |

## 5. API (usulan)

| Method & path | Fungsi |
|---|---|
| `GET /api/string/catalog` | Item + preset |
| `POST/PUT /api/string/items`, `/api/string/presets` | Kelola katalog (dengan approval) |
| `GET/PUT /api/wells/{id}/string-runs` | Runs per sumur (validasi lewat `runs_from_spec`) |
| `GET /api/wells/{id}/bending?t0&t1&calibrate` | Hasil `compute()`: channel waktu (di-cache seperti analisis lain) + ringkasan per run + peringatan |
| `GET /api/wells/{id}/bending/limits?setting_md` | Cek batas sambungan (perencanaan, tanpa data waktu) |
| `GET /api/wells/{id}/bending.las` | Ekspor channel LAS. Bisa di-import ke Navita bila Navita mendukung |

## 6. UI (usulan)

- **Data & Upload → Edit sumur → tab "String & Lubang"**: tabel runs. Setiap baris berisi mulai hole depth, preset (dropdown), jumlah DC/HWDP, hole size, shoe, dan setting depth (untuk casing). Ada tombol "Cek batas sambungan".
- **Pengaturan → Katalog String**: daftar item dan preset, dengan alur usul → setujui.
- **Analisis Anomali & Live Monitor**: channel `BND_BHA_EST`, `SF_MAX_EST`, `BEND_UTIL_MAX`, `HKLD_RESID` bisa dipilih di picker, ditambah track broomstick (hookload PU/SO/ROT model vs terukur).
- **Profil Depth**: kolom DLS + bending stress + zona yang melewati batas sambungan.
- **Panduan**: entri "Cara" dan "Batasan" yang sudah ada diperbarui saat fitur masuk.

## 7. Yang perlu dari klien sebelum dibangun

1. Konfirmasi isi katalog: ukuran DP/HWDP/DC yang benar-benar dipakai (OD, ID, ppf; tool joint DP 5" = 6-5/8"?), serta ukuran casing/liner dan connection-nya.
2. Jumlah DC dan HWDP tipikal per section (12-1/4", 8-1/2", 6-1/8").
3. Datasheet batas bending sambungan (°/100 ft atau ksi) untuk connection casing/liner.
4. Apakah entri BHA bisa dilakukan di Navita sebagai record manual (seperti Rec 04), atau cukup di aplikasi.
5. Apakah Navita bisa ekspor otomatis terjadwal (mengurangi delay) dan import channel LAS (menampilkan hasil di Navita).

## 8. Tahap berikutnya (setelah poin 7)

1. Tabel + migrasi + seed dari `bending_catalog.json`.
2. API + cache hasil `compute()` per (sumur, versi runs, data terakhir).
3. UI tab "String & Lubang" + channel di picker grafik.
4. Mode drilling on-bottom (WOB di bit) + torque model (FF × side force × jari-jari tool joint) → `TQ_RESID`.
5. Kalibrasi ambang dengan event stuck berlabel.
