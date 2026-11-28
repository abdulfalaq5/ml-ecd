/** Isi menu Panduan sesuai bahasa tampilan: guide.id.ts (Indonesia) / guide.en.ts (English).
 *  Kedua file harus berisi entri yang sama (id / key sama); perbarui keduanya bila UI berubah. */
import { lang } from "./i18n";
import * as ID from "./guide.id";
import * as EN from "./guide.en";

export type { Ctrl, Flow, HowTo, Limit, MenuGuide, Req, Term } from "./guide.id";
const G = lang === "en" ? EN : ID;
export const { ROLES_NOTE, FLOWS, MENUS, HOWTOS, TERMS, LIMITS, LIVE_REQS } = G;
