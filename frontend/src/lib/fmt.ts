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

export const LEVEL_COLOR: Record<string, string> = {
  NORMAL: "#4CC38A", ADVISORY: "#E8C547", WARNING: "#F59E4B", CRITICAL: "#F2555A", UNAVAILABLE: "#8A96A3",
  STUCK: "#F2555A", NOISE: "#8A96A3",
};
export const C = {
  ecd: "#FF9F43", fg: "#F2555A", sfg: "#E8C547", mw: "#7DB4FF", pp: "#B48CF2",
  text: "#E6EAEF", muted: "#9AA5B1", grid: "#222B34", panel: "#171D24",
  hook: "#4CC38A", torque: "#FF6B9A", flow: "#7DB4FF", spp: "#F59E4B", fo: "#5FD3E0", pit: "#B48CF2",
  rpm: "#C5CDD6", wob: "#A3E635", rop: "#FACC15", depth: "#9AA5B1",
};
export const STATE_LABEL: Record<string, string> = {
  DRILL_ROT: "DRILLING ROTARY", SLIDE: "SLIDING", REAM: "REAMING", WASH: "WASHING", CIRC: "SIRKULASI",
  TRIP: "TRIPPING", STATIC: "STATIK / POMPA MATI",
};
