import React, { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import { PeriodSelector } from "../components/PeriodSelector";

/* ───── Helpers ───── */
const pct = v => `${(v ?? 0).toFixed(1)}%`;
const fmt = v => (v ?? 0).toLocaleString("es-EC");

const SEMAFORO_COLORS = {
  rojo:     { bg: "bg-red-50",    border: "border-red-300",    dot: "bg-red-500",    text: "text-red-700",    label: "Crítico" },
  amarillo: { bg: "bg-yellow-50", border: "border-yellow-300", dot: "bg-yellow-500", text: "text-yellow-700", label: "En riesgo" },
  verde:    { bg: "bg-green-50",  border: "border-green-300",  dot: "bg-green-500",  text: "text-green-700",  label: "Estable" },
};

/* ═══════ KPI Card ═══════ */
function KpiCard({ title, value, subtitle, icon, color = "blue" }) {
  const palette = {
    blue:   { bg: "bg-blue-50",   iconBg: "bg-blue-100",   iconText: "text-blue-600",   valueText: "text-blue-700" },
    green:  { bg: "bg-green-50",  iconBg: "bg-green-100",  iconText: "text-green-600",  valueText: "text-green-700" },
    amber:  { bg: "bg-amber-50",  iconBg: "bg-amber-100",  iconText: "text-amber-600",  valueText: "text-amber-700" },
    purple: { bg: "bg-purple-50", iconBg: "bg-purple-100", iconText: "text-purple-600", valueText: "text-purple-700" },
    red:    { bg: "bg-red-50",    iconBg: "bg-red-100",    iconText: "text-red-600",    valueText: "text-red-700" },
    cyan:   { bg: "bg-cyan-50",   iconBg: "bg-cyan-100",   iconText: "text-cyan-600",   valueText: "text-cyan-700" },
  };
  const p = palette[color] || palette.blue;
  return (
    <div className={`${p.bg} rounded-xl p-5 border border-gray-100 shadow-sm`}>
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{title}</span>
        <span className={`${p.iconBg} ${p.iconText} w-9 h-9 rounded-lg flex items-center justify-center text-lg`}>{icon}</span>
      </div>
      <div className={`text-3xl font-bold ${p.valueText}`}>{value}</div>
      {subtitle && <div className="text-xs text-gray-500 mt-1">{subtitle}</div>}
    </div>
  );
}

/* ═══════ Risk donut (SVG) ═══════ */
function RiskDonut({ distribucion, total }) {
  const alto  = distribucion["Alto"] || 0;
  const medio = distribucion["Medio"] || 0;
  const bajo  = distribucion["Bajo"] || 0;
  const sin   = total - alto - medio - bajo;

  const items = [
    { label: "Alto",  count: alto,  color: "#ef4444" },
    { label: "Medio", count: medio, color: "#f59e0b" },
    { label: "Bajo",  count: bajo,  color: "#22c55e" },
  ];
  if (sin > 0) items.push({ label: "Sin clasificar", count: sin, color: "#94a3b8" });

  const radius = 52, stroke = 14, circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Distribución de Riesgo</h3>
      <div className="flex items-center gap-6">
        <svg width="140" height="140" viewBox="0 0 140 140" className="flex-shrink-0">
          {items.map(it => {
            const pctVal = total ? it.count / total : 0;
            const dash = pctVal * circumference;
            const el = (
              <circle key={it.label} cx="70" cy="70" r={radius} fill="none"
                stroke={it.color} strokeWidth={stroke}
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offset} strokeLinecap="butt"
                transform="rotate(-90 70 70)" />
            );
            offset += dash;
            return el;
          })}
          <text x="70" y="66" textAnchor="middle" className="text-2xl font-bold" fill="#1e293b">{fmt(total)}</text>
          <text x="70" y="82" textAnchor="middle" className="text-[10px]" fill="#64748b">estudiantes</text>
        </svg>
        <div className="space-y-2 flex-1">
          {items.map(it => (
            <div key={it.label} className="flex items-center gap-2 text-sm">
              <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: it.color }} />
              <span className="text-gray-600 flex-1">{it.label}</span>
              <span className="font-semibold text-gray-800">{it.count}</span>
              <span className="text-gray-400 text-xs w-12 text-right">{total ? pct(it.count / total * 100) : "0%"}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══════ Semáforo por carrera ═══════ */
function SemaforoCarreras({ carreras }) {
  if (!carreras || carreras.length === 0) return null;
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Semáforo por Carrera</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {carreras.map(c => {
          const s = SEMAFORO_COLORS[c.semaforo] || SEMAFORO_COLORS.verde;
          return (
            <div key={c.carrera} className={`${s.bg} ${s.border} border rounded-lg p-4`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-3 h-3 rounded-full ${s.dot}`} />
                <span className={`text-sm font-semibold ${s.text}`}>{s.label}</span>
              </div>
              <div className="text-sm font-medium text-gray-800 mb-2 truncate" title={c.carrera}>{c.carrera}</div>
              <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
                <div><span className="font-medium text-red-600">{c.alto}</span> alto</div>
                <div><span className="font-medium text-yellow-600">{c.medio}</span> medio</div>
                <div><span className="font-medium text-green-600">{c.bajo}</span> bajo</div>
              </div>
              <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
                <span>Riesgo alto: {pct(c.tasa_riesgo_alto)}</span>
                <span>Compromiso: {(c.compromiso_promedio * 100).toFixed(0)}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════ Tendencia multi-período (simple SVG chart) ═══════ */
function TendenciaChart({ data }) {
  if (!data || data.length < 2) return null;

  const W = 600, H = 200, PAD = { top: 20, right: 20, bottom: 40, left: 50 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const maxVal = Math.max(...data.map(d => d.tasa_riesgo_alto), 10);
  const x = (i) => PAD.left + (i / (data.length - 1)) * innerW;
  const y = (v) => PAD.top + innerH - (v / maxVal) * innerH;

  // Line path for tasa_riesgo_alto
  const linePath = data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.tasa_riesgo_alto)}`).join(" ");
  // Line path for compromiso (scaled to same axis as %)
  const compPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.compromiso_promedio * 100)}`).join(" ");

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-1">Tendencia por Período</h3>
      <div className="flex gap-4 text-xs text-gray-500 mb-3">
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-red-500 inline-block rounded" /> % Riesgo alto</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-500 inline-block rounded" /> Compromiso %</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 220 }}>
        {/* Grid lines */}
        {[0, 25, 50, 75, 100].filter(v => v <= maxVal + 10).map(v => (
          <g key={v}>
            <line x1={PAD.left} y1={y(v)} x2={W - PAD.right} y2={y(v)} stroke="#e2e8f0" strokeWidth={0.5} />
            <text x={PAD.left - 6} y={y(v) + 4} textAnchor="end" className="text-[10px]" fill="#94a3b8">{v}%</text>
          </g>
        ))}
        {/* X labels */}
        {data.map((d, i) => (
          <text key={d.periodo} x={x(i)} y={H - 8} textAnchor="middle" className="text-[10px]" fill="#64748b">{d.periodo}</text>
        ))}
        {/* Risk line */}
        <path d={linePath} fill="none" stroke="#ef4444" strokeWidth={2.5} strokeLinejoin="round" />
        {data.map((d, i) => <circle key={i} cx={x(i)} cy={y(d.tasa_riesgo_alto)} r={4} fill="#ef4444" />)}
        {/* Compromiso line */}
        <path d={compPath} fill="none" stroke="#3b82f6" strokeWidth={2.5} strokeLinejoin="round" strokeDasharray="6 3" />
        {data.map((d, i) => <circle key={`c${i}`} cx={x(i)} cy={y(d.compromiso_promedio * 100)} r={4} fill="#3b82f6" />)}
      </svg>
    </div>
  );
}

/* ═══════════════════════════════════
   PÁGINA PRINCIPAL: Dashboard Ejecutivo
   ═══════════════════════════════════ */
export default function Ejecutivo() {
  const [periodo, setPeriodo] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    if (!periodo) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.getExecutiveDashboard(periodo);
      setData(res);
    } catch (err) {
      setError("No se pudo cargar el dashboard ejecutivo.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [periodo]);

  useEffect(() => { loadData(); }, [loadData]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Dashboard Ejecutivo</h1>
          <p className="text-sm text-gray-500 mt-0.5">Visión institucional de retención y riesgo académico</p>
        </div>
        <PeriodSelector value={periodo} onChange={setPeriodo} />
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-20 text-gray-400">
          <svg className="animate-spin h-6 w-6 mr-2" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          Cargando indicadores...
        </div>
      )}

      {!loading && data && (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            <KpiCard title="Retención estimada" value={pct(data.kpis.retencion_estimada)} subtitle="% no riesgo alto" icon="🛡️" color="green" />
            <KpiCard title="Cobertura" value={pct(data.kpis.cobertura_intervencion)} subtitle="riesgo alto intervenido" icon="🎯" color="blue" />
            <KpiCard title="Efectividad" value={pct(data.kpis.efectividad_intervenciones)} subtitle="intervenciones resueltas" icon="✅" color="purple" />
            <KpiCard title="Compromiso" value={`${(data.kpis.compromiso_promedio * 100).toFixed(0)}%`} subtitle="promedio institucional" icon="📈" color="cyan" />
            <KpiCard title="Riesgo alto" value={fmt(data.kpis.estudiantes_riesgo_alto)} subtitle="estudiantes" icon="⚠️" color="red" />
            <KpiCard title="Intervenciones" value={fmt(data.kpis.intervenciones_activas)} subtitle="activas en curso" icon="🤝" color="amber" />
          </div>

          {/* Middle row: Donut + Tendencia */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <RiskDonut distribucion={data.distribucion_riesgo} total={data.total_estudiantes} />
            <TendenciaChart data={data.tendencia_periodos} />
          </div>

          {/* Semáforo por carrera */}
          <SemaforoCarreras carreras={data.semaforo_carreras} />

          {/* Empty state */}
          {data.total_estudiantes === 0 && (
            <div className="text-center py-16 text-gray-400">
              <div className="text-4xl mb-3">📭</div>
              <p className="text-lg font-medium">Sin datos para este período</p>
              <p className="text-sm">Seleccione un período con datos cargados.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
