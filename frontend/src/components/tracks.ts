import { t as L } from "../lib/i18n";
import { AX, TIP } from "./ui";
import { wib, C, LEVEL_COLOR } from "../lib/fmt";

export type Ch = { key: string; name: string; unit: string; color: string; min?: number; max?: number; dash?: boolean; band?: [string, string] };
export type Track = { title: string; ppg?: boolean; ch: Ch[] };

export const CHANNELS: Record<string, Ch> = {
  hookload: { key: "hookload", name: "Hookload", unit: "klb", color: C.hook, min: 0, max: 250 },
  torque: { key: "torque", name: "Torque", unit: "kft·lb", color: C.torque, min: 0, max: 25 },
  flow_in: { key: "flow_in", name: "Flow In", unit: "gpm", color: C.flow, min: 0, max: 900 },
  spp: { key: "spp", name: "SPP", unit: "psi", color: C.spp, min: 0, max: 4000 },
  rpm: { key: "rpm", name: "RPM", unit: "rpm", color: C.rpm, min: 0, max: 200 },
  wob: { key: "wob", name: "WOB", unit: "klb", color: C.wob, min: 0, max: 50 },
  rop: { key: "rop", name: "ROP", unit: "ft/h", color: C.rop, min: 0, max: 200 },
  block_pos: { key: "block_pos", name: "Block Pos", unit: "ft", color: C.depth },
  bit_depth: { key: "bit_depth", name: "Bit Depth", unit: "ft", color: C.depth },
  ecd: { key: "ecd", name: L("ECD terukur"), unit: "ppg", color: C.ecd },
  ecd_pred: { key: "ecd_pred", name: "ECD ⓥ", unit: "ppg", color: C.ecd, dash: true, band: ["ecd_lo", "ecd_hi"] },
  ecd_po: { key: "ecd_po", name: L("ECD di bawah sensor (pack-off, estimasi)"), unit: "ppg", color: "#B42318", band: ["ecd_pred", "ecd_po_hi"] },
  ecd_po_hi: { key: "ecd_po_hi", name: L("ECD pack-off batas atas (sumbatan total)"), unit: "ppg", color: "#B42318", dash: true },
  fg_bit: { key: "fg_bit", name: "FG bit", unit: "ppg", color: C.fg },
  lower_bit: { key: "lower_bit", name: "max(PP,SFG)", unit: "ppg", color: C.sfg, dash: true },
  mw: { key: "mw", name: "MW", unit: "ppg", color: C.mw },
  flow_out_pct: { key: "flow_out_pct", name: "Flow Out", unit: "%", color: C.fo, min: 0, max: 100 },
  active_pit: { key: "active_pit", name: "Active Pit", unit: "bbl", color: C.pit },
  gain_loss: { key: "gain_loss", name: "Gain/Loss", unit: "bbl", color: "#B42318" },
  risk: { key: "risk", name: L("Skor risiko"), unit: "0–1", color: "#D63A40", min: 0, max: 1 },
};

export const PRESETS: Record<string, string[][]> = {
  "Navita default": [["hookload", "torque"], ["flow_in", "spp"], ["ecd", "ecd_pred", "ecd_po", "fg_bit", "lower_bit", "mw"], ["flow_out_pct", "active_pit"]],
  Hidraulik: [["flow_in", "spp"], ["ecd", "ecd_pred", "ecd_po", "fg_bit", "lower_bit", "mw"], ["rpm", "rop"]],
  Mekanik: [["hookload", "wob"], ["torque", "rpm"], ["bit_depth", "block_pos"], ["ecd", "ecd_pred", "mw"]],
  "Loss/Influx": [["flow_in", "flow_out_pct"], ["active_pit", "gain_loss"], ["ecd", "ecd_pred", "ecd_po", "fg_bit", "lower_bit", "mw"]],
};

type Opt = { vertical?: boolean; hidden?: Record<string, boolean>; marks?: { t0: string; t1?: string; label: string; level: string }[];
  ppgRange?: [number, number]; cutoff?: string | null; after?: Record<string, any[]> | null };

/** Bangun option ECharts multi-track (horizontal: waktu → kanan; vertikal: format log, waktu ↓). */
export function buildTracks(s: Record<string, any[]>, tracks: Track[], o: Opt = {}) {
  const t = s.t || [];
  const n = tracks.length;
  const V = !!o.vertical;
  const grid: any[] = [], xAxis: any[] = [], yAxis: any[] = [], series: any[] = [];
  const gap = 2, pad = V ? 4 : 3;
  tracks.forEach((tr, i) => {
    const size = (100 - pad * 2 - gap * (n - 1)) / n;
    const start = pad + i * (size + gap);
    grid.push(V ? { left: `${start}%`, width: `${size}%`, top: 54, bottom: 28 } : { left: 64, right: 64, top: `${start + 3}%`, height: `${size - 3}%` });
    const timeAx = { type: "time", gridIndex: i, ...AX, axisLabel: { ...AX.axisLabel, show: V ? i === 0 : i === n - 1, formatter: (v: number) => wib(new Date(v).toISOString()) }, splitLine: { show: true, lineStyle: { color: "#F4F6F9" } }, inverse: V, min: "dataMin", max: "dataMax" };
    const chs = tr.ch.filter((c) => !o.hidden?.[c.key] && s[c.key]);
    const ppgTrack = tr.ch.some((c) => c.unit === "ppg");
    const axes = ppgTrack ? [{ min: o.ppgRange?.[0] ?? 8, max: o.ppgRange?.[1] ?? 16, name: "ppg", key: "__ppg" }] :
      chs.slice(0, 2).map((c) => ({ min: c.min, max: c.max, name: `${c.name} ${c.unit}`, key: c.key, color: c.color }));
    const axIdx: Record<string, number> = {};
    if (V) xAxis.push(...[]);
    else xAxis.push(timeAx);
    const valueAxes = (axes.length ? axes : [{ name: tr.title, key: "_" }]).map((a: any, j: number) => {
      const ax = { type: "value", gridIndex: i, ...AX, min: a.min, max: a.max, scale: a.min === undefined, name: a.name,
        nameLocation: "middle", nameGap: V ? 18 : 44, position: V ? (j === 0 ? "top" : "bottom") : (j === 0 ? "left" : "right"),
        nameTextStyle: { color: a.color || "#5B6775", fontSize: 11 }, axisLabel: { ...AX.axisLabel, color: a.color || "#5B6775", fontSize: 10 },
        splitLine: { show: j === 0, lineStyle: { color: "#EEF1F5" } }, inverse: false };
      return ax;
    });
    const base = (V ? xAxis : yAxis).length;
    valueAxes.forEach((ax: any, j: number) => { (V ? xAxis : yAxis).push(ax); axIdx[axes[j]?.key ?? "_"] = base + j; });
    if (V) yAxis.push(timeAx);
    const timeIndex = V ? yAxis.length - 1 : xAxis.length - 1;
    chs.forEach((c) => {
      const vi = ppgTrack ? axIdx["__ppg"] : (axIdx[c.key] ?? base);
      const pts = t.map((tt: string, k: number) => V ? [s[c.key][k], tt] : [tt, s[c.key][k]]);
      const axisRef = V ? { xAxisIndex: vi, yAxisIndex: timeIndex } : { xAxisIndex: timeIndex, yAxisIndex: vi };
      if (c.band && s[c.band[0]] && s[c.band[1]] && !V) {
        series.push({ type: "line", name: c.name + " lo", data: t.map((tt: string, k: number) => [tt, s[c.band![0]][k]]), ...axisRef, lineStyle: { opacity: 0 }, symbol: "none", stack: "band" + i, silent: true, tooltip: { show: false } });
        series.push({ type: "line", name: c.name + " interval", data: t.map((tt: string, k: number) => [tt, s[c.band![1]][k] != null && s[c.band![0]][k] != null ? s[c.band![1]][k] - s[c.band![0]][k] : null]), ...axisRef, lineStyle: { opacity: 0 }, symbol: "none", stack: "band" + i, areaStyle: { color: c.color + "33" }, silent: true, tooltip: { show: false } });
      }
      series.push({ type: "line", name: `${c.name}`, data: pts, ...axisRef, showSymbol: false, sampling: "lttb", connectNulls: false,
        lineStyle: { color: c.color, width: c.key === "ecd" || c.key === "ecd_pred" ? 2 : 1.4, type: c.dash ? "dashed" : "solid" }, itemStyle: { color: c.color },
        markArea: i === 0 && o.marks?.length ? { silent: true, data: o.marks.filter((m) => m.t1).map((m) => V ? [{ yAxis: m.t0, itemStyle: { color: (LEVEL_COLOR[m.level] || "#888") + "22" } }, { yAxis: m.t1 }] : [{ xAxis: m.t0, itemStyle: { color: (LEVEL_COLOR[m.level] || "#888") + "22" } }, { xAxis: m.t1 }]) } : undefined,
        markLine: o.cutoff ? { symbol: "none", silent: true, lineStyle: { color: "#1B2430", type: "solid", width: 1.5 }, label: { show: i === 0, formatter: "cut-off", color: "#1B2430" }, data: [V ? { yAxis: o.cutoff } : { xAxis: o.cutoff }] } : undefined,
      });
      if (o.after?.[c.key]) {
        const at = o.after.t || [];
        series.push({ type: "line", name: c.name + L(" (setelah cut-off)"), data: at.map((tt: string, k: number) => V ? [o.after![c.key][k], tt] : [tt, o.after![c.key][k]]), ...axisRef, showSymbol: false, lineStyle: { color: "#9AA5B1", width: 1.2 }, itemStyle: { color: "#9AA5B1" } });
      }
    });
    // judul track
    grid[i].title = tr.title;
  });
  const titles = grid.map((g, i) => ({ text: tracks[i].title, textStyle: { color: "#5B6775", fontSize: 11, fontWeight: 500 },
    ...(V ? { left: g.left, top: 0 } : { left: "center", top: `${parseFloat(g.top) - 2.6}%` }) }));
  return {
    backgroundColor: "transparent", animation: false, title: titles, grid: grid.map(({ title, ...g }) => g), xAxis, yAxis, series,
    tooltip: { ...TIP, valueFormatter: (v: any) => (v == null ? "—" : typeof v === "number" ? v.toFixed(2) : v) },
    axisPointer: { link: [{ [V ? "yAxisIndex" : "xAxisIndex"]: "all" }] },
    dataZoom: [{ type: "inside", [V ? "yAxisIndex" : "xAxisIndex"]: (V ? yAxis : xAxis).map((a: any, k: number) => a.type === "time" ? k : -1).filter((k: number) => k >= 0) }],
  };
}
