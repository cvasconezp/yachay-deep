/**
 * DashboardCharts — Visualizaciones densas para el dashboard (Épica 2.4).
 *
 * 3 gráficos SVG puro (sin dependencias externas):
 * 1. Donut de distribución por nivel de riesgo
 * 2. Barras horizontales por carrera (top 10)
 * 3. Indicadores clave con mini-barras
 */
import { useMemo } from "react";

const RISK_COLORS = {
  Alto:  { fill: "#ef4444", bg: "bg-red-100",    text: "text-red-700" },
  Medio: { fill: "#f59e0b", bg: "bg-amber-100",  text: "text-amber-700" },
  Bajo:  { fill: "#22c55e", bg: "bg-green-100",  text: "text-green-700" },
};

// ── Donut Chart SVG ──────────────────────────────────────────────────

function DonutChart({ data, total }) {
  const segments = useMemo(() => {
    if (!data?.length || total === 0) return [];
    let acc = 0;
    return data.map(d => {
      const pct = d.total / total;
      const start = acc;
      acc += pct;
      return { ...d, pct, start, end: acc };
    });
  }, [data, total]);

  if (segments.length === 0) {
    return <div className="text-center text-xs text-gray-400 py-4">Sin datos</div>;
  }

  const cx = 60, cy = 60, r = 48, r2 = 30;

  // Arc path helper
  const arc = (startAngle, endAngle, radius) => {
    const s = startAngle * 2 * Math.PI - Math.PI / 2;
    const e = endAngle * 2 * Math.PI - Math.PI / 2;
    const largeArc = endAngle - startAngle > 0.5 ? 1 : 0;
    const x1 = cx + radius * Math.cos(s);
    const y1 = cy + radius * Math.sin(s);
    const x2 = cx + radius * Math.cos(e);
    const y2 = cy + radius * Math.sin(e);
    return { x1, y1, x2, y2, largeArc };
  };

  return (
    <div className="flex items-center gap-4">
      <svg width={120} height={120} viewBox="0 0 120 120">
        {segments.map((seg, i) => {
          if (seg.pct < 0.001) return null;
          // For near-100%, use a full circle
          const adjustedEnd = seg.pct > 0.999 ? seg.start + 0.999 : seg.end;
          const outer = arc(seg.start, adjustedEnd, r);
          const inner = arc(seg.start, adjustedEnd, r2);
          const color = RISK_COLORS[seg.nivel]?.fill || "#9ca3af";
          const d = [
            `M${outer.x1},${outer.y1}`,
            `A${r},${r},0,${outer.largeArc},1,${outer.x2},${outer.y2}`,
            `L${inner.x2},${inner.y2}`,
            `A${r2},${r2},0,${outer.largeArc},0,${inner.x1},${inner.y1}`,
            "Z",
          ].join(" ");
          return <path key={i} d={d} fill={color} opacity="0.85" />;
        })}
        <text x={cx} y={cy - 4} textAnchor="middle" fontSize="18" fontWeight="bold" fill="#1f2937">{total}</text>
        <text x={cx} y={cy + 10} textAnchor="middle" fontSize="8" fill="#9ca3af">estudiantes</text>
      </svg>
      <div className="flex flex-col gap-1.5">
        {segments.map((seg, i) => {
          const style = RISK_COLORS[seg.nivel] || {};
          return (
            <div key={i} className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: style.fill || "#9ca3af" }} />
              <span className="text-xs text-gray-700 font-medium">{seg.nivel || "Sin evaluar"}</span>
              <span className="text-xs text-gray-500">{seg.total}</span>
              <span className="text-[10px] text-gray-400">({(seg.pct * 100).toFixed(1)}%)</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Bar Chart por Carrera ────────────────────────────────────────────

function CarreraBarChart({ data }) {
  if (!data?.length) {
    return <div className="text-center text-xs text-gray-400 py-4">Sin datos por carrera</div>;
  }

  const top = data.slice(0, 10);
  const maxVal = Math.max(...top.map(d => d.total), 1);

  return (
    <div className="space-y-1.5">
      {top.map((item, i) => {
        const pct = (item.total / maxVal) * 100;
        const shortName = item.carrera?.length > 35
          ? item.carrera.slice(0, 33) + "…"
          : item.carrera;
        return (
          <div key={i} className="flex items-center gap-2">
            <span className="text-[10px] text-gray-600 w-36 truncate text-right flex-shrink-0" title={item.carrera}>
              {shortName}
            </span>
            <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded transition-all duration-500"
                style={{ width: `${pct}%`, opacity: 0.7 + (0.3 * (1 - i / top.length)) }}
              />
            </div>
            <span className="text-[10px] text-gray-500 w-6 text-right font-mono">{item.total}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── KPI Mini Bars ────────────────────────────────────────────────────

function KpiBar({ label, value, maxValue, color = "bg-blue-500", suffix = "" }) {
  const pct = maxValue > 0 ? Math.min((value / maxValue) * 100, 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-gray-500 w-24 text-right flex-shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-700 font-semibold w-10 text-right">{value}{suffix}</span>
    </div>
  );
}

// ── Componente Principal ────────────────────────────────────────────

export default function DashboardCharts({ stats, students }) {
  if (!stats || stats.tiene_datos_periodo === false) return null;

  const riesgoData = stats.por_nivel_riesgo || [];
  const carreraData = stats.por_carrera || [];
  const total = stats.total_estudiantes || 0;

  // Calcular KPIs de los estudiantes cargados
  const kpis = useMemo(() => {
    if (!students?.length) return null;
    const withTareas = students.filter(s => s.porcentaje_tareas != null);
    const withAcceso = students.filter(s => s.dias_sin_acceso != null);
    const inactivos14 = withAcceso.filter(s => s.dias_sin_acceso > 14).length;
    const tareasBajas = withTareas.filter(s => s.porcentaje_tareas < 50).length;
    const promedioTareas = withTareas.length > 0
      ? withTareas.reduce((s, x) => s + x.porcentaje_tareas, 0) / withTareas.length
      : 0;
    const promedioAcceso = withAcceso.length > 0
      ? withAcceso.reduce((s, x) => s + x.dias_sin_acceso, 0) / withAcceso.length
      : 0;
    return { inactivos14, tareasBajas, promedioTareas, promedioAcceso, total: students.length };
  }, [students]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
      {/* Donut: Distribución de Riesgo */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Distribución de Riesgo</h3>
        <DonutChart data={riesgoData} total={total} />
      </div>

      {/* Barras: Estudiantes por Carrera */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Estudiantes por Carrera {carreraData.length > 10 && <span className="text-gray-400 font-normal">(top 10)</span>}
        </h3>
        <CarreraBarChart data={carreraData} />
      </div>

      {/* KPIs con mini-barras */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Indicadores Clave</h3>
        {kpis ? (
          <div className="space-y-3">
            <KpiBar
              label="Inactivos >14d"
              value={kpis.inactivos14}
              maxValue={kpis.total}
              color="bg-red-500"
            />
            <KpiBar
              label="Tareas <50%"
              value={kpis.tareasBajas}
              maxValue={kpis.total}
              color="bg-orange-500"
            />
            <KpiBar
              label="Prom. tareas"
              value={Math.round(kpis.promedioTareas)}
              maxValue={100}
              color="bg-blue-500"
              suffix="%"
            />
            <KpiBar
              label="Prom. inactividad"
              value={Math.round(kpis.promedioAcceso)}
              maxValue={60}
              color="bg-purple-500"
              suffix="d"
            />
            <div className="border-t border-gray-100 pt-2 mt-2 grid grid-cols-2 gap-2 text-center">
              <div>
                <div className="text-lg font-bold text-blue-700">{stats.total_aulas_virtuales || 0}</div>
                <div className="text-[9px] text-gray-400 uppercase">Aulas AVAC</div>
              </div>
              <div>
                <div className="text-lg font-bold text-green-700">{stats.estudiantes_intervenidos || 0}</div>
                <div className="text-[9px] text-gray-400 uppercase">Intervenidos</div>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-xs text-gray-400 text-center py-4">Cargando indicadores...</div>
        )}
      </div>
    </div>
  );
}
