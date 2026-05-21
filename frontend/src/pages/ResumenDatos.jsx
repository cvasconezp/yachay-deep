import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { useStudentListModal } from "../components/StudentListModal";
import { PeriodSelector } from "../components/PeriodSelector";
import { TrendCharts } from "../components/TrendCharts";
import {
  ResponsiveContainer,
  PieChart, Pie, Cell,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  LabelList,
  Treemap,
} from "recharts";

/* ── Paleta Power BI global ────────────── */
const PBI = {
  navy: "#1B2A4A", blue: "#2B5EA7", teal: "#0F9B8D",
  gold: "#F2C94C", coral: "#EB5757", purple: "#7B61FF",
  slate: "#64748B", bg: "#F8FAFC", card: "#FFFFFF", border: "#E2E8F0",
  green: "#0F9B8D", orange: "#F97316",
  // Treemap & chart palette (varied, high contrast)
  palette: ["#2B5EA7","#0F9B8D","#7B61FF","#EB5757","#F2C94C","#14B8A6","#6366F1","#F97316","#EC4899","#06B6D4","#84CC16","#8B5CF6","#0EA5E9","#F43F5E","#10B981","#A855F7","#EAB308","#3B82F6"],
};
const RISK_COLORS = { Alto: PBI.coral, Medio: PBI.gold, Bajo: PBI.teal };
const CHART_COLORS = PBI.palette;
const GENDER_COLORS = { Masculino: PBI.blue, Femenino: "#EC4899", "Sin dato": PBI.slate };

/* ── Tooltip estilo PBI (reutilizable) ── */
const pbiTooltipStyle = { fontSize: 12, borderRadius: 8, border: "none", boxShadow: "0 4px 12px rgba(0,0,0,.1)", background: "#fff" };

/* ── KPI Card (Power BI style) ─────────── */
/* KPI tooltip descriptions */
const KPI_TOOLTIPS = {
  "Estudiantes": "Total de estudiantes matriculados en el período",
  "Docentes": "Total de docentes asignados a materias",
  "Carreras": "Programas académicos activos",
  "Matrículas": "Registros de estudiante × materia",
  "Prom. Calificaciones": "Promedio general de notas sobre 100",
  "Asignaturas": "Materias únicas ofertadas",
  "Secciones": "Grupos de materia × docente",
  "Aulas Virtuales": "Cursos activos en plataforma AVAC",
  "Matrículas con Repitencia": "Estudiantes que repiten alguna materia",
  "Con Riesgo Calculado": "Estudiantes con indicador de riesgo generado",
  "Con Calificaciones": "Estudiantes con notas registradas",
  "Docentes (calificaciones)": "Docentes que han registrado calificaciones",
  "Total analizadas": "Intervenciones cerradas evaluadas",
  "Exitosas": "Intervenciones con resultado positivo",
  "No exitosas": "Intervenciones sin mejora observable",
  "Tasa de éxito": "Porcentaje de intervenciones exitosas",
};

function KPICard({ label, value, sub, icon, accent = PBI.blue, onClick }) {
  const clickable = !!onClick;
  const tooltip = clickable ? "Clic para ver listado" : (KPI_TOOLTIPS[label] || label);
  return (
    <div
      className={`rounded-lg p-4 flex flex-col transition-all ${clickable ? "cursor-pointer hover:shadow-lg hover:-translate-y-0.5" : "hover:shadow-sm"}`}
      style={{ background: PBI.card, border: `1px solid ${PBI.border}`, borderTop: `3px solid ${accent}` }}
      onClick={onClick}
      title={tooltip}
    >
      <div className="flex items-center gap-2 mb-1">
        {icon && <span className="text-base">{icon}</span>}
        <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: PBI.slate }}>{label}</span>
        {clickable && <span className="text-[10px] ml-auto" style={{ color: PBI.blue }}>▸ ver lista</span>}
      </div>
      <div className="text-2xl font-bold leading-tight" style={{ color: PBI.navy }}>{value ?? "—"}</div>
      {sub && <span className="text-[11px] mt-0.5" style={{ color: PBI.slate }}>{sub}</span>}
    </div>
  );
}

/* ── Mini horizontal bar ───────────────── */
function MiniBar({ label, value, total, color = PBI.blue }) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 truncate" style={{ color: PBI.slate }} title={label}>{label}</span>
      <div className="flex-1 rounded-full h-2.5 overflow-hidden" style={{ background: "#f1f5f9" }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
      </div>
      <span className="w-12 text-right font-semibold" style={{ color: PBI.navy }}>{value}</span>
    </div>
  );
}

/* ── Donut chart section (PBI style) ──── */
function DonutSection({ title, data, colors, total, onItemClick }) {
  if (!data || data.length === 0) return null;
  const titleWithCount = `${title} (n=${data.length})`;
  return (
    <div className="rounded-lg p-4" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
      <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: PBI.slate }}>{titleWithCount}</h3>
      <div className="flex items-center gap-4">
        <div style={{ position: "relative", width: 120, height: 120 }}>
          <ResponsiveContainer width={120} height={120}>
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={30} outerRadius={50} paddingAngle={3} strokeWidth={0}>
                {data.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
              </Pie>
              <Tooltip contentStyle={pbiTooltipStyle} formatter={(v, name) => {
                const pct = total > 0 ? ((v / total) * 100).toFixed(1) : 0;
                return [`${v.toLocaleString()} (${pct}%)`, name];
              }} />
            </PieChart>
          </ResponsiveContainer>
          {total > 0 && (
            <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", textAlign: "center", pointerEvents: "none" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: PBI.navy, lineHeight: 1.1 }}>{total.toLocaleString()}</div>
              <div style={{ fontSize: 8, color: PBI.slate, textTransform: "uppercase" }}>Total</div>
            </div>
          )}
        </div>
        <div className="flex-1 space-y-1.5">
          {data.map((d, i) => {
            const clickHandler = onItemClick ? () => onItemClick(d.name) : undefined;
            return (
              <div key={d.name}
                className={`flex items-center gap-2 text-xs ${clickHandler ? "cursor-pointer hover:bg-blue-50/40 rounded-md px-1 -mx-1 py-0.5 transition-colors" : ""}`}
                onClick={clickHandler} title={clickHandler ? "Clic para ver listado" : undefined}>
                <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: colors[i % colors.length] }} />
                <span className="truncate flex-1" style={{ color: PBI.navy }}>{d.name}</span>
                <span className="font-semibold" style={{ color: PBI.navy }}>{d.value.toLocaleString()}</span>
                <span className="w-10 text-right" style={{ color: PBI.slate }}>{total > 0 ? `${Math.round(d.value / total * 100)}%` : ""}</span>
                {clickHandler && <span className="text-[10px]" style={{ color: PBI.blue }}>▸</span>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ── Horizontal bar chart (all items, PBI) ── */
function HBarChart({ title, data, color = PBI.blue, maxItems = 999, leftMargin = 180 }) {
  if (!data || data.length === 0) return null;
  const sliced = data.slice(0, maxItems);
  const totalSum = sliced.reduce((s, d) => s + (d.value || 0), 0);
  const titleAnnotated = `${title} (n=${sliced.length})`;
  return (
    <div className="rounded-lg p-4" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
      <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: PBI.slate }}>{titleAnnotated}</h3>
      <ResponsiveContainer width="100%" height={Math.max(sliced.length * 32, 120)}>
        <BarChart data={sliced} layout="vertical" margin={{ top: 0, right: 50, bottom: 0, left: 10 }}>
          <CartesianGrid horizontal={false} stroke="#f1f5f9" />
          <XAxis type="number" tick={{ fontSize: 10, fill: PBI.slate }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: PBI.navy }} width={leftMargin} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={pbiTooltipStyle} formatter={(v, _, p) => {
            const pct = totalSum > 0 ? ((v / totalSum) * 100).toFixed(1) : 0;
            return [`${v.toLocaleString()} estudiantes (${pct}%)`, p.payload.full || p.payload.name];
          }} />
          <Bar dataKey="value" fill={color} radius={[0, 6, 6, 0]} barSize={18}>
            <LabelList dataKey="value" position="right" style={{ fontSize: 10, fill: PBI.navy, fontWeight: 600 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ── Export config columns ─────────────── */
const DEFAULT_EXPORT_COLS = [
  "cedula", "nombre", "correo_institucional", "carrera",
  "nivel_academico", "nivel_riesgo", "promedio_calificaciones",
];

/* ── Tabla de estudiantes de una escuela (prácticas) ── */
function StudentTable({ esc, navigate }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {esc.nombre_autoridad && (
        <div className="px-3 py-2 bg-amber-50 border-b border-amber-100 text-xs text-amber-800">
          <span className="font-medium">Autoridad:</span> {esc.nombre_autoridad} ({esc.cargo_autoridad}) — {esc.telefono_autoridad}
        </div>
      )}
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-gray-50 text-gray-500 text-left">
            <th className="px-3 py-2 font-medium">Estudiante</th>
            <th className="px-3 py-2 font-medium">Cédula</th>
            <th className="px-3 py-2 font-medium">Correo</th>
            <th className="px-3 py-2 font-medium">Centro</th>
            <th className="px-3 py-2 font-medium">Nivel / Práctica</th>
            <th className="px-3 py-2 font-medium">Mineduc</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {(esc.estudiantes || []).map((est, i) => (
            <tr key={i} className="hover:bg-blue-50/40">
              <td className="px-3 py-2">
                <button className="font-medium text-blue-700 hover:text-blue-900 hover:underline text-left"
                  onClick={() => navigate(`/ficha/${est.student_id}`)}>
                  {est.nombre || est.cedula || `#${est.student_id}`}
                </button>
              </td>
              <td className="px-3 py-2 text-gray-500">{est.cedula}</td>
              <td className="px-3 py-2 text-gray-500">{est.correo}</td>
              <td className="px-3 py-2 text-gray-500">{est.centro_apoyo}</td>
              <td className="px-3 py-2 text-gray-500">{est.nivel_practica}</td>
              <td className="px-3 py-2">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${est.en_mineduc === "Sí" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                  {est.en_mineduc || "—"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* (PBI palette is now defined globally at the top of the file) */

/* ── Custom Treemap cell (distritos) ── */
function TreemapCell({ x, y, width, height, name, value, fill }) {
  if (width < 30 || height < 20) return null;
  const code = (name || "").replace(/^Distrito\s+/, "");
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={4}
        style={{ fill, stroke: "#fff", strokeWidth: 2, cursor: "default" }} />
      {width > 50 && height > 30 && (
        <>
          <text x={x + width / 2} y={y + height / 2 - 6} textAnchor="middle" fill="#fff"
            style={{ fontSize: Math.min(13, width / 6), fontWeight: 700 }}>{code}</text>
          <text x={x + width / 2} y={y + height / 2 + 10} textAnchor="middle" fill="rgba(255,255,255,0.85)"
            style={{ fontSize: Math.min(11, width / 7) }}>{value} est.</text>
        </>
      )}
    </g>
  );
}

/* ── Custom Treemap cell (generic, for carreras & distritos) ── */
function SmartTreemapCell({ x, y, width, height, name, value, fill, total }) {
  if (width < 4 || height < 4) return null;
  const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
  const canFitName = width > 60 && height > 36;
  const canFitValue = width > 35 && height > 20;
  const fontSize = Math.max(9, Math.min(14, Math.min(width / 7, height / 3.5)));
  const subFontSize = Math.max(8, fontSize - 2);
  const maxChars = Math.max(5, Math.floor(width / (fontSize * 0.52)));
  const displayName = name && name.length > maxChars ? name.slice(0, maxChars - 1) + "\u2026" : name;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={5}
        style={{ fill, stroke: "#fff", strokeWidth: 2, cursor: "pointer", opacity: 0.92, transition: "opacity 0.15s" }}
        onMouseOver={e => e.currentTarget.style.opacity = 1}
        onMouseOut={e => e.currentTarget.style.opacity = 0.92} />
      {canFitName && (
        <>
          <text x={x + width / 2} y={y + height / 2 - (height > 48 ? 7 : 2)} textAnchor="middle" fill="#fff"
            style={{ fontSize, fontWeight: 700, textShadow: "0 1px 4px rgba(0,0,0,0.5)", pointerEvents: "none" }}>{displayName}</text>
          <text x={x + width / 2} y={y + height / 2 + (height > 48 ? 11 : 13)} textAnchor="middle" fill="rgba(255,255,255,0.9)"
            style={{ fontSize: subFontSize, fontWeight: 500, pointerEvents: "none" }}>{value.toLocaleString()} ({pct}%)</text>
        </>
      )}
      {!canFitName && canFitValue && (
        <text x={x + width / 2} y={y + height / 2 + 3} textAnchor="middle" fill="#fff"
          style={{ fontSize: Math.max(8, fontSize - 1), fontWeight: 700, pointerEvents: "none" }}>{value.toLocaleString()}</text>
      )}
    </g>
  );
}

/* ── Hybrid Chart: Treemap (top items) + compact table (rest) ── */
function HybridTreemapChart({ title, data, total, topN = 10, onItemClick, palette = PBI.palette }) {
  if (!data || data.length === 0) return null;
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const topItems = sorted.slice(0, topN);
  const restItems = sorted.slice(topN);
  const topTotal = topItems.reduce((s, d) => s + d.value, 0);
  const treemapData = topItems.map((d, i) => ({ name: d.name, size: d.value, fill: palette[i % palette.length] }));

  return (
    <div className="rounded-lg p-4" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
      <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: PBI.slate }}>
        {title} ({data.length} total \u00B7 {total.toLocaleString()} estudiantes)
      </h3>
      {/* Treemap for top items */}
      <ResponsiveContainer width="100%" height={Math.max(280, Math.min(420, topItems.length * 30))}>
        <Treemap data={treemapData} dataKey="size" nameKey="name" isAnimationActive={false}
          content={<SmartTreemapCell total={total} />}
          onClick={(node) => { if (onItemClick && node?.name) onItemClick(node.name); }}
        >
          <Tooltip contentStyle={pbiTooltipStyle} formatter={(v, name) => {
            const pct = total > 0 ? ((v / total) * 100).toFixed(1) : 0;
            return [`${v.toLocaleString()} estudiantes (${pct}%)`, name];
          }} />
        </Treemap>
      </ResponsiveContainer>

      {/* Compact table for remaining items */}
      {restItems.length > 0 && (
        <div className="mt-3 pt-3" style={{ borderTop: `1px solid ${PBI.border}` }}>
          <div className="text-[10px] font-semibold uppercase tracking-wider mb-2" style={{ color: PBI.slate }}>
            Otras ({restItems.length})
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-x-4 gap-y-1">
            {restItems.map((d, i) => {
              const pct = total > 0 ? ((d.value / total) * 100).toFixed(1) : 0;
              return (
                <div key={d.name}
                  className={`flex items-center justify-between text-xs py-1 px-2 rounded ${onItemClick ? "cursor-pointer hover:bg-blue-50/60 transition-colors" : ""}`}
                  onClick={onItemClick ? () => onItemClick(d.name) : undefined}
                  title={d.name}>
                  <span className="flex items-center gap-1.5 truncate flex-1 min-w-0">
                    <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: palette[(topN + i) % palette.length] }} />
                    <span className="truncate" style={{ color: PBI.navy }}>{d.name}</span>
                  </span>
                  <span className="ml-2 flex-shrink-0 font-semibold" style={{ color: PBI.slate }}>{d.value} <span className="font-normal text-[10px]">({pct}%)</span></span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Componente PBI KPI (mini card estilo dashboard) ── */
function PBIKpi({ label, value, sub, accent }) {
  return (
    <div className="rounded-lg p-4 flex flex-col" style={{ background: PBI.card, border: `1px solid ${PBI.border}`, borderTop: `3px solid ${accent}` }}>
      <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: PBI.slate }}>{label}</span>
      <span className="text-2xl font-bold mt-1" style={{ color: PBI.navy }}>{value}</span>
      {sub && <span className="text-[11px] mt-0.5" style={{ color: PBI.slate }}>{sub}</span>}
    </div>
  );
}

/* ── Chip de filtro ── */
const filterCls = "border rounded-lg px-3 py-1.5 text-xs bg-white focus:ring-2 focus:ring-blue-200 focus:border-blue-400 transition-colors";

/* ══════════════════════════════════════════
   PRÁCTICAS TAB (Power BI style)
   ══════════════════════════════════════════ */
function PracticasTab({ data: practicasData, loading, filtros, setFiltros, expanded, setExpanded, escuelaAbierta, setEscuelaAbierta, search, setSearch, navigate }) {
  if (loading) return <div className="text-center py-10 text-gray-400">Cargando datos de prácticas...</div>;
  if (!practicasData || practicasData.total_estudiantes === 0) return (
    <div className="text-center py-16 text-gray-300">
      <div className="text-4xl mb-3">{"🏫"}</div>
      <div className="text-sm">No hay datos de prácticas preprofesionales</div>
      <p className="text-xs text-gray-400 mt-1">Sube el archivo de formularios desde el panel Admin</p>
    </div>
  );

  const pd = practicasData;
  const pctMineduc = pd.total_estudiantes ? Math.round(pd.en_mineduc / pd.total_estudiantes * 100) : 0;

  // District data for hybrid chart
  const distritoChartData = (pd.por_distrito || []).map(d => ({
    name: d.distrito,
    value: d.total,
  }));
  const distritoTotal = distritoChartData.reduce((s, d) => s + d.value, 0);

  // Nivel data for horizontal bars (cleaned names)
  const nivelData = (pd.por_nivel || []).map(n => ({
    name: n.nivel.replace(/^\d+\w+ nivel - /, ""),
    full: n.nivel,
    value: n.total,
  }));

  // Sistema data for donut
  const sistemaData = (pd.por_sistema || []).map(s => ({ name: s.sistema, value: s.total }));
  const sistemaColors = ["#2B5EA7", "#0F9B8D", "#7B61FF", "#EB5757"];

  // Centro data for bar
  const centroData = (pd.por_centro || []).map(c => ({ name: c.centro, value: c.total }));
  const centroColors = ["#2B5EA7", "#0F9B8D", "#F2C94C", "#EB5757"];

  return (
    <div className="space-y-4" style={{ background: PBI.bg }}>
      {/* ── Row 1: KPI strip ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <PBIKpi label="Practicantes" value={pd.total_estudiantes} accent={PBI.blue} />
        <PBIKpi label="Escuelas" value={pd.total_escuelas} accent={PBI.teal} />
        <PBIKpi label="Distritos" value={pd.total_distritos} accent={PBI.purple} />
        <PBIKpi label="En Mineduc" value={pd.en_mineduc} accent={PBI.gold} sub={`${pctMineduc}% del total`} />
      </div>

      {/* ── Filtros (pill bar) ── */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-[10px] font-semibold uppercase tracking-widest mr-1" style={{ color: PBI.slate }}>Filtros</span>
        <select value={filtros.sistema} onChange={e => setFiltros(f => ({ ...f, sistema: e.target.value }))} className={filterCls} style={{ borderColor: PBI.border }}>
          <option value="">Sistema educativo</option>
          {(pd.filtros?.sistemas_educativos || []).map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filtros.distrito} onChange={e => setFiltros(f => ({ ...f, distrito: e.target.value }))} className={filterCls} style={{ borderColor: PBI.border }}>
          <option value="">Distrito</option>
          {(pd.filtros?.distritos || []).map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <select value={filtros.centro} onChange={e => setFiltros(f => ({ ...f, centro: e.target.value }))} className={filterCls} style={{ borderColor: PBI.border }}>
          <option value="">Centro de apoyo</option>
          {(pd.filtros?.centros_apoyo || []).map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={filtros.nivel} onChange={e => setFiltros(f => ({ ...f, nivel: e.target.value }))} className={filterCls} style={{ borderColor: PBI.border }}>
          <option value="">Nivel de práctica</option>
          {(pd.filtros?.niveles_practica || []).map(n => <option key={n} value={n}>{n}</option>)}
        </select>
        {(filtros.sistema || filtros.distrito || filtros.centro || filtros.nivel) && (
          <button onClick={() => setFiltros({ sistema: "", distrito: "", centro: "", nivel: "" })}
            className="text-[10px] text-red-500 hover:text-red-700 font-medium ml-1">Limpiar</button>
        )}
      </div>

      {/* ── Row 2: Charts grid (2 cols) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Sistema Educativo — donut */}
        <div className="rounded-lg p-4" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: PBI.slate }}>Sistema Educativo (n={sistemaData.length})</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={sistemaData} cx="50%" cy="50%" innerRadius={45} outerRadius={75} paddingAngle={3}
                dataKey="value" nameKey="name" strokeWidth={0}>
                {sistemaData.map((_, i) => <Cell key={i} fill={sistemaColors[i % sistemaColors.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}
                formatter={(v, name) => {
                  const tot = sistemaData.reduce((s, d) => s + d.value, 0);
                  const pct = tot > 0 ? ((v / tot) * 100).toFixed(1) : 0;
                  return [`${v} estudiantes (${pct}%)`, name];
                }} />
              <Legend iconType="circle" iconSize={8}
                formatter={(v, entry) => {
                  const item = sistemaData.find(d => d.name === v);
                  const tot = sistemaData.reduce((s, d) => s + d.value, 0);
                  const pct = item && tot > 0 ? Math.round((item.value / tot) * 100) : 0;
                  return <span style={{ fontSize: 11, color: PBI.slate }}>{v} ({pct}%)</span>;
                }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Centro de Apoyo — bar */}
        <div className="rounded-lg p-4" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: PBI.slate }}>Centro de Apoyo (n={centroData.length})</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={centroData} barCategoryGap="20%">
              <CartesianGrid vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: PBI.slate }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: PBI.slate }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}
                formatter={(v) => {
                  const tot = centroData.reduce((s, d) => s + d.value, 0);
                  const pct = tot > 0 ? ((v / tot) * 100).toFixed(1) : 0;
                  return [`${v} estudiantes (${pct}%)`, ""];
                }} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {centroData.map((_, i) => <Cell key={i} fill={centroColors[i % centroColors.length]} />)}
                <LabelList dataKey="value" position="top" style={{ fontSize: 10, fill: PBI.navy, fontWeight: 600 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Row 3: Nivel de práctica (horizontal) + Treemap distritos ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Nivel de práctica */}
        <div className="rounded-lg p-4" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: PBI.slate }}>Nivel de Práctica (n={nivelData.length})</h3>
          <ResponsiveContainer width="100%" height={nivelData.length * 45 + 20}>
            <BarChart data={nivelData} layout="vertical" barCategoryGap="25%">
              <CartesianGrid horizontal={false} stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 10, fill: PBI.slate }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" width={180} tick={{ fontSize: 11, fill: PBI.navy }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}
                formatter={(v, _, p) => {
                  const tot = nivelData.reduce((s, d) => s + d.value, 0);
                  const pct = tot > 0 ? ((v / tot) * 100).toFixed(1) : 0;
                  return [`${v} estudiantes (${pct}%)`, p.payload.full];
                }} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                {nivelData.map((_, i) => <Cell key={i} fill={[PBI.teal, PBI.blue, PBI.purple][i % 3]} />)}
                <LabelList dataKey="value" position="right" style={{ fontSize: 10, fill: PBI.navy, fontWeight: 600 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Distribución por Distrito — hybrid treemap */}
        {distritoChartData.length > 0 && (
          <HybridTreemapChart
            title="Distribución por Distrito"
            data={distritoChartData}
            total={distritoTotal}
            topN={8}
          />
        )}
      </div>

      {/* ── Buscador de escuelas ── */}
      <div className="rounded-lg overflow-hidden" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
        <div className="px-4 py-3 flex items-center gap-3" style={{ borderBottom: `1px solid ${PBI.border}` }}>
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: PBI.slate }}>Buscar escuela</span>
          <input type="text" placeholder="Nombre o código AMIE..."
            value={search} onChange={e => setSearch(e.target.value)}
            className="flex-1 border rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-400"
            style={{ borderColor: PBI.border }} />
        </div>
        {search.trim().length >= 2 && (() => {
          const q = search.trim().toLowerCase();
          const matches = (pd.escuelas || []).filter(e =>
            (e.nombre_escuela || "").toLowerCase().includes(q) || (e.amie || "").toLowerCase().includes(q)
          ).slice(0, 20);
          if (matches.length === 0) return <div className="px-4 py-6 text-center text-sm" style={{ color: PBI.slate }}>No se encontraron escuelas</div>;
          return (
            <div className="divide-y" style={{ borderColor: PBI.border }}>
              {matches.map((esc, i) => (
                <div key={esc.amie || i}>
                  <button onClick={() => setEscuelaAbierta(escuelaAbierta?.amie === esc.amie ? null : esc)}
                    className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-blue-50/40 transition-colors text-left">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px]" style={{ color: PBI.slate }}>{escuelaAbierta?.amie === esc.amie ? "▼" : "▶"}</span>
                      <span className="text-sm font-medium" style={{ color: PBI.navy }}>{esc.nombre_escuela}</span>
                      {esc.amie && <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: "#f1f5f9", color: PBI.slate }}>{esc.amie}</span>}
                      <span className="text-[10px]" style={{ color: PBI.purple }}>{esc.distrito}</span>
                      <span className="text-[10px]" style={{ color: PBI.slate }}>{esc.sistema_educativo}</span>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold" style={{ background: "#ecfdf5", color: PBI.teal }}>{esc.total_estudiantes} est.</span>
                  </button>
                  {escuelaAbierta?.amie === esc.amie && (
                    <div className="px-4 pb-3"><StudentTable esc={esc} navigate={navigate} /></div>
                  )}
                </div>
              ))}
            </div>
          );
        })()}
      </div>

      {/* ── Distritos → Escuelas → Estudiantes ── */}
      <div className="rounded-lg overflow-hidden" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
        <div className="px-4 py-3" style={{ background: PBI.navy }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-white">Distritos y Escuelas</h3>
        </div>
        <div className="divide-y" style={{ borderColor: PBI.border }}>
          {(pd.distritos || []).map((dist, dIdx) => (
            <div key={dist.distrito}>
              <button onClick={() => setExpanded(prev => ({ ...prev, [dIdx]: !prev[dIdx] }))}
                className="w-full flex items-center justify-between px-4 py-3 transition-colors text-left"
                style={{ background: expanded[dIdx] ? "#f8fafc" : "transparent" }}
                onMouseEnter={e => { if (!expanded[dIdx]) e.currentTarget.style.background = "#f8fafc"; }}
                onMouseLeave={e => { if (!expanded[dIdx]) e.currentTarget.style.background = "transparent"; }}>
                <div className="flex items-center gap-2">
                  <span className="text-xs" style={{ color: PBI.blue }}>{expanded[dIdx] ? "▼" : "▶"}</span>
                  <span className="font-semibold text-sm" style={{ color: PBI.navy }}>{dist.distrito}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[10px]" style={{ color: PBI.slate }}>{dist.total_escuelas} escuela{dist.total_escuelas !== 1 ? "s" : ""}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold" style={{ background: "#dbeafe", color: PBI.blue }}>{dist.total_estudiantes} est.</span>
                </div>
              </button>
              {expanded[dIdx] && (
                <div style={{ borderTop: `1px solid ${PBI.border}`, background: "#fafbfc" }}>
                  {dist.escuelas.map((esc, eIdx) => {
                    const isOpen = escuelaAbierta?.amie === esc.amie && escuelaAbierta?.distrito === dist.distrito;
                    return (
                      <div key={esc.amie || eIdx}>
                        <button onClick={() => setEscuelaAbierta(isOpen ? null : esc)}
                          className="w-full flex items-center justify-between px-6 py-2 hover:bg-blue-50/50 transition-colors text-left">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px]" style={{ color: PBI.teal }}>{isOpen ? "▼" : "▶"}</span>
                            <span className="text-sm" style={{ color: PBI.navy }}>{esc.nombre_escuela || "Sin nombre"}</span>
                            {esc.amie && <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "#f1f5f9", color: PBI.slate }}>{esc.amie}</span>}
                          </div>
                          <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold" style={{ background: "#ecfdf5", color: PBI.teal }}>{esc.total_estudiantes} est.</span>
                        </button>
                        {isOpen && (
                          <div className="px-6 pb-3"><StudentTable esc={esc} navigate={navigate} /></div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════ */
export default function ResumenDatos() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [carreras, setCarreras] = useState([]);
  const [filtroCarrera, setFiltroCarrera] = useState("");
  const [filtroPeriodo, setFiltroPeriodo] = useState("");
  const [comparativa, setComparativa] = useState([]);

  // Export
  const [exportOpen, setExportOpen] = useState(false);
  const [colsDisponibles, setColsDisponibles] = useState([]);
  const [colsSeleccionadas, setColsSeleccionadas] = useState(new Set(DEFAULT_EXPORT_COLS));
  const [exportCarrera, setExportCarrera] = useState("");
  const [exportNivel, setExportNivel] = useState("");
  const [exportRiesgo, setExportRiesgo] = useState("");
  const [exportPeriodo, setExportPeriodo] = useState("");
  const [exporting, setExporting] = useState(false);

  // Carrera expand
  const [expandedCarrera, setExpandedCarrera] = useState(null);

  // Student list modal (shared component)
  const { openStudentList, StudentListModalEl } = useStudentListModal({
    periodo: filtroPeriodo,
    carrera: filtroCarrera,
  });

  // Tab
  const [activeTab, setActiveTab] = useState("general");
  const [kpiCollapsed, setKpiCollapsed] = useState(false);

  // Prácticas preprofesionales
  const [practicasData, setPracticasData] = useState(null);
  const [practicasLoading, setPracticasLoading] = useState(false);
  const [practicasFiltros, setPracticasFiltros] = useState({ sistema: "", distrito: "", centro: "", nivel: "" });
  const [practicasExpanded, setPracticasExpanded] = useState({});  // distrito idx
  const [practicasEscuela, setPracticasEscuela] = useState(null);  // escuela seleccionada para ver estudiantes
  const [practicasSearch, setPracticasSearch] = useState("");  // búsqueda de escuelas
  const [execData, setExecData] = useState(null);
  const [execLoading, setExecLoading] = useState(false);
  const [effData, setEffData] = useState(null);
  const [effLoading, setEffLoading] = useState(false);

  useEffect(() => {
    api.getCarreras().then(setCarreras).catch(() => {});
    api.getExportColumnas().then(setColsDisponibles).catch(() => {});
  }, []);

  const loadData = useCallback(async () => {
    if (!filtroPeriodo) return;
    setLoading(true);
    setError(null);
    try {
      const params = { periodo: filtroPeriodo };
      if (filtroCarrera) params.carrera = filtroCarrera;
      const compParams = {};
      if (filtroCarrera) compParams.carrera = filtroCarrera;
      const [result, compData] = await Promise.allSettled([
        api.getResumenDatos(params),
        api.getComparativa(compParams),
      ]);
      if (result.status === "fulfilled") setData(result.value);
      if (compData.status === "fulfilled") setComparativa(compData.value);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filtroCarrera, filtroPeriodo]);

  useEffect(() => { loadData(); }, [loadData]);

  // Load prácticas data when tab is active
  useEffect(() => {
    if (activeTab !== "practicas") return;
    setPracticasLoading(true);
    const params = {};
    if (filtroPeriodo) params.periodo = filtroPeriodo;
    if (practicasFiltros.sistema) params.sistema_educativo = practicasFiltros.sistema;
    if (practicasFiltros.distrito) params.distrito = practicasFiltros.distrito;
    if (practicasFiltros.centro) params.centro_apoyo = practicasFiltros.centro;
    if (practicasFiltros.nivel) params.nivel_practica = practicasFiltros.nivel;
    api.getPracticasResumen(params)
      .then(d => { setPracticasData(d); setPracticasEscuela(null); })
      .catch(e => { console.error("Error cargando prácticas:", e); setPracticasData(null); })
      .finally(() => setPracticasLoading(false));
  }, [activeTab, filtroPeriodo, practicasFiltros]);

  // Load executive dashboard data when tab is active
  useEffect(() => {
    if (activeTab !== "ejecutivo") return;
    setExecLoading(true);
    api.getExecutiveDashboard(filtroPeriodo)
      .then(d => setExecData(d))
      .catch(() => setExecData(null))
      .finally(() => setExecLoading(false));
  }, [activeTab, filtroPeriodo]);

  // Load effectiveness data when tab is active
  useEffect(() => {
    if (activeTab !== "efectividad") return;
    setEffLoading(true);
    api.getEffectiveness(filtroPeriodo)
      .then(d => setEffData(d))
      .catch(() => setEffData(null))
      .finally(() => setEffLoading(false));
  }, [activeTab, filtroPeriodo]);

  const toggleCol = (key) => {
    setColsSeleccionadas(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };
  const selectAllCols = () => setColsSeleccionadas(new Set(colsDisponibles.map(c => c.key)));
  const deselectAllCols = () => setColsSeleccionadas(new Set(["cedula", "nombre"]));

  const handleExport = async () => {
    if (colsSeleccionadas.size === 0) return;
    setExporting(true);
    try {
      const params = new URLSearchParams();
      params.set("columnas", Array.from(colsSeleccionadas).join(","));
      if (exportCarrera) params.set("carrera", exportCarrera);
      if (exportNivel) params.set("nivel", exportNivel);
      if (exportRiesgo) params.set("nivel_riesgo", exportRiesgo);
      if (exportPeriodo) params.set("periodo", exportPeriodo);
      const blob = await api.exportEstudiantesExcel(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "estudiantes.xlsx"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { alert(e.message); }
    finally { setExporting(false); }
  };

  const g = data?.global || {};
  const porCarrera = data?.por_carrera || [];

  /* ── Derived chart data ──────────────── */
  const riskData = g.por_riesgo ? Object.entries(g.por_riesgo).filter(([,v]) => v > 0).map(([k, v]) => ({ name: k, value: v })) : [];
  const riskColors = riskData.map(d => RISK_COLORS[d.name] || "#94a3b8");

  const genderData = g.por_genero ? Object.entries(g.por_genero).map(([k, v]) => ({ name: k, value: v })) : [];
  const genderColors = genderData.map(d => GENDER_COLORS[d.name] || "#94a3b8");

  const etniaData = g.por_etnia ? Object.entries(g.por_etnia).slice(0, 8).map(([k, v]) => ({ name: k, value: v })) : [];
  const ciudadData = g.por_ciudad ? Object.entries(g.por_ciudad).slice(0, 12).map(([k, v]) => ({ name: k, value: v })) : [];
  const sedeData = g.por_sede ? Object.entries(g.por_sede).filter(([k]) => k !== "Sin dato").map(([k, v]) => ({ name: k, value: v })) : [];
  const nivelData = g.por_nivel ? Object.entries(g.por_nivel).map(([k, v]) => ({ name: `Nivel ${k}`, value: v })) : [];
  const tipoAsigData = g.por_tipo_asignatura ? Object.entries(g.por_tipo_asignatura).map(([k, v]) => ({ name: k, value: v })) : [];

  const carreraBarData = porCarrera
    .sort((a, b) => b.total_estudiantes - a.total_estudiantes)
    .map(c => ({ name: c.carrera?.length > 45 ? c.carrera.slice(0, 43) + "…" : c.carrera, value: c.total_estudiantes, full: c.carrera }));

  // Treemap data for carreras
  const carreraTreemapData = porCarrera
    .sort((a, b) => b.total_estudiantes - a.total_estudiantes)
    .map((c, i) => ({ name: c.carrera, size: c.total_estudiantes, fill: PBI.palette[i % PBI.palette.length] }));
  const carreraTreemapTotal = porCarrera.reduce((s, c) => s + c.total_estudiantes, 0);

  const practicasCount = practicasData?.total_estudiantes || 0;
  const TABS = [
    { key: "general", label: "Vista General", icon: "📊" },
    { key: "academico", label: "Académico", icon: "📝" },
    { key: "demografico", label: "Demográfico", icon: "👥" },
    { key: "carreras", label: "Por Carrera", icon: "🎓", badge: porCarrera.length || null },
    { key: "tendencias", label: "Tendencias", icon: "📈", badge: comparativa.length >= 2 ? comparativa.length : null },
    { key: "practicas", label: "Prácticas", icon: "🏫", badge: practicasCount || null },
    { key: "ejecutivo", label: "Ejecutivo", icon: "🛡️" },
    { key: "efectividad", label: "Efectividad", icon: "🎯" },
  ];

  return (
    <div>
      {/* ── Header ─── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: PBI.navy }}>Análisis Institucional</h1>
          <p className="text-sm" style={{ color: PBI.slate }}>
            {filtroPeriodo && g.total_estudiantes
              ? `Período ${filtroPeriodo} — ${g.total_estudiantes?.toLocaleString()} estudiantes en ${g.total_carreras || "—"} carreras`
              : "Panel analítico integral — estudiantes, carreras y métricas institucionales"}
          </p>
        </div>
        <button onClick={() => setExportOpen(!exportOpen)}
          className="flex items-center gap-2 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm hover:opacity-90"
          style={{ background: PBI.teal }}>
          {"📥"} Exportar Excel
        </button>
      </div>

      {/* ── Export Panel ─── */}
      {exportOpen && (
        <div className="bg-white rounded-xl border border-green-200 shadow-sm mb-5 p-5">
          <h3 className="text-sm font-bold text-gray-800 mb-3">Configurar exportación Excel</h3>
          <div className="flex flex-wrap gap-2 mb-4">
            <PeriodSelector value={exportPeriodo} onChange={setExportPeriodo} />
            <select value={exportCarrera} onChange={e => setExportCarrera(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 min-w-[160px]">
              <option value="">Todas las carreras</option>
              {carreras.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={exportNivel} onChange={e => setExportNivel(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500">
              <option value="">Todos los niveles</option>
              {[1,2,3,4,5,6,7,8].map(n => <option key={n} value={n}>Nivel {n}</option>)}
            </select>
            <select value={exportRiesgo} onChange={e => setExportRiesgo(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500">
              <option value="">Todos los riesgos</option>
              {["Alto", "Medio", "Bajo"].map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div className="mb-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-600">Columnas a exportar ({colsSeleccionadas.size} seleccionadas)</span>
              <div className="flex gap-2">
                <button onClick={selectAllCols} className="text-[11px] text-blue-600 hover:underline">Seleccionar todas</button>
                <button onClick={deselectAllCols} className="text-[11px] text-gray-500 hover:underline">Mínimo</button>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-1.5">
              {colsDisponibles.map(col => (
                <label key={col.key} className="flex items-center gap-1.5 text-xs cursor-pointer hover:bg-gray-50 rounded px-1.5 py-1">
                  <input type="checkbox" checked={colsSeleccionadas.has(col.key)} onChange={() => toggleCol(col.key)} className="accent-green-600" />
                  <span className="text-gray-700">{col.label}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleExport} disabled={exporting || colsSeleccionadas.size === 0}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors">
              {exporting ? "Generando..." : "Descargar Excel"}
            </button>
            <button onClick={() => setExportOpen(false)} className="text-sm text-gray-500 hover:text-gray-700">Cerrar</button>
          </div>
        </div>
      )}

      {/* ── Filters ─── */}
      <div className="flex flex-wrap items-end gap-3 mb-5">
        <PeriodSelector value={filtroPeriodo} onChange={setFiltroPeriodo} />
        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Carrera</label>
          <select value={filtroCarrera} onChange={e => setFiltroCarrera(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[160px]">
            <option value="">Todas las carreras</option>
            {carreras.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {/* ── Error ─── */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4 text-red-700 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadData} className="text-red-600 hover:text-red-800 font-medium text-sm">Reintentar</button>
        </div>
      )}

      {/* ── Loading ─── */}
      {loading && <div className="text-center py-12 text-gray-400">Cargando resumen...</div>}

      {/* ── No data banner ─── */}
      {!loading && data?.tiene_datos_periodo === false && !g.tiene_enrollments && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl px-5 py-8 text-center my-5">
          <div className="text-3xl mb-2">{"📋"}</div>
          <h3 className="text-lg font-semibold text-amber-800 mb-1">Aún no hay datos para este período</h3>
          <p className="text-sm text-amber-700">Las estadísticas se actualizarán cuando se carguen calificaciones y datos de AVAC.</p>
        </div>
      )}

      {/* ── Enrollment-only banner ─── */}
      {!loading && data?.tiene_datos_periodo === false && g.tiene_enrollments && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4 text-sm text-blue-800 my-4 flex items-start gap-3">
          <span className="text-xl">{"📝"}</span>
          <div>
            <strong>Datos de matrícula disponibles</strong> — Se muestran datos del reporte de matriculación.
            Los indicadores de calificaciones, riesgo y compromiso se completarán cuando se carguen datos de AVAC.
          </div>
        </div>
      )}

      {/* ── Main content (show if students exist) ─── */}
      {!loading && g.total_estudiantes > 0 && (
        <>
          {/* ── KPI Cards (PBI style, collapsible) ─── */}
          <div className="mb-5">
            <button
              onClick={() => setKpiCollapsed(!kpiCollapsed)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg mb-2 transition-colors hover:bg-gray-50"
              style={{ background: kpiCollapsed ? "#f8fafc" : "transparent" }}
            >
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: PBI.slate }}>
                  Indicadores Principales
                </span>
                {kpiCollapsed && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ background: `${PBI.blue}12`, color: PBI.blue }}>
                    {g.total_estudiantes?.toLocaleString()} est. · {g.total_carreras} carreras · {g.total_docentes_enrollment || g.total_docentes || "—"} doc.
                  </span>
                )}
              </div>
              <span className="text-xs transition-transform" style={{ color: PBI.slate, transform: kpiCollapsed ? "rotate(-90deg)" : "rotate(0deg)" }}>▼</span>
            </button>
            <div style={{
              maxHeight: kpiCollapsed ? 0 : 500,
              opacity: kpiCollapsed ? 0 : 1,
              overflow: "hidden",
              transition: "max-height 0.35s ease, opacity 0.25s ease",
            }}>
              <div className="space-y-3">
                {/* Fila 1: Población y estructura */}
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                  <KPICard icon="🎓" label="Estudiantes" value={g.total_estudiantes?.toLocaleString()} accent={PBI.blue} />
                  <KPICard icon="👨‍🏫" label="Docentes" value={g.total_docentes_enrollment || g.total_docentes || "—"} accent={PBI.teal} />
                  <KPICard icon="📚" label="Carreras" value={g.total_carreras} accent={PBI.purple} />
                  <KPICard icon="📋" label="Matrículas" value={g.total_matriculas?.toLocaleString()} accent={PBI.gold} sub="registros est × materia" />
                  <KPICard icon="📊" label="Prom. Calificaciones" value={g.promedio_calificaciones ?? "—"} accent={PBI.coral} sub={g.promedio_calificaciones ? "sobre 100" : "Aún sin AVAC"} />
                </div>

                {/* Fila 2: Oferta académica */}
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider mb-2 ml-1" style={{ color: PBI.slate }}>Oferta académica</p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <KPICard icon="📖" label="Asignaturas" value={g.total_asignaturas} accent="#06B6D4" sub="materias únicas" />
                    <KPICard icon="📑" label="Secciones" value={g.total_secciones ?? "—"} accent={PBI.orange} sub="materia × docente" />
                    <KPICard icon="🖥️" label="Aulas Virtuales" value={g.total_aulas_virtuales ?? "—"} accent="#6366F1" sub="cursos en AVAC" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── Tab Navigation (PBI style, sticky) ─── */}
          <div className="flex gap-0 mb-5 overflow-x-auto sticky top-0 z-10 -mx-1 px-1" style={{ borderBottom: `2px solid ${PBI.border}`, background: PBI.bg }}>
            {TABS.map(t => (
              <button key={t.key} onClick={() => setActiveTab(t.key)}
                className="px-5 py-2.5 text-sm font-medium transition-colors whitespace-nowrap relative flex items-center gap-1.5"
                style={{
                  color: activeTab === t.key ? PBI.navy : PBI.slate,
                  fontWeight: activeTab === t.key ? 700 : 500,
                  borderBottom: activeTab === t.key ? `3px solid ${PBI.blue}` : "3px solid transparent",
                  marginBottom: "-2px",
                }}>
                <span className="text-sm">{t.icon}</span>
                {t.label}
                {t.badge && (
                  <span className="ml-1 px-1.5 py-0 text-[10px] font-semibold rounded-full" style={{
                    background: activeTab === t.key ? `${PBI.blue}15` : "#f1f5f9",
                    color: activeTab === t.key ? PBI.blue : PBI.slate,
                  }}>{t.badge}</span>
                )}
              </button>
            ))}
          </div>

          {/* ═══ TAB: GENERAL ═══ */}
          {activeTab === "general" && (
            <div className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Risk donut */}
                <DonutSection title="Distribución de Riesgo" data={riskData} colors={riskColors} total={g.total_estudiantes}
                  onItemClick={(name) => {
                    const map = { Alto: "riesgo_alto", Medio: "riesgo_medio", Bajo: "riesgo_bajo" };
                    if (map[name]) openStudentList(map[name]);
                  }} />

                {/* Gender donut */}
                <DonutSection title="Género" data={genderData} colors={genderColors} total={g.total_estudiantes} />

                {/* Academic indicators */}
                <div className="rounded-lg p-4" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                  <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: PBI.slate }}>Indicadores Clave</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm" style={{ color: PBI.slate }}>Reprobados</span>
                      <span className="text-lg font-bold" style={{ color: PBI.coral }}>{g.reprobados ?? 0}</span>
                    </div>
                    <div className="flex justify-between items-center cursor-pointer hover:bg-blue-50/40 rounded-lg px-2 py-1 -mx-2 transition-colors"
                         onClick={() => openStudentList("repitentes")} title="Clic para ver listado">
                      <span className="text-sm" style={{ color: PBI.slate }}>Repitentes</span>
                      <span className="text-lg font-bold flex items-center gap-1" style={{ color: PBI.gold }}>{g.repitentes ?? 0} <span className="text-[10px]" style={{ color: PBI.blue }}>▸</span></span>
                    </div>
                    <div className="flex justify-between items-center cursor-pointer hover:bg-blue-50/40 rounded-lg px-2 py-1 -mx-2 transition-colors"
                         onClick={() => openStudentList("condicionados")} title="Clic para ver listado de condicionados (3ra matrícula)">
                      <span className="text-sm" style={{ color: PBI.slate }}>Condicionados</span>
                      <span className="text-lg font-bold flex items-center gap-1" style={{ color: PBI.purple }}>{g.condicionados ?? 0} <span className="text-[10px]" style={{ color: PBI.blue }}>▸</span></span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm" style={{ color: PBI.slate }}>Prob. deserción alta</span>
                      <span className="text-lg font-bold" style={{ color: PBI.coral }}>{g.desertores_prob ?? 0}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm" style={{ color: PBI.slate }}>Compromiso promedio</span>
                      <span className="text-lg font-bold" style={{ color: PBI.teal }}>{g.promedio_compromiso ? `${(g.promedio_compromiso * 100).toFixed(0)}%` : "—"}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm" style={{ color: PBI.slate }}>Edad promedio</span>
                      <span className="text-lg font-bold" style={{ color: PBI.navy }}>{g.promedio_edad ? `${g.promedio_edad} años` : "—"}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Estudiantes por carrera — hybrid treemap + table */}
              {carreraBarData.length > 0 && (
                <HybridTreemapChart
                  title="Distribución por Carrera"
                  data={carreraBarData.map(d => ({ name: d.full || d.name, value: d.value }))}
                  total={carreraTreemapTotal}
                  topN={10}
                  onItemClick={(name) => { setActiveTab("carreras"); setExpandedCarrera(name); }}
                />
              )}

              {/* Intervenciones summary */}
              {g.intervenciones && g.intervenciones.total > 0 && (
                <div className="rounded-lg overflow-hidden" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                  <div className="px-5 py-4 flex items-center justify-between" style={{ borderBottom: `1px solid ${PBI.border}` }}>
                    <div>
                      <h3 className="text-sm font-bold" style={{ color: PBI.navy }}>Intervenciones</h3>
                      <p className="text-xs mt-0.5" style={{ color: PBI.slate }}>Seguimiento y resolución de casos</p>
                    </div>
                  </div>
                  <div className="p-5">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                      {[
                        { v: g.intervenciones.total, l: "Total", c: PBI.blue },
                        { v: g.intervenciones.resueltas, l: "Resueltas", c: PBI.teal },
                        { v: g.intervenciones.pendientes_seguimiento, l: "Pendientes", c: PBI.gold },
                        { v: g.intervenciones.total > 0 ? `${Math.round((g.intervenciones.resueltas / g.intervenciones.total) * 100)}%` : "—", l: "Resolución", c: PBI.slate },
                      ].map(({ v, l, c }) => (
                        <div key={l} className="text-center rounded-lg px-3 py-2.5" style={{ background: `${c}10`, borderTop: `3px solid ${c}` }}>
                          <div className="text-xl font-bold" style={{ color: PBI.navy }}>{v}</div>
                          <div className="text-[10px] uppercase font-medium" style={{ color: c }}>{l}</div>
                        </div>
                      ))}
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <div className="text-[10px] font-semibold uppercase mb-2" style={{ color: PBI.slate }}>Por motivo</div>
                        <div className="space-y-1.5">
                          {Object.entries(g.intervenciones.por_motivo || {}).sort((a,b) => b[1]-a[1]).map(([m, c]) => (
                            <MiniBar key={m} label={m} value={c} total={g.intervenciones.total} color={PBI.blue} />
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-semibold uppercase mb-2" style={{ color: PBI.slate }}>Por resultado</div>
                        <div className="space-y-1.5">
                          {Object.entries(g.intervenciones.por_resultado || {}).sort((a,b) => b[1]-a[1]).map(([r, c]) => (
                            <MiniBar key={r} label={r} value={c} total={g.intervenciones.total} color={PBI.purple} />
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ═══ TAB: ACADÉMICO ═══ */}
          {activeTab === "academico" && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <KPICard icon="📝" label="Matrículas con Repitencia" value={g.matriculas_con_repitencia ?? 0} accent={PBI.gold} />
                <KPICard icon="🎯" label="Con Riesgo Calculado" value={g.con_riesgo_calculado ?? 0} accent={PBI.coral} />
                <KPICard icon="📈" label="Con Calificaciones" value={g.con_calificaciones ?? 0} accent={PBI.blue} />
                <KPICard icon="👨‍🏫" label="Docentes (calificaciones)" value={g.total_docentes ?? 0} accent={PBI.teal} />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Nivel académico */}
                {nivelData.length > 0 && (
                  <div className="rounded-lg p-4" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                    <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: PBI.slate }}>Estudiantes por Nivel Académico (n={nivelData.length} niveles)</h3>
                    <ResponsiveContainer width="100%" height={240}>
                      <BarChart data={nivelData} margin={{ top: 20, right: 20, bottom: 5, left: 0 }}>
                        <CartesianGrid vertical={false} stroke="#f1f5f9" />
                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: PBI.slate }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 11, fill: PBI.slate }} axisLine={false} tickLine={false} />
                        <Tooltip contentStyle={pbiTooltipStyle} formatter={(v) => {
                          const total = nivelData.reduce((s, d) => s + d.value, 0);
                          const pct = total > 0 ? ((v / total) * 100).toFixed(1) : 0;
                          return [`${v} estudiantes (${pct}%)`, ""];
                        }} />
                        <Bar dataKey="value" name="Estudiantes" fill={PBI.blue} radius={[6, 6, 0, 0]}>
                          <LabelList dataKey="value" position="top" style={{ fontSize: 10, fill: PBI.navy, fontWeight: 600 }} />
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Tipo de asignatura */}
                {tipoAsigData.length > 0 && (
                  <DonutSection title="Matrículas por Tipo de Asignatura" data={tipoAsigData} colors={CHART_COLORS} total={g.total_matriculas || 0} />
                )}
              </div>

              {/* Estado matrícula */}
              {g.por_estado_matricula && Object.keys(g.por_estado_matricula).length > 0 && (
                <div className="rounded-lg p-4" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                  <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: PBI.slate }}>Estado de Matrícula</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {Object.entries(g.por_estado_matricula).sort((a,b) => b[1]-a[1]).map(([est, cnt]) => (
                      <div key={est} className="flex justify-between text-sm rounded-lg px-3 py-2" style={{ background: "#f8fafc" }}>
                        <span className="truncate" style={{ color: PBI.slate }} title={est}>{est}</span>
                        <span className="font-bold ml-2" style={{ color: PBI.navy }}>{cnt}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Pago matrícula */}
              {g.matriculas_pagadas && (g.matriculas_pagadas.SI > 0 || g.matriculas_pagadas.NO > 0) && (
                <div className="rounded-lg p-4" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                  <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: PBI.slate }}>Estado de Pago de Matrícula</h3>
                  <div className="flex gap-4">
                    <div className="flex-1 text-center rounded-lg py-3" style={{ background: `${PBI.teal}10`, borderTop: `3px solid ${PBI.teal}` }}>
                      <div className="text-2xl font-bold" style={{ color: PBI.navy }}>{g.matriculas_pagadas.SI?.toLocaleString()}</div>
                      <div className="text-xs uppercase font-medium" style={{ color: PBI.teal }}>Pagadas</div>
                    </div>
                    <div className="flex-1 text-center rounded-lg py-3" style={{ background: `${PBI.coral}10`, borderTop: `3px solid ${PBI.coral}` }}>
                      <div className="text-2xl font-bold" style={{ color: PBI.navy }}>{g.matriculas_pagadas.NO?.toLocaleString()}</div>
                      <div className="text-xs uppercase font-medium" style={{ color: PBI.coral }}>No Pagadas</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ═══ TAB: DEMOGRÁFICO ═══ */}
          {activeTab === "demografico" && (
            <div className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <DonutSection title="Género" data={genderData} colors={genderColors} total={g.total_estudiantes} />
                <DonutSection title="Autoidentificación Étnica" data={etniaData} colors={CHART_COLORS} total={g.total_estudiantes} />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <HBarChart title="Estudiantes por Ciudad" data={ciudadData} color="#14b8a6" maxItems={12} />
                {sedeData.length > 1 && (
                  <HBarChart title="Estudiantes por Sede / Centro de Apoyo" data={sedeData} color="#8b5cf6" maxItems={10} />
                )}
              </div>
            </div>
          )}

          {/* ═══ TAB: POR CARRERA ═══ */}
          {activeTab === "carreras" && (
            <div className="space-y-5">
              {/* Summary hybrid treemap */}
              {carreraBarData.length > 0 && (
                <HybridTreemapChart
                  title="Distribución por Carrera"
                  data={carreraBarData.map(d => ({ name: d.full || d.name, value: d.value }))}
                  total={carreraTreemapTotal}
                  topN={12}
                  onItemClick={(name) => setExpandedCarrera(expandedCarrera === name ? null : name)}
                />
              )}

              {/* Docentes por carrera */}
              {porCarrera.some(c => c.total_docentes > 0) && (
                <HBarChart
                  title="Docentes por Carrera"
                  data={porCarrera.filter(c => c.total_docentes > 0).sort((a,b) => b.total_docentes - a.total_docentes).map(c => ({
                    name: c.carrera?.length > 45 ? c.carrera.slice(0, 43) + "…" : c.carrera,
                    value: c.total_docentes,
                    full: c.carrera
                  }))}
                  color="#3b82f6"
                />
              )}

              {/* Expandable carrera cards */}
              <div>
                <h3 className="text-sm font-bold mb-3" style={{ color: PBI.navy }}>Detalle por Carrera</h3>
                <div className="space-y-2">
                  {[...porCarrera].sort((a, b) => (a.carrera || "").localeCompare(b.carrera || "", "es")).map(c => (
                    <div key={c.carrera} className="rounded-lg overflow-hidden" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                      <button onClick={() => setExpandedCarrera(expandedCarrera === c.carrera ? null : c.carrera)}
                        className="w-full px-5 py-3 flex items-center justify-between hover:bg-blue-50/30 transition-colors">
                        <div className="flex items-center gap-4">
                          <span className="text-xs" style={{ color: PBI.blue }}>{expandedCarrera === c.carrera ? "▼" : "▶"}</span>
                          <h4 className="text-sm font-bold" style={{ color: PBI.navy }}>{c.carrera}</h4>
                          <div className="flex gap-3 text-xs" style={{ color: PBI.slate }}>
                            <span><strong style={{ color: PBI.blue }}>{c.total_estudiantes}</strong> est.</span>
                            <span><strong style={{ color: PBI.teal }}>{c.total_docentes}</strong> doc.</span>
                            <span>Prom: <strong style={{ color: PBI.navy }}>{c.promedio_calificaciones ?? "—"}</strong></span>
                            <span><strong style={{ color: PBI.coral }}>{c.por_riesgo?.Alto || 0}</strong> alto riesgo</span>
                          </div>
                        </div>
                      </button>
                      {expandedCarrera === c.carrera && (() => {
                        const cInterv = c.intervenciones || {};
                        const cGenero = c.por_genero ? Object.entries(c.por_genero).filter(([k]) => k !== "Sin dato") : [];
                        const cEtnia = c.por_etnia ? Object.entries(c.por_etnia).filter(([k]) => k !== "Sin dato").slice(0, 5) : [];
                        const cSede = c.por_sede ? Object.entries(c.por_sede).filter(([k]) => k !== "Sin dato").slice(0, 5) : [];
                        const cEstado = c.por_estado_matricula ? Object.entries(c.por_estado_matricula) : [];
                        return (
                        <div className="px-5 py-4" style={{ borderTop: `1px solid ${PBI.border}`, background: PBI.bg }}>
                          {/* KPI strip */}
                          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 mb-4">
                            {[
                              { v: c.total_estudiantes, l: "Estudiantes", c: PBI.blue },
                              { v: c.promedio_calificaciones ?? "—", l: "Promedio", c: PBI.teal },
                              { v: c.promedio_edad ?? "—", l: "Edad prom.", c: PBI.slate },
                              { v: c.promedio_compromiso ? `${(c.promedio_compromiso * 100).toFixed(0)}%` : "—", l: "Compromiso", c: PBI.purple },
                              { v: c.total_docentes, l: "Docentes", c: PBI.gold },
                              { v: c.condicionados ?? 0, l: "Condicionados", c: PBI.coral },
                            ].map(({ v, l, c: accent }) => (
                              <div key={l} className="text-center rounded-lg py-2" style={{ borderTop: `3px solid ${accent}`, background: PBI.card }}>
                                <div className="text-2xl font-bold" style={{ color: PBI.navy }}>{v}</div>
                                <div className="text-[10px] uppercase" style={{ color: PBI.slate }}>{l}</div>
                              </div>
                            ))}
                          </div>

                          {/* Row 1: Riesgo + Académico + Género */}
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                            <div className="rounded-lg p-3 space-y-1.5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                              <div className="text-[10px] font-semibold uppercase" style={{ color: PBI.slate }}>Riesgo</div>
                              <MiniBar label="Alto" value={c.por_riesgo?.Alto || 0} total={c.total_estudiantes} color={PBI.coral} />
                              <MiniBar label="Medio" value={c.por_riesgo?.Medio || 0} total={c.total_estudiantes} color={PBI.gold} />
                              <MiniBar label="Bajo" value={c.por_riesgo?.Bajo || 0} total={c.total_estudiantes} color={PBI.teal} />
                            </div>
                            <div className="rounded-lg p-3 space-y-1.5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                              <div className="text-[10px] font-semibold uppercase" style={{ color: PBI.slate }}>Académico</div>
                              <div className="flex justify-between text-xs"><span style={{ color: PBI.slate }}>Reprobados</span><span className="font-bold" style={{ color: PBI.coral }}>{c.reprobados ?? 0}</span></div>
                              <div className="flex justify-between text-xs"><span style={{ color: PBI.slate }}>Repitentes</span><span className="font-bold" style={{ color: PBI.gold }}>{c.repitentes ?? 0}</span></div>
                              <div className="flex justify-between text-xs"><span style={{ color: PBI.slate }}>Condicionados (3ra mat.)</span><span className="font-bold" style={{ color: PBI.purple }}>{c.condicionados ?? 0}</span></div>
                              <div className="flex justify-between text-xs"><span style={{ color: PBI.slate }}>Prob. deserción alta</span><span className="font-bold" style={{ color: PBI.coral }}>{c.desertores_prob ?? 0}</span></div>
                              <div className="flex justify-between text-xs"><span style={{ color: PBI.slate }}>Con calificaciones</span><span className="font-bold" style={{ color: PBI.blue }}>{c.con_calificaciones ?? 0}</span></div>
                            </div>
                            <div className="rounded-lg p-3 space-y-1.5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                              <div className="text-[10px] font-semibold uppercase" style={{ color: PBI.slate }}>Género</div>
                              {cGenero.length > 0 ? cGenero.map(([g, cnt]) => (
                                <MiniBar key={g} label={g} value={cnt} total={c.total_estudiantes} color={GENDER_COLORS[g] || PBI.slate} />
                              )) : <span className="text-xs" style={{ color: PBI.slate }}>Sin datos</span>}
                            </div>
                          </div>

                          {/* Separator */}
                          <div className="flex items-center gap-3 my-1">
                            <div className="flex-1 h-px" style={{ background: PBI.border }} />
                            <span className="text-[9px] uppercase tracking-widest" style={{ color: PBI.slate }}>Demografía</span>
                            <div className="flex-1 h-px" style={{ background: PBI.border }} />
                          </div>

                          {/* Row 2: Ciudades + Etnia + Sede */}
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                            <div className="rounded-lg p-3 space-y-1.5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                              <div className="text-[10px] font-semibold uppercase" style={{ color: PBI.slate }}>Ciudades top</div>
                              {c.por_ciudad && Object.entries(c.por_ciudad).slice(0, 5).map(([city, cnt]) => (
                                <MiniBar key={city} label={city} value={cnt} total={c.total_estudiantes} color={PBI.teal} />
                              ))}
                            </div>
                            <div className="rounded-lg p-3 space-y-1.5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                              <div className="text-[10px] font-semibold uppercase" style={{ color: PBI.slate }}>Autoidentificación étnica</div>
                              {cEtnia.length > 0 ? cEtnia.map(([e, cnt]) => (
                                <MiniBar key={e} label={e} value={cnt} total={c.total_estudiantes} color={PBI.purple} />
                              )) : <span className="text-xs" style={{ color: PBI.slate }}>Sin datos</span>}
                            </div>
                            <div className="rounded-lg p-3 space-y-1.5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                              <div className="text-[10px] font-semibold uppercase" style={{ color: PBI.slate }}>Sede / Centro de apoyo</div>
                              {cSede.length > 0 ? cSede.map(([s, cnt]) => (
                                <MiniBar key={s} label={s} value={cnt} total={c.total_estudiantes} color={PBI.blue} />
                              )) : <span className="text-xs" style={{ color: PBI.slate }}>Sin datos</span>}
                            </div>
                          </div>

                          {/* Separator */}
                          <div className="flex items-center gap-3 my-1">
                            <div className="flex-1 h-px" style={{ background: PBI.border }} />
                            <span className="text-[9px] uppercase tracking-widest" style={{ color: PBI.slate }}>Matrícula y seguimiento</span>
                            <div className="flex-1 h-px" style={{ background: PBI.border }} />
                          </div>

                          {/* Row 3: Estado matrícula + Intervenciones + Nivel */}
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            {/* Estado de matrícula */}
                            <div className="rounded-lg p-3" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                              <div className="text-[10px] font-semibold uppercase mb-1.5" style={{ color: PBI.slate }}>Estado de matrícula</div>
                              {cEstado.length > 0 ? (
                                <div className="space-y-1">
                                  {cEstado.sort((a,b) => b[1]-a[1]).map(([est, cnt]) => (
                                    <div key={est} className="flex justify-between text-xs">
                                      <span className="truncate" style={{ color: PBI.slate }} title={est}>{est}</span>
                                      <span className="font-bold ml-2" style={{ color: PBI.navy }}>{cnt}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : <span className="text-xs" style={{ color: PBI.slate }}>Sin datos</span>}
                            </div>

                            {/* Intervenciones */}
                            <div className="rounded-lg p-3" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                              <div className="text-[10px] font-semibold uppercase mb-1.5" style={{ color: PBI.slate }}>Intervenciones</div>
                              {cInterv.total > 0 ? (
                                <div className="space-y-1.5">
                                  <div className="flex justify-between text-xs"><span style={{ color: PBI.slate }}>Total</span><span className="font-bold" style={{ color: PBI.blue }}>{cInterv.total}</span></div>
                                  <div className="flex justify-between text-xs"><span style={{ color: PBI.slate }}>Resueltas</span><span className="font-bold" style={{ color: PBI.teal }}>{cInterv.resueltas ?? 0}</span></div>
                                  <div className="flex justify-between text-xs"><span style={{ color: PBI.slate }}>Pendientes</span><span className="font-bold" style={{ color: PBI.gold }}>{cInterv.pendientes ?? 0}</span></div>
                                  {cInterv.total > 0 && (
                                    <div className="flex justify-between text-xs"><span style={{ color: PBI.slate }}>Tasa resolución</span><span className="font-bold" style={{ color: PBI.teal }}>{Math.round((cInterv.resueltas || 0) / cInterv.total * 100)}%</span></div>
                                  )}
                                  {cInterv.por_motivo && Object.keys(cInterv.por_motivo).length > 0 && (
                                    <div className="mt-2 pt-2" style={{ borderTop: `1px solid ${PBI.border}` }}>
                                      <div className="text-[9px] font-semibold uppercase mb-1" style={{ color: PBI.slate }}>Por motivo</div>
                                      {Object.entries(cInterv.por_motivo).sort((a,b) => b[1]-a[1]).slice(0, 3).map(([m, cnt]) => (
                                        <div key={m} className="flex justify-between text-[11px]">
                                          <span className="truncate" style={{ color: PBI.slate }} title={m}>{m}</span>
                                          <span className="font-bold ml-1" style={{ color: PBI.navy }}>{cnt}</span>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ) : <span className="text-xs" style={{ color: PBI.slate }}>Sin intervenciones</span>}
                            </div>

                            {/* Estudiantes por nivel */}
                            <div className="rounded-lg p-3" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                              <div className="text-[10px] font-semibold uppercase mb-1.5" style={{ color: PBI.slate }}>Estudiantes por nivel</div>
                              {c.por_nivel && Object.keys(c.por_nivel).length > 0 ? (
                                <div className="space-y-1.5">
                                  {Object.entries(c.por_nivel).map(([niv, cnt]) => (
                                    <MiniBar key={niv} label={`Nivel ${niv}`} value={cnt} total={c.total_estudiantes} color={PBI.blue} />
                                  ))}
                                </div>
                              ) : <span className="text-xs" style={{ color: PBI.slate }}>Sin datos</span>}
                            </div>
                          </div>
                        </div>
                        );
                      })()}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ═══ TAB: TENDENCIAS ═══ */}
          {activeTab === "tendencias" && (
            <div className="space-y-5">
              <TrendCharts data={comparativa} />
              {(!comparativa || comparativa.length < 2) && (
                <div className="text-center py-12 text-gray-400 text-sm">
                  Se necesitan datos de al menos 2 períodos para mostrar tendencias.
                </div>
              )}
            </div>
          )}

          {/* ═══ TAB: PRÁCTICAS PREPROFESIONALES ═══ */}
          {activeTab === "practicas" && (
            <PracticasTab
              data={practicasData}
              loading={practicasLoading}
              filtros={practicasFiltros}
              setFiltros={setPracticasFiltros}
              expanded={practicasExpanded}
              setExpanded={setPracticasExpanded}
              escuelaAbierta={practicasEscuela}
              setEscuelaAbierta={setPracticasEscuela}
              search={practicasSearch}
              setSearch={setPracticasSearch}
              navigate={navigate}
            />
          )}

          {/* ═══ TAB: EJECUTIVO ═══ */}
          {activeTab === "ejecutivo" && (
            <div className="space-y-5">
              {execLoading ? (
                <div className="flex items-center justify-center py-16 text-gray-400">
                  <svg className="animate-spin h-6 w-6 mr-2" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
                  Cargando indicadores ejecutivos...
                </div>
              ) : !execData ? (
                <div className="text-center py-16">
                  <div className="text-4xl mb-3">{"🛡️"}</div>
                  <p className="text-sm font-medium" style={{ color: PBI.navy }}>Dashboard ejecutivo sin datos</p>
                  <p className="text-xs mt-2 max-w-md mx-auto" style={{ color: PBI.slate }}>
                    Este dashboard requiere que los estudiantes tengan niveles de riesgo calculados e intervenciones registradas.
                    Carga los datos de AVAC y ejecuta el proceso ETL para activar los indicadores ejecutivos.
                  </p>
                </div>
              ) : (
                <>
                  {/* KPI Cards */}
                  <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
                    {[{ t:"Retención estimada", v:`${(execData.kpis.retencion_estimada??0).toFixed(1)}%`, s:"% no riesgo alto", i:"🛡️", c:PBI.green },
                      { t:"Cobertura", v:`${(execData.kpis.cobertura_intervencion??0).toFixed(1)}%`, s:"riesgo alto intervenido", i:"🎯", c:PBI.blue },
                      { t:"Efectividad", v:`${(execData.kpis.efectividad_intervenciones??0).toFixed(1)}%`, s:"intervenciones resueltas", i:"✅", c:PBI.purple },
                      { t:"Compromiso", v:`${((execData.kpis.compromiso_promedio??0)*100).toFixed(0)}%`, s:"promedio institucional", i:"📈", c:PBI.teal },
                      { t:"Riesgo alto", v:(execData.kpis.estudiantes_riesgo_alto??0).toLocaleString("es-EC"), s:"estudiantes", i:"⚠️", c:PBI.coral },
                      { t:"Intervenciones", v:(execData.kpis.intervenciones_activas??0).toLocaleString("es-EC"), s:"activas en curso", i:"🤝", c:PBI.gold },
                    ].map((k,i) => (
                      <div key={i} className="rounded-lg p-4" style={{ background:PBI.card, border:`1px solid ${PBI.border}`, borderTop:`3px solid ${k.c}` }}>
                        <div className="flex items-start justify-between mb-2">
                          <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">{k.t}</span>
                          <span className="text-lg">{k.i}</span>
                        </div>
                        <div className="text-2xl font-bold" style={{color:k.c}}>{k.v}</div>
                        {k.s && <div className="text-[10px] text-gray-400 mt-1">{k.s}</div>}
                      </div>
                    ))}
                  </div>

                  {/* Semáforo por carrera */}
                  {execData.semaforo_carreras?.length > 0 && (
                    <div className="rounded-lg p-5" style={{ background:PBI.card, border:`1px solid ${PBI.border}` }}>
                      <h3 className="text-sm font-semibold mb-4" style={{color:PBI.navy}}>Semáforo por Carrera</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {execData.semaforo_carreras.map(c => {
                          const sColors = { rojo:{bg:"#fef2f2",bd:"#fca5a5",dot:"#ef4444",tx:"#b91c1c",lb:"Crítico"}, amarillo:{bg:"#fffbeb",bd:"#fcd34d",dot:"#f59e0b",tx:"#92400e",lb:"En riesgo"}, verde:{bg:"#f0fdf4",bd:"#86efac",dot:"#22c55e",tx:"#166534",lb:"Estable"} };
                          const sc = sColors[c.semaforo] || sColors.verde;
                          return (
                            <div key={c.carrera} className="rounded-lg p-4" style={{ background:sc.bg, border:`1px solid ${sc.bd}` }}>
                              <div className="flex items-center gap-2 mb-2">
                                <span className="w-3 h-3 rounded-full" style={{background:sc.dot}} />
                                <span className="text-sm font-semibold" style={{color:sc.tx}}>{sc.lb}</span>
                              </div>
                              <div className="text-sm font-medium text-gray-800 mb-2 truncate" title={c.carrera}>{c.carrera}</div>
                              <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
                                <div><span className="font-medium" style={{color:PBI.coral}}>{c.alto}</span> alto</div>
                                <div><span className="font-medium" style={{color:PBI.gold}}>{c.medio}</span> medio</div>
                                <div><span className="font-medium" style={{color:PBI.green}}>{c.bajo}</span> bajo</div>
                              </div>
                              <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
                                <span>Riesgo alto: {(c.tasa_riesgo_alto??0).toFixed(1)}%</span>
                                <span>Compromiso: {((c.compromiso_promedio??0)*100).toFixed(0)}%</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Tendencia multi-período */}
                  {execData.tendencia_periodos?.length >= 2 && (
                    <div className="rounded-lg p-5" style={{ background:PBI.card, border:`1px solid ${PBI.border}` }}>
                      <h3 className="text-sm font-semibold mb-1" style={{color:PBI.navy}}>Tendencia por Período</h3>
                      <div className="flex gap-4 text-xs text-gray-500 mb-3">
                        <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 rounded" style={{background:PBI.coral}} /> % Riesgo alto</span>
                        <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 rounded" style={{background:PBI.blue}} /> Compromiso %</span>
                      </div>
                      <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={execData.tendencia_periodos.map(t => ({ ...t, compromiso_pct: (t.compromiso_promedio*100) }))}>
                          <CartesianGrid strokeDasharray="3 3" stroke={PBI.border} />
                          <XAxis dataKey="periodo" tick={{fontSize:11}} />
                          <YAxis tick={{fontSize:11}} />
                          <Tooltip contentStyle={pbiTooltipStyle} />
                          <Bar dataKey="tasa_riesgo_alto" name="% Riesgo alto" fill={PBI.coral} radius={[4,4,0,0]} />
                          <Bar dataKey="compromiso_pct" name="Compromiso %" fill={PBI.blue} radius={[4,4,0,0]} />
                          <Legend wrapperStyle={{fontSize:11}} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {execData.total_estudiantes === 0 && (
                    <div className="text-center py-16 text-gray-400">
                      <div className="text-4xl mb-3">📭</div>
                      <p className="text-sm">Sin datos ejecutivos para este período</p>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ═══ TAB: EFECTIVIDAD DE INTERVENCIONES ═══ */}
          {activeTab === "efectividad" && (
            <div className="space-y-5">
              {effLoading ? (
                <div className="flex items-center justify-center py-16 text-gray-400">
                  <svg className="animate-spin h-6 w-6 mr-2" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
                  Cargando análisis de efectividad...
                </div>
              ) : !effData || effData.total_analizadas === 0 ? (
                <div className="text-center py-16">
                  <div className="text-4xl mb-3">{"🎯"}</div>
                  <p className="text-sm font-medium" style={{ color: PBI.navy }}>Sin datos de efectividad</p>
                  <p className="text-xs mt-2 max-w-md mx-auto" style={{ color: PBI.slate }}>
                    Este análisis evalúa intervenciones cerradas o resueltas. Se activará cuando existan
                    intervenciones con estado de resolución. Registra y cierra intervenciones desde la ficha de cada estudiante.
                  </p>
                </div>
              ) : (
                <>
                  {/* KPI Cards */}
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <KPICard label="Total analizadas" value={effData.total_analizadas} icon="📋" accent={PBI.navy} />
                    <KPICard label="Exitosas" value={effData.exitosas} sub={`${effData.tasa_exito_global}% de éxito`} icon="✅" accent={PBI.green} />
                    <KPICard label="No exitosas" value={effData.total_analizadas - effData.exitosas} icon="⚠️" accent={PBI.coral} />
                    <KPICard label="Tasa de éxito" value={`${effData.tasa_exito_global}%`} icon="🎯" accent={effData.tasa_exito_global >= 50 ? PBI.green : PBI.coral} />
                  </div>

                  {/* Ranking de medios más efectivos */}
                  {effData.ranking_medios?.length > 0 && (
                    <div className="rounded-lg p-5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                      <h3 className="text-sm font-semibold mb-4" style={{ color: PBI.navy }}>Ranking de Medios de Intervención</h3>
                      <div className="space-y-3">
                        {effData.ranking_medios.map((m, i) => {
                          const barColor = m.tasa_exito >= 70 ? PBI.green : m.tasa_exito >= 40 ? PBI.gold : PBI.coral;
                          return (
                            <div key={m.medio} className="flex items-center gap-3">
                              <span className="w-6 text-center text-sm font-bold" style={{ color: i < 3 ? PBI.blue : PBI.slate }}>#{i + 1}</span>
                              <div className="flex-1">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-sm font-medium" style={{ color: PBI.navy }}>{m.medio}</span>
                                  <span className="text-xs font-semibold" style={{ color: barColor }}>{m.tasa_exito}%</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 rounded-full h-3 overflow-hidden" style={{ background: "#f1f5f9" }}>
                                    <div className="h-full rounded-full transition-all" style={{ width: `${m.tasa_exito}%`, background: barColor }} />
                                  </div>
                                  <span className="text-[10px] whitespace-nowrap" style={{ color: PBI.slate }}>{m.exitosas}/{m.total}</span>
                                </div>
                                {m.delta_compromiso_promedio !== null && (
                                  <span className="text-[10px]" style={{ color: m.delta_compromiso_promedio > 0 ? PBI.green : m.delta_compromiso_promedio < 0 ? PBI.coral : PBI.slate }}>
                                    Δ compromiso: {m.delta_compromiso_promedio > 0 ? "+" : ""}{(m.delta_compromiso_promedio * 100).toFixed(1)}%
                                  </span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Por Motivo y Por Carrera side by side */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    {/* Por Motivo */}
                    {effData.por_motivo?.length > 0 && (
                      <div className="rounded-lg p-5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                        <h3 className="text-sm font-semibold mb-4" style={{ color: PBI.navy }}>Efectividad por Motivo</h3>
                        <ResponsiveContainer width="100%" height={Math.max(200, effData.por_motivo.length * 40)}>
                          <BarChart layout="vertical" data={effData.por_motivo.slice(0, 10).map(m => ({ name: m.motivo?.length > 25 ? m.motivo.slice(0,23) + "..." : m.motivo, tasa: m.tasa_exito, total: m.total, full: m.motivo }))}>
                            <CartesianGrid strokeDasharray="3 3" stroke={PBI.border} />
                            <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                            <YAxis dataKey="name" type="category" width={130} tick={{ fontSize: 11 }} />
                            <Tooltip contentStyle={pbiTooltipStyle} formatter={(v, name, props) => [`${v}% (${props.payload.total} intervenciones)`, "Tasa éxito"]} />
                            <Bar dataKey="tasa" fill={PBI.blue} radius={[0, 4, 4, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}

                    {/* Por Carrera */}
                    {effData.por_carrera?.length > 0 && (
                      <div className="rounded-lg p-5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                        <h3 className="text-sm font-semibold mb-4" style={{ color: PBI.navy }}>Efectividad por Carrera</h3>
                        <ResponsiveContainer width="100%" height={Math.max(200, effData.por_carrera.slice(0, 10).length * 40)}>
                          <BarChart layout="vertical" data={effData.por_carrera.slice(0, 10).map(c => ({ name: c.carrera?.length > 25 ? c.carrera.slice(0,23) + "..." : c.carrera, tasa: c.tasa_exito, total: c.total, full: c.carrera }))}>
                            <CartesianGrid strokeDasharray="3 3" stroke={PBI.border} />
                            <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                            <YAxis dataKey="name" type="category" width={130} tick={{ fontSize: 11 }} />
                            <Tooltip contentStyle={pbiTooltipStyle} formatter={(v, name, props) => [`${v}% (${props.payload.total} intervenciones)`, "Tasa éxito"]} />
                            <Bar dataKey="tasa" fill={PBI.teal} radius={[0, 4, 4, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>

                  {/* Tabla detallada por medio */}
                  {effData.por_medio?.length > 0 && (
                    <div className="rounded-lg p-5" style={{ background: PBI.card, border: `1px solid ${PBI.border}` }}>
                      <h3 className="text-sm font-semibold mb-4" style={{ color: PBI.navy }}>Detalle por Medio de Intervención</h3>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr style={{ background: "#f8fafc" }}>
                              <th className="text-left px-3 py-2 font-semibold text-xs uppercase tracking-wider" style={{ color: PBI.slate }}>Medio</th>
                              <th className="text-center px-3 py-2 font-semibold text-xs uppercase tracking-wider" style={{ color: PBI.slate }}>Total</th>
                              <th className="text-center px-3 py-2 font-semibold text-xs uppercase tracking-wider" style={{ color: PBI.slate }}>Exitosas</th>
                              <th className="text-center px-3 py-2 font-semibold text-xs uppercase tracking-wider" style={{ color: PBI.slate }}>Tasa</th>
                              <th className="text-center px-3 py-2 font-semibold text-xs uppercase tracking-wider" style={{ color: PBI.slate }}>Δ Compromiso</th>
                            </tr>
                          </thead>
                          <tbody>
                            {effData.por_medio.map((m, i) => (
                              <tr key={m.medio} style={{ borderBottom: `1px solid ${PBI.border}`, background: i % 2 === 0 ? "#fff" : "#fafbfc" }}>
                                <td className="px-3 py-2 font-medium" style={{ color: PBI.navy }}>{m.medio}</td>
                                <td className="px-3 py-2 text-center" style={{ color: PBI.slate }}>{m.total}</td>
                                <td className="px-3 py-2 text-center font-semibold" style={{ color: PBI.green }}>{m.exitosas}</td>
                                <td className="px-3 py-2 text-center">
                                  <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold" style={{
                                    background: m.tasa_exito >= 70 ? "#f0fdf4" : m.tasa_exito >= 40 ? "#fffbeb" : "#fef2f2",
                                    color: m.tasa_exito >= 70 ? "#166534" : m.tasa_exito >= 40 ? "#92400e" : "#b91c1c",
                                  }}>{m.tasa_exito}%</span>
                                </td>
                                <td className="px-3 py-2 text-center text-xs font-medium" style={{
                                  color: m.delta_compromiso_promedio > 0 ? PBI.green : m.delta_compromiso_promedio < 0 ? PBI.coral : PBI.slate,
                                }}>
                                  {m.delta_compromiso_promedio !== null ? `${m.delta_compromiso_promedio > 0 ? "+" : ""}${(m.delta_compromiso_promedio * 100).toFixed(1)}%` : "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}

      {/* ── Empty state ─── */}
      {!loading && !error && !g.total_estudiantes && data?.tiene_datos_periodo !== false && (
        <div className="text-center py-16 text-gray-300">
          <div className="text-4xl mb-3">{"📊"}</div>
          <div className="text-sm">No hay datos disponibles</div>
          <p className="text-xs text-gray-400 mt-1">Ejecuta el proceso ETL para cargar datos de estudiantes</p>
        </div>
      )}

      {/* ── Student List Modal ─── */}
      {StudentListModalEl}
    </div>
  );
}
