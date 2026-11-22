export const TZ = "Asia/Jakarta";

export function wib(iso?: string | null, withDate = false) {
  if (!iso) return "—";
  const d = new Date(iso);
  const o: Intl.DateTimeFormatOptions = { timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false };
  if (withDate) Object.assign(o, { day: "2-digit", month: "short", year: "numeric" });
  return d.toLocaleString("id-ID", o).replace(".", ":") + (withDate ? " WIB" : "");
}
export function dateOnly(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("id-ID", { timeZone: TZ, day: "2-digit", month: "short", year: "numeric" });
}
/** ISO -> nilai <input type=datetime-local> dalam WIB */
export function toLocalInput(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(new Date(iso).getTime() + 7 * 3600e3);
  return d.toISOString().slice(0, 16);
}
export function n(v: any, d = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}
export function ft(v: any) { return v === null || v === undefined ? "—" : Math.round(v).toLocaleString("en-US"); }
export function ago(min?: number | null) {
  if (min === null || min === undefined) return "—";
  if (min < 60) return `${Math.round(min)} mnt lalu`;
  if (min < 60 * 48) return `${Math.round(min / 60)} jam lalu`;
  return `${Math.round(min / 1440)} hari lalu`;
}

/** warna zona rathole (open hole di bawah shoe yang tidak ter-cover casing) */
export const RATHOLE = "#C77700";
export const ZONE_LABEL: Record<string, string> = { rathole: "Rathole", atas_shoe: "Atas shoe", bawah_rathole: "Bawah rathole" };
export const LEVEL_COLOR: Record<string, string> = {
  INFO: "#2F6FD1",
  NORMAL: "#1E9E5A", ADVISORY: "#B98900", WARNING: "#E07A10", CRITICAL: "#D63A40", UNAVAILABLE: "#7A8694",
  STUCK: "#D63A40", NOISE: "#7A8694",
};
export const C = {
  ecd: "#E8710A", fg: "#D63A40", sfg: "#B98900", mw: "#2F6FD1", pp: "#7C4DD8",
  text: "#1B2430", muted: "#5B6775", grid: "#E3E8EE", panel: "#FFFFFF",
  hook: "#1E9E5A", torque: "#D63A7A", flow: "#2F6FD1", spp: "#E07A10", fo: "#0E9AAE", pit: "#7C4DD8",
  rpm: "#3A4552", wob: "#5E9E0B", rop: "#A88400", depth: "#5B6775",
};
export const STATE_LABEL: Record<string, string> = {
  DRILL_ROT: "DRILLING ROTARY", SLIDE: "SLIDING", REAM: "REAMING", WASH: "WASHING", CIRC: "SIRKULASI",
  TRIP: "TRIPPING", STATIC: "STATIK / POMPA MATI",
};
