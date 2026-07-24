var __defProp = Object.defineProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};

// src/AttributionBadge.tsx
import { useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
var CYAN = "#0E9AB8";
var CYAN_DARK = "#0B7C93";
var CYAN_LIGHT = "#3FC0DA";
var THEMES = {
  light: { bg: "rgba(255,255,255,.92)", fg: "#0F2444", muted: "#6b7280", border: "rgba(15,36,68,.08)" },
  dark: { bg: "rgba(16,32,58,.72)", fg: "#eaf2fb", muted: "#9db4d6", border: "rgba(168,220,232,.22)" }
};
function AttributionBadge({
  theme = "light",
  href = "https://analytics.yachaydeep.com",
  mark = "\u{1F4CA}",
  accent = `var(--yd-accent, ${CYAN})`
}) {
  const [hover, setHover] = useState(false);
  const t = THEMES[theme];
  const badge = {
    position: "absolute",
    right: 12,
    bottom: 12,
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 12px 6px 10px",
    borderRadius: 999,
    background: t.bg,
    WebkitBackdropFilter: "blur(6px)",
    backdropFilter: "blur(6px)",
    border: `1px solid ${t.border}`,
    boxShadow: hover ? "0 6px 16px -4px rgba(15,36,68,.35)" : "0 2px 10px -2px rgba(15,36,68,.25)",
    transform: hover ? "translateY(-1px)" : "none",
    transition: "transform .15s ease, box-shadow .15s ease",
    fontFamily: '"Instrument Sans", system-ui, -apple-system, sans-serif',
    fontSize: 12,
    lineHeight: 1,
    color: t.fg,
    textDecoration: "none",
    cursor: "pointer",
    zIndex: 5
  };
  const stripe = {
    width: 4,
    height: 16,
    borderRadius: 2,
    // Franja sólida en el color del host (o cian por defecto). Sólido = compatible
    // con cualquier color, incluyendo `currentColor` o una variable CSS del host.
    background: accent,
    flex: "0 0 auto"
  };
  const wordmark = { fontStyle: "italic", fontWeight: 600, letterSpacing: ".01em" };
  const sub = { fontStyle: "italic", fontWeight: 500, color: t.muted };
  return /* @__PURE__ */ jsxs(
    "a",
    {
      href,
      target: "_blank",
      rel: "noopener noreferrer",
      style: badge,
      onMouseEnter: () => setHover(true),
      onMouseLeave: () => setHover(false),
      "aria-label": "Hecho con Yachay Deep Analytics",
      "data-yd-attribution": true,
      children: [
        /* @__PURE__ */ jsx("span", { style: stripe, "aria-hidden": "true" }),
        mark && /* @__PURE__ */ jsx("span", { style: { fontSize: 14, lineHeight: 1 }, "aria-hidden": "true", children: mark }),
        /* @__PURE__ */ jsxs("span", { style: wordmark, children: [
          "Yachay Deep ",
          /* @__PURE__ */ jsx("span", { style: sub, children: "Analytics" })
        ] })
      ]
    }
  );
}
var ANALYTICS_COLOR = { base: CYAN, dark: CYAN_DARK, light: CYAN_LIGHT };

// src/Panel.tsx
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";

// src/useMetric.ts
import { useQuery } from "@tanstack/react-query";

// src/client.ts
var DEFAULT_BASE = import.meta.env?.VITE_ANALYTICS_API ?? "http://127.0.0.1:8000";
var _cfg = { apiBase: DEFAULT_BASE };
function configureAnalytics(cfg) {
  _cfg = { ..._cfg, ...cfg };
}
function analyticsBase() {
  return (_cfg.apiBase ?? DEFAULT_BASE).replace(/\/+$/, "");
}
function analyticsHeaders() {
  const h = { "Content-Type": "application/json", ..._cfg.headers ?? {} };
  if (_cfg.apiKey) h["X-API-Key"] = _cfg.apiKey;
  return h;
}
function analyticsCredentials() {
  return _cfg.credentials ?? (_cfg.apiKey ? "omit" : "include");
}

// src/filterStore.ts
import { create } from "zustand";
function readURL() {
  if (typeof window === "undefined") return {};
  const p = new URLSearchParams(window.location.search);
  const out = {};
  p.forEach((v, k) => {
    if (k.startsWith("f.")) out[k.slice(2)] = { field: k.slice(2), op: "eq", value: v };
  });
  return out;
}
function writeURL(filters) {
  if (typeof window === "undefined") return;
  const p = new URLSearchParams(window.location.search);
  [...p.keys()].forEach((k) => k.startsWith("f.") && p.delete(k));
  Object.values(filters).forEach((f) => p.set(`f.${f.field}`, String(f.value)));
  window.history.replaceState(null, "", `${window.location.pathname}?${p.toString()}`);
}
var useFilters = create((set, get) => ({
  filters: readURL(),
  set: (field, value, op = "eq") => set((s) => {
    const filters = { ...s.filters, [field]: { field, op, value } };
    writeURL(filters);
    return { filters };
  }),
  toggle: (field, value) => set((s) => {
    const cur = s.filters[field];
    const filters = { ...s.filters };
    if (cur && cur.value === value) delete filters[field];
    else filters[field] = { field, op: "eq", value };
    writeURL(filters);
    return { filters };
  }),
  clear: (field) => set((s) => {
    const filters = field ? { ...s.filters } : {};
    if (field) delete filters[field];
    writeURL(filters);
    return { filters };
  }),
  asArray: () => Object.values(get().filters)
}));

// src/useMetric.ts
async function fetchPanel(spec, filters) {
  const res = await fetch(`${analyticsBase()}/analytics/query`, {
    method: "POST",
    headers: analyticsHeaders(),
    // Content-Type + X-API-Key (si se configuró)
    credentials: analyticsCredentials(),
    // cookie de sesión, o "omit" con API key
    body: JSON.stringify({
      metric: spec.metric,
      dimensions: spec.dimensions ?? [],
      grain: spec.grain ?? null,
      chart_hint: spec.chartHint ?? null,
      filters
      // params (p. ej. umbral) pueden venir de un contexto de tablero; omitido aquí
    })
  });
  if (!res.ok) throw new Error(`analytics ${res.status}: ${await res.text()}`);
  return res.json();
}
function useMetric(spec) {
  const filters = useFilters((s) => s.filters);
  const arr = Object.values(filters);
  return useQuery({
    queryKey: ["panel", spec.id, spec.metric, spec.dimensions, arr],
    queryFn: () => fetchPanel(spec, arr),
    staleTime: 3e4
  });
}

// src/format.ts
var format_exports = {};
__export(format_exports, {
  impact: () => impact,
  money: () => money,
  number: () => number,
  percent: () => percent
});
var LOCALE = "es-EC";
function money(value) {
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value);
}
function number(value, decimals = 0) {
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(value);
}
function percent(value, decimals = 1) {
  return `${number(value, decimals)} %`;
}
function impact(value) {
  return `${number(value)}+`;
}

// src/palette.ts
var palette_exports = {};
__export(palette_exports, {
  ALL_PAIRS_CAP: () => ALL_PAIRS_CAP,
  CATEGORICAL: () => CATEGORICAL,
  CHROME: () => CHROME,
  DIVERGING: () => DIVERGING,
  PRODUCT_PRIMARY: () => PRODUCT_PRIMARY,
  SEQUENTIAL: () => SEQUENTIAL,
  STATUS: () => STATUS,
  categorical: () => categorical,
  seriesColor: () => seriesColor
});
var CATEGORICAL = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#e34948"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#e66767"]
};
var ALL_PAIRS_CAP = 3;
var SEQUENTIAL = [
  "#cde2fb",
  "#9ec5f4",
  "#6da7ec",
  "#3987e5",
  "#256abf",
  "#184f95",
  "#0d366b"
];
var DIVERGING = { low: "#2a78d6", mid: { light: "#f0efec", dark: "#383835" }, high: "#e34948" };
var STATUS = { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" };
var CHROME = {
  light: { surface: "#fcfcfb", page: "#f9f9f7", ink: "#0b0b0b", ink2: "#52514e", muted: "#898781", grid: "#e1e0d9", axis: "#c3c2b7" },
  dark: { surface: "#16181d", page: "#0d0d0d", ink: "#ffffff", ink2: "#c3c2b7", muted: "#898781", grid: "#2c2c2a", axis: "#383835" }
};
var PRODUCT_PRIMARY = { light: "#1B3A6B", dark: "#3987e5", accent: "#E8A838" };
function categorical(mode2 = "light") {
  return CATEGORICAL[mode2];
}
function seriesColor(i, mode2 = "light") {
  const p = CATEGORICAL[mode2];
  return p[i % p.length];
}

// src/chartOptions.ts
var css = (v, fallback) => (typeof getComputedStyle !== "undefined" ? getComputedStyle(document.documentElement).getPropertyValue(v).trim() : "") || fallback;
var PRIMARY = () => css("--brand-primary", "#1B3A6B");
var INK = () => css("--ink", "#11182a");
var MUTED = () => css("--muted", "#6B7280");
var mode = () => css("--yd-mode", "light") === "dark" ? "dark" : "light";
var CAT = () => categorical(mode());
function fmt(value, formato) {
  if (formato === "money") return money(value);
  if (formato === "percent") return percent(value);
  return Number.isInteger(value) ? number(value) : number(value, 2);
}
function toEChartsOption(chart, result) {
  const { rows, formato } = result;
  const axisFmt = (v) => fmt(v, formato);
  if (chart.type === "line" || chart.type === "area") {
    const x = chart.encoding.x.field;
    return {
      grid: { left: 48, right: 16, top: 24, bottom: 32 },
      tooltip: { trigger: "axis", valueFormatter: axisFmt },
      xAxis: { type: "category", data: rows.map((r) => r[x]), axisLine: { lineStyle: { color: MUTED() } } },
      yAxis: { type: "value", axisLabel: { formatter: axisFmt } },
      series: [{
        type: "line",
        smooth: true,
        areaStyle: chart.type === "area" ? { opacity: 0.15 } : void 0,
        data: rows.map((r) => r.valor),
        itemStyle: { color: PRIMARY() },
        lineStyle: { color: PRIMARY(), width: 2.5 }
      }]
    };
  }
  if (chart.type === "bar" || chart.type === "bar_h") {
    const cat = chart.encoding.x.field;
    const horizontal = chart.type === "bar_h";
    const catAxis = { type: "category", data: rows.map((r) => r[cat]) };
    const valAxis = { type: "value", axisLabel: { formatter: axisFmt } };
    return {
      grid: { left: horizontal ? 96 : 48, right: 16, top: 24, bottom: 32 },
      tooltip: { trigger: "item", valueFormatter: axisFmt },
      xAxis: horizontal ? valAxis : catAxis,
      yAxis: horizontal ? { ...catAxis, inverse: true } : valAxis,
      series: [{
        type: "bar",
        data: rows.map((r) => r.valor),
        itemStyle: { color: PRIMARY(), borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] }
      }]
    };
  }
  if (chart.type === "heatmap") {
    const [xf, yf] = [chart.encoding.x.field, chart.encoding.y.field];
    const xs = [...new Set(rows.map((r) => r[xf]))];
    const ys = [...new Set(rows.map((r) => r[yf]))];
    const data = rows.map((r) => [xs.indexOf(r[xf]), ys.indexOf(r[yf]), r.valor]);
    const max = Math.max(...rows.map((r) => Number(r.valor)));
    return {
      grid: { left: 96, right: 16, top: 24, bottom: 48 },
      tooltip: { position: "top", valueFormatter: axisFmt },
      xAxis: { type: "category", data: xs },
      yAxis: { type: "category", data: ys },
      visualMap: {
        min: 0,
        max,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        inRange: { color: ["#D8EFF4", PRIMARY()] }
      },
      // hielo → primario (nunca violeta)
      series: [{ type: "heatmap", data, label: { show: true, formatter: (p) => axisFmt(p.value[2]) } }]
    };
  }
  if (chart.type === "pie") {
    const cat = chart.encoding.x?.field ?? result.columns[0];
    return {
      tooltip: { trigger: "item", formatter: (p) => `${p.name}: ${axisFmt(p.value)} (${p.percent}%)` },
      legend: { bottom: 0 },
      series: [{
        type: "pie",
        radius: ["48%", "72%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: css("--surface", "#fff"), borderWidth: 2 },
        label: { color: INK() },
        data: rows.map((r, i) => ({ name: r[cat], value: r.valor, itemStyle: { color: CAT()[i % CAT().length] } }))
      }]
    };
  }
  if (chart.type === "stacked_bar") {
    const cat = chart.encoding.x.field;
    return {
      grid: { left: 44, right: 16, top: 28, bottom: 40 },
      legend: { top: 0 },
      tooltip: { trigger: "axis", valueFormatter: axisFmt },
      xAxis: { type: "category", data: rows.map((r) => r[cat]) },
      yAxis: { type: "value", axisLabel: { formatter: axisFmt } },
      series: [{
        type: "bar",
        stack: "s",
        data: rows.map((r) => r.valor),
        itemStyle: { color: CAT()[0], borderColor: css("--surface", "#fff"), borderWidth: 1 }
      }]
    };
  }
  if (chart.type === "treemap") {
    const cat = chart.encoding.x?.field ?? result.columns[0];
    return {
      tooltip: { formatter: (p) => `${p.name}: ${axisFmt(p.value)}` },
      series: [{
        type: "treemap",
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: { color: "#fff" },
        itemStyle: { gapWidth: 2, borderColor: css("--surface", "#fff") },
        data: rows.map((r, i) => ({
          name: r[cat],
          value: r.valor,
          itemStyle: { color: SEQUENTIAL[Math.max(0, SEQUENTIAL.length - 1 - i)] }
        }))
      }]
    };
  }
  if (chart.type === "scatter") {
    const xf = chart.encoding.x.field;
    return {
      grid: { left: 44, right: 16, top: 16, bottom: 30 },
      tooltip: { trigger: "item", formatter: (p) => `${xf} ${p.value[0]}, ${axisFmt(p.value[1])}` },
      xAxis: { type: "value", name: xf },
      yAxis: { type: "value", axisLabel: { formatter: axisFmt } },
      series: [{
        type: "scatter",
        symbolSize: 9,
        itemStyle: { color: CAT()[0], opacity: 0.75 },
        // series ≤ 3 (tope all-pairs) aguas arriba
        data: rows.map((r) => [r[xf], r.valor])
      }]
    };
  }
  if (chart.type === "histogram") {
    const cat = chart.encoding.x.field;
    return {
      grid: { left: 40, right: 12, top: 12, bottom: 34 },
      tooltip: { trigger: "item", valueFormatter: axisFmt },
      xAxis: { type: "category", data: rows.map((r) => r[cat]) },
      yAxis: { type: "value", axisLabel: { formatter: axisFmt } },
      series: [{
        type: "bar",
        barWidth: "96%",
        data: rows.map((r) => r.valor),
        itemStyle: { color: CAT()[0], borderColor: css("--surface", "#fff"), borderWidth: 1 }
      }]
    };
  }
  if (chart.type === "funnel") {
    const cat = chart.encoding.x?.field ?? result.columns[0];
    return {
      tooltip: { trigger: "item", formatter: (p) => `${p.name}: ${axisFmt(p.value)}` },
      series: [{
        type: "funnel",
        left: 8,
        right: 8,
        minSize: "24%",
        label: { position: "inside", color: "#fff" },
        labelLine: { show: false },
        itemStyle: { borderColor: css("--surface", "#fff"), borderWidth: 2 },
        data: rows.map((r, i) => ({
          name: r[cat],
          value: r.valor,
          itemStyle: { color: SEQUENTIAL[Math.min(SEQUENTIAL.length - 1, i + 2)] }
        }))
      }]
    };
  }
  return { _table: true, columns: result.columns, rows };
}

// src/Panel.tsx
import { jsx as jsx2, jsxs as jsxs2 } from "react/jsx-runtime";
function Panel({ spec }) {
  const { data, isLoading, error } = useMetric(spec);
  const toggle = useFilters((s) => s.toggle);
  const option = useMemo(
    () => data ? toEChartsOption(data.chart, data.result) : null,
    [data]
  );
  if (isLoading) return /* @__PURE__ */ jsx2("div", { className: "yd-panel yd-panel--loading", children: "Cargando\u2026" });
  if (error) return /* @__PURE__ */ jsxs2("div", { className: "yd-panel yd-panel--error", children: [
    "Error: ",
    String(error)
  ] });
  if (!data) return null;
  const { chart, result } = data;
  if (chart.type === "kpi") {
    const valor = Number(result.rows[0]?.valor ?? 0);
    return /* @__PURE__ */ jsxs2("div", { className: "yd-panel yd-kpi", children: [
      /* @__PURE__ */ jsx2("div", { className: "yd-kpi__value", children: fmt(valor, result.formato) }),
      /* @__PURE__ */ jsx2("div", { className: "yd-kpi__label", children: spec.titulo ?? spec.metric })
    ] });
  }
  const onEvents = chart.interactions.emits_filter ? {
    click: (p) => {
      const field = chart.interactions.emits_filter;
      const value = p.name;
      toggle(field, value);
    }
  } : {};
  return /* @__PURE__ */ jsxs2("div", { className: "yd-panel", children: [
    /* @__PURE__ */ jsxs2("div", { className: "yd-panel__head", children: [
      /* @__PURE__ */ jsx2("h3", { children: spec.titulo ?? spec.metric }),
      (spec.nota || chart.note) && /* @__PURE__ */ jsx2("p", { className: "yd-panel__note", children: spec.nota ?? chart.note })
    ] }),
    /* @__PURE__ */ jsx2(ReactECharts, { option, onEvents, style: { height: 280 }, notMerge: true })
  ] });
}

// src/Dashboard.tsx
import { Fragment, jsx as jsx3, jsxs as jsxs3 } from "react/jsx-runtime";
function Dashboard({
  spec,
  attribution = true,
  attributionTheme = "light",
  attributionAccent
}) {
  const filters = useFilters((s) => s.filters);
  const clear = useFilters((s) => s.clear);
  const activos = Object.values(filters);
  return /* @__PURE__ */ jsxs3("section", { className: "yd-dashboard", style: { position: "relative" }, children: [
    /* @__PURE__ */ jsxs3("header", { className: "yd-dashboard__head", children: [
      /* @__PURE__ */ jsx3("h2", { children: spec.titulo }),
      /* @__PURE__ */ jsx3("div", { className: "yd-dashboard__filtros", children: activos.length > 0 ? /* @__PURE__ */ jsxs3(Fragment, { children: [
        activos.map((f) => /* @__PURE__ */ jsxs3("button", { className: "yd-chip", onClick: () => clear(f.field), children: [
          f.field,
          ": ",
          String(f.value),
          " \u2715"
        ] }, f.field)),
        /* @__PURE__ */ jsx3("button", { className: "yd-chip yd-chip--reset", onClick: () => clear(), children: "Limpiar todo" })
      ] }) : /* @__PURE__ */ jsx3("span", { className: "yd-dashboard__hint", children: "Haz clic en una barra para filtrar todo el tablero" }) })
    ] }),
    /* @__PURE__ */ jsx3("div", { className: "yd-grid", children: spec.paneles.map((p) => /* @__PURE__ */ jsx3("div", { className: `yd-cell yd-cell--${p.size ?? "md"}`, children: /* @__PURE__ */ jsx3(Panel, { spec: p }) }, p.id)) }),
    attribution && /* @__PURE__ */ jsx3(AttributionBadge, { theme: attributionTheme, accent: attributionAccent })
  ] });
}

// src/NetworkView.tsx
import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { jsx as jsx4 } from "react/jsx-runtime";
var VIRIDIS = ["#440154", "#46327e", "#365c8d", "#277f8e", "#1fa187", "#4ac16d", "#a0da39", "#fde725"];
var hex2rgb = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
var lerp = (a, b, t) => Math.round(a + (b - a) * t);
function viridis(t) {
  t = Math.max(0, Math.min(1, t));
  const s = t * (VIRIDIS.length - 1), i = Math.floor(s), f = s - i;
  if (i >= VIRIDIS.length - 1) return VIRIDIS[VIRIDIS.length - 1];
  const a = hex2rgb(VIRIDIS[i]), b = hex2rgb(VIRIDIS[i + 1]);
  return `rgb(${lerp(a[0], b[0], f)},${lerp(a[1], b[1], f)},${lerp(a[2], b[2], f)})`;
}
function lighten(hex, amt) {
  const [r, g, b] = hex2rgb(hex);
  const f = (x) => Math.round(x + (255 - x) * amt);
  return `rgb(${f(r)},${f(g)},${f(b)})`;
}
function sphere(color) {
  return new echarts.graphic.RadialGradient(0.32, 0.3, 0.85, [
    { offset: 0, color: color.startsWith("#") ? lighten(color, 0.35) : color },
    { offset: 1, color }
  ]);
}
var CLUSTER_PALETTE = ["#E4A11B", "#2B6FD6", "#17A398", "#E4572E", "#6B7A8F", "#4CA64C"];
function NetworkView({
  data,
  colorBy = "cluster",
  clusterOf,
  overlayValue,
  height = 600,
  onSelect
}) {
  const ref = useRef(null);
  const chartRef = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = chartRef.current ?? echarts.init(ref.current);
    chartRef.current = chart;
    const groups = Array.from(new Set(data.nodes.map((n) => n.group ?? "\u2014")));
    const defClusterColor = (n) => CLUSTER_PALETTE[groups.indexOf(n.group ?? "\u2014") % CLUSTER_PALETTE.length];
    const clusterFor = (n) => clusterOf ? clusterOf(n) : { name: String(n.group ?? "\u2014"), color: defClusterColor(n) };
    const ovVal = (n) => overlayValue ? overlayValue(n) : n.value ?? 1;
    const vals = data.nodes.map(ovVal);
    const vmin = Math.min(...vals), vmax = Math.max(...vals);
    const solidOf = (n) => colorBy === "overlay" ? viridis((ovVal(n) - vmin) / (vmax - vmin || 1)) : clusterFor(n).color;
    const nodes = data.nodes.map((n) => {
      const solid = solidOf(n);
      return {
        id: n.id,
        name: n.id,
        value: ovVal(n),
        symbolSize: 12 + (n.value ?? 1) * 5,
        itemStyle: { color: colorBy === "overlay" ? solid : sphere(solid), borderWidth: 0, shadowBlur: 8, shadowColor: "rgba(30,40,60,.18)" },
        label: {
          show: true,
          position: "right",
          distance: 4,
          color: "#2a2f3a",
          fontSize: 10,
          formatter: n.label.length > 18 ? n.id : n.label
        },
        _solid: solid
      };
    });
    const cmap = {};
    nodes.forEach((d) => cmap[d.id] = d._solid);
    const links = data.edges.map((e) => {
      const c = cmap[e.source] ?? "#94a3b8";
      const rgb = /^rgb/.test(c) ? c.match(/\d+/g).map(Number) : hex2rgb(c);
      return {
        source: e.source,
        target: e.target,
        lineStyle: { color: `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.42)`, width: 1.1, curveness: 0.28 }
      };
    });
    chart.setOption({
      tooltip: { formatter: (p) => p.dataType === "node" ? `<b>${data.nodes.find((n) => n.id === p.name)?.label ?? p.name}</b>` : "" },
      visualMap: colorBy === "overlay" ? {
        type: "continuous",
        min: vmin,
        max: vmax,
        calculable: true,
        orient: "horizontal",
        right: 20,
        bottom: 10,
        inRange: { color: VIRIDIS },
        dimension: 0,
        seriesIndex: 0
      } : void 0,
      series: [{
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        force: { repulsion: 900, edgeLength: [90, 210], gravity: 0.035, friction: 0.12 },
        edgeSymbol: ["none", "none"],
        emphasis: { focus: "adjacency", label: { fontWeight: "bold" }, lineStyle: { width: 2.4, opacity: 0.8 } },
        data: nodes,
        links
      }]
    }, true);
    const onClick = (p) => {
      if (p?.dataType === "node") onSelect?.(p.name);
    };
    chart.off("click");
    chart.on("click", onClick);
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [data, colorBy, clusterOf, overlayValue, onSelect]);
  useEffect(() => () => {
    chartRef.current?.dispose();
    chartRef.current = null;
  }, []);
  return /* @__PURE__ */ jsx4("div", { ref, style: { width: "100%", height } });
}

// src/ChoroplethView.tsx
import { useEffect as useEffect2, useRef as useRef2 } from "react";
import * as echarts2 from "echarts";
import { jsx as jsx5 } from "react/jsx-runtime";
function ChoroplethView({ geojson, mapName = "ecuador", data, height = 460, onSelect }) {
  const ref = useRef2(null);
  const chartRef = useRef2(null);
  useEffect2(() => {
    if (!ref.current) return;
    echarts2.registerMap(mapName, geojson);
    const chart = chartRef.current ?? echarts2.init(ref.current);
    chartRef.current = chart;
    const max = Math.max(1, ...data.map((d) => d.value));
    chart.setOption({
      tooltip: { trigger: "item", formatter: (p) => `${p.name}: ${p.value ?? "\u2014"}` },
      visualMap: {
        min: 0,
        max,
        left: 8,
        bottom: 8,
        calculable: true,
        inRange: { color: [SEQUENTIAL[0], SEQUENTIAL[3], SEQUENTIAL[6]] }
      },
      series: [{
        type: "map",
        map: mapName,
        roam: true,
        data,
        emphasis: { label: { show: true }, itemStyle: { areaColor: "#E8A838" } },
        // acento dorado al hover
        itemStyle: { borderColor: "#fff", borderWidth: 0.5 },
        label: { show: false }
      }]
    }, true);
    const onClick = (p) => onSelect?.(p?.name ?? null);
    chart.off("click");
    chart.on("click", onClick);
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [geojson, mapName, data, onSelect]);
  useEffect2(() => () => {
    chartRef.current?.dispose();
    chartRef.current = null;
  }, []);
  return /* @__PURE__ */ jsx5("div", { ref, style: { width: "100%", height } });
}

// src/export.ts
function toCSV(result) {
  const cols = result.columns;
  const head = cols.join(",");
  const body = result.rows.map(
    (r) => cols.map((c) => {
      const v = r[c];
      const s = v == null ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(",")
  );
  return [head, ...body].join("\n");
}
function download(name, mime, data) {
  const url = URL.createObjectURL(typeof data === "string" ? new Blob([data], { type: mime }) : data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1e3);
}
function exportCSV(result, filename = "datos.csv") {
  download(filename, "text/csv;charset=utf-8", "\uFEFF" + toCSV(result));
}
function exportPNG(chart, filename = "grafico.png") {
  const url = chart.getDataURL({ pixelRatio: 2, backgroundColor: "#fff" });
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
}
export {
  ANALYTICS_COLOR,
  AttributionBadge,
  ChoroplethView,
  Dashboard,
  NetworkView,
  Panel,
  analyticsBase,
  analyticsCredentials,
  analyticsHeaders,
  configureAnalytics,
  exportCSV,
  exportPNG,
  fmt,
  format_exports as format,
  palette_exports as palette,
  toCSV,
  toEChartsOption,
  useFilters,
  useMetric
};
