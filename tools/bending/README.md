# Estimasi bending moment & side force (alat bantu, belum ada tombol di aplikasi)

Script ini menghitung **estimasi** bending moment, bending stress, side force, dan hookload model untuk drill string, casing, dan liner. Inputnya survey (Rec 07) dan data rig berbasis waktu (Rec 01). Hasilnya berupa channel tambahan (CSV + LAS) untuk analisa tripping dan stuck pipe, dan bisa dibuka di Navita atau software log lain.

- Inti perhitungan ada di backend, `backend/app/core/bending.py`, dan sudah diuji dengan `tests/test_bending.py`.
- Katalog komponen dan preset ada di `backend/app/bending_catalog.json`.
- Script di folder ini hanya membaca input dan menulis output. Modul yang sama nanti dipakai aplikasi; rencananya ada di [`docs/BENDING_INTEGRATION.md`](../../docs/BENDING_INTEGRATION.md).

> **Estimasi, bukan pengukuran.** Sensor downhole (mis. `BND_MAX_DMM` SLB) mengukur lengkungan aktual, termasuk getaran, whirl, buckling, dan efek lubang membesar atau ledge. Script ini hanya menghitung lengkungan yang **dipaksakan oleh bentuk lubang**. Lubang dianggap slick dan pipa mengikuti sumbu lubang.

## Rumus

| Besaran | Rumus | Catatan |
|---|---|---|
| Kelengkungan κ | dogleg min. curvature antar stasiun survey ÷ ΔMD | Dihitung ulang dari INC/AZI, dicek terhadap `SDLS` di file |
| Bending moment | M = E · I · κ | E baja 30×10⁶ psi; I = π/64 (OD⁴ − ID⁴) dari ukuran **body** |
| Bending stress | σb = E · κ · OD / 2 | Dibandingkan dengan batas bending sambungan |
| Side force | soft-string Johancsik, elemen 30 ft (≈ 1 joint) | Mode pick-up; butuh berat string + friction factor |
| Hookload model | tension di permukaan (PU / SO / ROT, bit off-bottom) | Pembanding hookload terukur (broomstick) |

## Katalog, preset, dan runs per section

Konfigurasi string tidak perlu diketik ulang. Ada tiga lapis:

1. **Katalog komponen** (`items`): DP, HWDP, drill collar, BHA directional, casing, liner, hanger. Setiap item berisi:
   - OD dan ID body, berat, OD tool joint/coupling, grade, connection;
   - **batas bending sambungan** (`bend_limit_dls` °/100 ft dan/atau `bend_limit_ksi`).

   Isi awal memakai ukuran **nominal API**. Collar 8-1/4" (section 12-1/4") dan 7" (section 8-1/2") mengikuti info klien. **Batas sambungan sengaja dikosongkan** sampai ada datasheet pabrikan connection yang dipakai PHR.
2. **Preset per section** (`presets`), disusun dari katalog:

   | Preset | Isi |
   |---|---|
   | `BHA_12.25_STD` | BHA dir. 8" + 6 × DC 8-1/4" + 15 × HWDP 5" + DP 5" |
   | `BHA_8.5_STD` | BHA dir. 6-3/4" + 6 × DC 7" + 15 × HWDP 5" + DP 5" |
   | `BHA_6.125_STD` | BHA dir. 4-3/4" + 6 × DC 4-3/4" + 15 × HWDP 3-1/2" + DP 3-1/2" |
   | `CSG_13.375_RUN` / `CSG_9.625_RUN` / `CSG_7_RUN` | shoe track 85 ft + casing sampai permukaan |
   | `LNR_7_ON_DP5` / `LNR_4.5_ON_DP3.5` | shoe track + liner + hanger + landing string DP |

   Jumlah DC dan HWDP di preset adalah **angka tipikal**. Angka ini perlu dikonfirmasi klien dan bisa diganti per sumur.
3. **Runs per sumur** (`runs.json`): "mulai hole depth X → preset Y", **depth-based seperti MW di Rec 04 Navita**.
   - Run dipilih otomatis dari hole depth tertinggi yang sudah dicapai, memakai filter glitch yang sama dengan MW.
   - Saat **tripping keluar** dari section 8-1/2", BHA 8-1/2" tetap dipakai walaupun bit sudah naik ke dangkal.

```json
{
  "well": "BDSI 18",
  "runs": [
    {"from_hole_md": 0,    "preset": "BHA_12.25_STD", "hole_size": 12.25, "shoe_md_ft": 350},
    {"from_hole_md": 3000, "preset": "BHA_8.5_STD",   "hole_size": 8.5,   "shoe_md_ft": 2990, "counts": {"DC_7": 9}}
  ]
}
```

Isian per run:
- `counts` / `lengths` mengganti jumlah joint atau panjang komponen. Kuncinya id item katalog, atau `"#2"` (urutan komponen) bila item yang sama dipakai dua kali, misalnya shoe track dan liner.
- `shoe_md_ft` adalah shoe casing yang **sudah terpasang** saat run itu, dan menjadi batas friction cased/open hole. Untuk **run casing/liner**, isi dengan shoe casing **sebelumnya**. Kalau tidak, seluruh string dianggap di dalam casing dan script memberi peringatan.
- `setting_md_ft`: kedalaman set untuk run casing/liner, dipakai untuk cek batas sambungan.
- `hole_size`: dicatat untuk keperluan berikutnya (input model ECD). Tidak dipakai di soft-string.
- Komponen di luar katalog: ganti `"preset"` dengan `"components": [{name, od, id, length, weight_ppf, bha, bend_limit_dls}, …]` (lihat `string.manual.example.json`).

## Cara pakai

Jalankan dari root repo. Docker harus hidup karena script berjalan di container backend. File asli hanya disalin, tidak dipindah. Katalog dari repo selalu ikut dikirim, jadi perubahan katalog langsung berlaku tanpa build ulang.

```bash
tools/bending/run.sh --list-catalog                    # lihat item & preset
tools/bending/run.sh --example-runs runs.json          # contoh file runs per section

# sumur yang sudah ada di sistem, BHA per section
tools/bending/run.sh --well "BDSI 18" --runs runs.json --calibrate --out bending_out

# satu preset saja, mis. hanya periode run casing 7" GW339 + cek batas sambungan sampai kedalaman set
tools/bending/run.sh --well GW339 --preset CSG_7_RUN --shoe 2000 \
                     --from "2026-11-11 00:00" --to "2026-11-12 19:30" --setting-depth 5354 --calibrate

# langsung dari file Navita (LAS / CSV / zip)
tools/bending/run.sh --survey rec07.las --rig rec01_a.las rec01_b.las --mw rec04.las --preset BHA_8.5_STD
```

| Opsi | Fungsi |
|---|---|
| `--runs` / `--preset` / `--string` | Konfigurasi string (pilih satu). `--runs` disarankan |
| `--calibrate` | Per run: mencari friction factor open hole (0,05–0,55) dan berat block yang paling cocok dengan hookload PU/SO terukur. Berat block seharusnya mirip antar run; kalau sangat berbeda, konfigurasi string belum sesuai |
| `--from` / `--to` | Membatasi data waktu ke satu periode (zona `--tz`, default WIB) |
| `--setting-depth` | Kedalaman akhir run terakhir untuk cek batas sambungan |
| `--shoe` | Menimpa shoe dari database untuk semua run |
| `--catalog` | Memakai file katalog lain |
| `--step` | Grid kedalaman bit (default 50 ft) |

## Output

| Channel (per 30 detik, CSV + LAS) | Satuan | Arti |
|---|---|---|
| `RUN_IDX` | – | Run/section yang dipakai (1, 2, …) |
| `DLS_BIT` | °/100 ft | DLS di posisi bit |
| `BND_BHA_EST` | kft·lbf | Bending maks di komponen `bha: true` (BHA atau casing/liner) |
| `BND_STR_EST` | kft·lbf | Bending maks di seluruh string |
| `BSTR_MAX_EST` | ksi | Bending stress maks |
| `SF_MAX_EST` | klbf | Side force maks per joint (pick-up) |
| `BEND_UTIL_MAX` | rasio | Bending ÷ batas sambungan (1,0 = di batas). Hanya komponen yang batasnya diisi |
| `HKLD_EXP` | klb | Hookload model sesuai mode gerak (PU = POOH, SO = RIH, ROT) |
| `HKLD_RESID` | klb | Hookload terukur − model. Bernilai + saat PU berarti overpull di atas model; bernilai − saat SO berarti drag atau set-down |

File lain:
- `_bending_depth.csv`: profil per kedalaman bit per run.
- `_bending_limits.csv`: interval kedalaman ≥ 80% batas sambungan, berstatus `MENDEKATI` atau `LEWAT BATAS`.
- `_survey_dls.csv`
- `_summary.json`: ringkasan per run, termasuk hasil kalibrasi dan peringatan.

## Casing vs drill pipe

Pada DLS yang sama, casing jauh lebih kaku sehingga momennya jauh lebih besar. Contoh pada DLS 6°/100 ft:

| String | Bending moment | Bending stress |
|---|---|---|
| DP 5" 19,5 ppf | 3,1 kft·lbf | 6,5 ksi |
| Casing 7" 26 ppf | 9,1 kft·lbf | 9,2 ksi |
| Casing 9-5/8" 47 ppf | 31,1 kft·lbf | 12,6 ksi |
| Casing 13-3/8" 68 ppf | 88,3 kft·lbf | 17,5 ksi |

Untuk casing, yang paling berguna adalah **bending stress / DLS dibandingkan dengan batas sambungan**. Cek ini tidak butuh data waktu, jadi bisa dipakai untuk perencanaan sebelum run.

## Uji coba (22 Nov 2026)

| Uji | Hasil |
|---|---|
| Unit test (`pytest tests/test_bending.py`, 9 test) | DLS min. curvature = build rate; M = EIκ; hookload vertikal = berat terapung tanpa side force; PU > ROT > SO; utilisasi & cek batas; preset & override; pemilihan run saat trip keluar; end-to-end 2 run |
| BDSI 18, string contoh 6-3/4" + DP 5" | DLS maks 7,5°/100 ft @ 2.623 ft (selisih vs `SDLS` file 0,005°), bending BHA 27,4 kft·lbf. Kalibrasi FF 0,30: pick-up cocok (median 1,3 klb), slack-off horizontal meleset ±20 klb |
| BDSI 18, `runs` 12-1/4" → 8-1/2" (batas section 1.500 ft **asumsi**) | Run 1: bending BHA maks 53,7 kft·lbf (DC 8-1/4"); run 2: 31,9 kft·lbf (DC 7"). Berat block hasil kalibrasi berbeda (14 vs 35 klb), tanda bahwa konfigurasi/batas section asumsi belum sesuai |
| GW339 run casing 7" (11–12 Nov, set 5.354 ft; ppf 26 dan batas 3°/100 ft **asumsi**) | DLS maks 3,7 @ 4.051 ft → bending 5,7 kft·lbf, stress 5,7 ksi, utilisasi maks 1,25; 38 interval lewat batas asumsi. Kalibrasi 831 titik: median selisih PU −2,3 klb, SO +1,7 klb |

## Batasan

1. Hanya bending **statis** dari geometri lubang. Getaran, whirl, buckling, lubang membesar, dan ledge tidak terhitung.
2. Survey biasanya per ±90 ft, sehingga micro-dogleg di antaranya tidak terlihat.
3. Untuk BHA kaku, M = EIκ adalah batas atas, karena BHA bisa tidak mengikuti lubang sepenuhnya dan lebih banyak menyentuh dinding.
4. Model soft-string tidak memperhitungkan kekakuan pipa, buckling, maupun efek hidraulik (pompa) pada hookload. Mode drilling on-bottom dan torque model belum ada.
5. Tidak ada data bending terukur di sumur PHR yang ada, sehingga estimasi ini **belum tervalidasi**. Yang bisa dicek hanya kecocokan hookload model dengan hookload terukur.
6. Ambang "bending tinggi" untuk risiko stuck belum ada. Perlu dikalibrasi bersama Drilling Eng memakai event stuck yang sudah diberi label.
7. **Casing kaku:** kontak sebenarnya terpusat di coupling dan centralizer. M = EIκ adalah batas atas untuk body pipa, dan side force lokal di centralizer tidak terhitung (perlu model stiff-string + data centralizer).
8. Cek batas sambungan memakai DLS antar stasiun survey. DLS lokal bisa lebih tinggi dari itu, jadi utilisasi ≥ 80% sebaiknya sudah dianggap perlu perhatian.
9. Katalog masih nominal API dan jumlah DC/HWDP di preset masih tipikal. Hasil hanya sebaik konfigurasi yang diisi.
