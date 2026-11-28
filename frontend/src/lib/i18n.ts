/** Bahasa tampilan ID / EN (permintaan klien 28 Nov; default English).
 *
 * Teks sumber di kode tetap bahasa Indonesia dan sekaligus menjadi kunci kamus: t("Simpan") → "Save" saat EN.
 * Variabel memakai placeholder {nama}: t("Tersimpan v{p0}", { p0: 3 }). Kunci yang belum ada di kamus tampil
 * apa adanya (bahasa Indonesia) dan dicatat sekali di console agar mudah dilengkapi.
 * Pilihan bahasa disimpan di localStorage; ganti bahasa = muat ulang halaman, sehingga t() cukup fungsi biasa
 * (juga aman dipakai di konstanta tingkat modul). */
import { EN } from "./i18n.en";

export type Lang = "en" | "id";
const KEY = "ecd_lang";

export const lang: Lang = (() => {
  try { return localStorage.getItem(KEY) === "id" ? "id" : "en"; } catch { return "en"; }
})();

export function setLang(l: Lang) {
  try { localStorage.setItem(KEY, l); } catch { /* ignore */ }
  location.reload();
}

const missing = new Set<string>();

export function t(s: string, vars?: Record<string, unknown>): string {
  let out = s;
  if (lang === "en") {
    const e = EN[s];
    if (e !== undefined) out = e;
    else if (!missing.has(s)) { missing.add(s); console.debug("[i18n] belum ada EN:", s); }
  }
  return vars ? out.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k] ?? "") : m)) : out;
}

/** Daftar teks yang belum diterjemahkan pada sesi ini (untuk dicek di console: __i18nMissing()). */
(globalThis as any).__i18nMissing = () => [...missing];
