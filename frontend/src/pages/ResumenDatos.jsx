import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import { useStudentListModal } from "../components/StudentListModal";
import { PeriodSelector } from "../components/PeriodSelector";
import { TrendCharts } from "../components/TrendCharts";
import {
  ResponsiveContainer,
  PieChart, Pie, Cell,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";

/* ── Paleta de colores ─────────────────── */
const RISK_COLORS = { Alto: "#ef4444", Medio: "#f59e0b", Bajo: "#22c55e" };
const CHART_COLORS = [
  "#3b82f6", "#8b5cf6", "#06b6d4", "#f97316", "#ec4899",
  "#14b8a6", "#6366f1", "#84cc16", "#f43f5e", "#0ea5e9",
];
const GENDER_COLORS = { Masculino: "#3b82f6", Femenino: "#ec4899", "Sin dato": "#94a3b8" };

/* ── KPI Card ──────────────────────────── */
function KPICard({ label, value, sub, icon, color = "text-gray-900", bg = "bg-white", onClick }) {
  const clickable = !!onClick;
  return (
    <div
      className={`${bg} rounded-xl border border-gray-200 p-4 shadow-sm flex flex-col ${clickable ? "cursor-pointer hover:ring-2 hover:ring-blue-300 hover:shadow-md transition-all" : ""}`}
      onClick={onClick}
      title={clickable ? "Clic para ver listado" : undefined}
    >
      <div className="flex items-center gap-2 mb-1">
        {icon && <span className="text-lg">{icon}</span>}
        <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{label}</span>
        {clickable && <span className="text-[10px] text-blue-400 ml-auto">▸ ver lista</span>}
      </div>
      <div className={`text-2xl font-bold ${color} leading-tight`}>{value ?? "—"}</div>
      {sub && <span className="text-[11px] text-gray-400 mt-0.5">{sub}</span>}
    </div>
  );
}

/* ── Mini horizontal bar ───────────────── */
function MiniBar({ label, value, total, color = "bg-blue-500" }) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 text-gray-500 truncate" title={label}>{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2.5 overflow-hidden">
        <div className={`${color} h-full rounded-full transition-all`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="w-12 text-right font-medium text-gray-700">{value}</span>
    </div>
  );
}

/* ── Donut chart section ───────────────── */
function DonutSection({ title, data, colors, total, onItemClick }) {
  if (!data || data.length === 0) return null;
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">{title}</h3>
      <div className="flex items-center gap-4">
        <ResponsiveContainer width={120} height={120}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={30} outerRadius={50} paddingAngle={2}>
              {data.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
            </Pie>
            <Tooltip formatter={(v) => v.toLocaleString()} />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex-1 space-y-1.5">
          {data.map((d, i) => {
            const clickHandler = onItemClick ? () => onItemClick(d.name) : undefined;
            return (
              <div key={d.name}
                className={`flex items-center gap-2 text-xs ${clickHandler ? "cursor-pointer hover:bg-gray-50 rounded-md px-1 -mx-1 py-0.5 transition-colors" : ""}`}
                onClick={clickHandler} title={clickHandler ? "Clic para ver listado" : undefined}>
                <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: colors[i % colors.length] }} />
                <span className="text-gray-600 truncate flex-1">{d.name}</span>
                <span className="font-semibold text-gray-800">{d.value.toLocaleString()}</span>
                <span className="text-gray-400 w-10 text-right">{total > 0 ? `${Math.round(d.value / total * 100)}%` : ""}</span>
                {clickHandler && <span className="text-[10px] text-blue-400">▸</span>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ── Horizontal bar chart (top N) ──────── */
function HBarChart({ title, data, color = "#3b82f6", maxItems = 10 }) {
  if (!data || data.length === 0) return null;
  const sliced = data.slice(0, maxItems);
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">{title}</h3>
      <ResponsiveContainer width="100%" height={Math.max(sliced.length * 32, 120)}>
        <BarChart data={sliced} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 100 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={95} />
          <Tooltip />
          <Bar dataKey="value" fill={color} radius={[0, 4, 4, 0]} barSize={18} />
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

/* ══════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════ */
export default function ResumenDatos() {
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
    .slice(0, 15)
    .map(c => ({ name: c.carrera?.length > 30 ? c.carrera.slice(0, 28) + "..." : c.carrera, value: c.total_estudiantes, full: c.carrera }));

  const TABS = [
    { key: "general", label: "Vista General" },
    { key: "academico", label: "Académico" },
    { key: "demografico", label: "Demográfico" },
    { key: "carreras", label: "Por Carrera" },
    { key: "tendencias", label: "Tendencias" },
  ];

  return (
    <div>
      {/* ── Header ─── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Resumen de Datos</h1>
          <p className="text-gray-400 text-sm">Panel analítico integral — estudiantes, carreras y métricas institucionales</p>
        </div>
        <button onClick={() => setExportOpen(!exportOpen)}
          className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm">
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
          {/* ── KPI Cards ─── */}
          <div className="space-y-4 mb-6">
            {/* Fila 1: Población y estructura */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              <KPICard icon="🎓" label="Estudiantes" value={g.total_estudiantes?.toLocaleString()} color="text-blue-700" bg="bg-blue-50/60" />
              <KPICard icon="👨‍🏫" label="Docentes" value={g.total_docentes_enrollment || g.total_docentes || "—"} color="text-emerald-700" bg="bg-emerald-50/60" />
              <KPICard icon="📚" label="Carreras" value={g.total_carreras} color="text-purple-700" bg="bg-purple-50/60" />
              <KPICard icon="📋" label="Matrículas" value={g.total_matriculas?.toLocaleString()} color="text-teal-700" bg="bg-teal-50/60" sub="registros est × materia" />
              <KPICard icon="📊" label="Prom. Calificaciones" value={g.promedio_calificaciones ?? "—"} color="text-gray-700" bg="bg-gray-50/60" sub={g.promedio_calificaciones ? "sobre 100" : "Aún sin AVAC"} />
            </div>

            {/* Fila 2: Oferta académica */}
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2 ml-1">Oferta académica</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <KPICard icon="📖" label="Asignaturas" value={g.total_asignaturas} color="text-cyan-700" bg="bg-cyan-50/60" sub="materias únicas" />
                <KPICard icon="📑" label="Secciones" value={g.total_secciones ?? "—"} color="text-orange-700" bg="bg-orange-50/60" sub="materia × docente" />
                <KPICard icon="🖥️" label="Aulas Virtuales" value={g.total_aulas_virtuales ?? "—"} color="text-indigo-700" bg="bg-indigo-50/60" sub="cursos en AVAC" />
              </div>
            </div>
          </div>

          {/* ── Tab Navigation ─── */}
          <div className="flex gap-1 mb-5 bg-gray-100 rounded-lg p-1 overflow-x-auto">
            {TABS.map(t => (
              <button key={t.key} onClick={() => setActiveTab(t.key)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${activeTab === t.key ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
                {t.label}
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
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                  <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Indicadores Clave</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-500">Reprobados</span>
                      <span className="text-lg font-bold text-red-600">{g.reprobados ?? 0}</span>
                    </div>
                    <div className="flex justify-between items-center cursor-pointer hover:bg-orange-50 rounded-lg px-2 py-1 -mx-2 transition-colors"
                         onClick={() => openStudentList("repitentes")} title="Clic para ver listado">
                      <span className="text-sm text-gray-500">Repitentes</span>
                      <span className="text-lg font-bold text-orange-600 flex items-center gap-1">{g.repitentes ?? 0} <span className="text-[10px] text-orange-300">▸</span></span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-500">Prob. deserción alta</span>
                      <span className="text-lg font-bold text-red-700">{g.desertores_prob ?? 0}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-500">Compromiso promedio</span>
                      <span className="text-lg font-bold text-teal-600">{g.promedio_compromiso ? `${(g.promedio_compromiso * 100).toFixed(0)}%` : "—"}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-500">Edad promedio</span>
                      <span className="text-lg font-bold text-gray-700">{g.promedio_edad ? `${g.promedio_edad} años` : "—"}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Estudiantes por carrera — bar chart */}
              {carreraBarData.length > 0 && (
                <HBarChart title="Estudiantes por Carrera" data={carreraBarData} color="#6366f1" maxItems={15} />
              )}

              {/* Intervenciones summary */}
              {g.intervenciones && g.intervenciones.total > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                  <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-gray-800">Intervenciones</h3>
                      <p className="text-xs text-gray-400 mt-0.5">Seguimiento y resolución de casos</p>
                    </div>
                  </div>
                  <div className="p-5">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                      <div className="text-center bg-blue-50 rounded-lg px-3 py-2.5">
                        <div className="text-xl font-bold text-blue-700">{g.intervenciones.total}</div>
                        <div className="text-[10px] text-blue-500 uppercase font-medium">Total</div>
                      </div>
                      <div className="text-center bg-green-50 rounded-lg px-3 py-2.5">
                        <div className="text-xl font-bold text-green-700">{g.intervenciones.resueltas}</div>
                        <div className="text-[10px] text-green-500 uppercase font-medium">Resueltas</div>
                      </div>
                      <div className="text-center bg-orange-50 rounded-lg px-3 py-2.5">
                        <div className="text-xl font-bold text-orange-700">{g.intervenciones.pendientes_seguimiento}</div>
                        <div className="text-[10px] text-orange-500 uppercase font-medium">Pendientes</div>
                      </div>
                      <div className="text-center bg-gray-50 rounded-lg px-3 py-2.5">
                        <div className="text-xl font-bold text-gray-700">
                          {g.intervenciones.total > 0 ? `${Math.round((g.intervenciones.resueltas / g.intervenciones.total) * 100)}%` : "—"}
                        </div>
                        <div className="text-[10px] text-gray-500 uppercase font-medium">Resolución</div>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <div className="text-[10px] font-semibold text-gray-500 uppercase mb-2">Por motivo</div>
                        <div className="space-y-1.5">
                          {Object.entries(g.intervenciones.por_motivo || {}).sort((a,b) => b[1]-a[1]).map(([m, c]) => (
                            <MiniBar key={m} label={m} value={c} total={g.intervenciones.total} color="bg-blue-400" />
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-semibold text-gray-500 uppercase mb-2">Por resultado</div>
                        <div className="space-y-1.5">
                          {Object.entries(g.intervenciones.por_resultado || {}).sort((a,b) => b[1]-a[1]).map(([r, c]) => (
                            <MiniBar key={r} label={r} value={c} total={g.intervenciones.total} color="bg-purple-400" />
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
                <KPICard icon="📝" label="Matrículas con Repitencia" value={g.matriculas_con_repitencia ?? 0} color="text-orange-700" />
                <KPICard icon="🎯" label="Con Riesgo Calculado" value={g.con_riesgo_calculado ?? 0} color="text-red-600" />
                <KPICard icon="📈" label="Con Calificaciones" value={g.con_calificaciones ?? 0} color="text-blue-600" />
                <KPICard icon="👨‍🏫" label="Docentes (calificaciones)" value={g.total_docentes ?? 0} color="text-gray-700" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Nivel académico */}
                {nivelData.length > 0 && (
                  <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                    <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Estudiantes por Nivel Académico</h3>
                    <ResponsiveContainer width="100%" height={240}>
                      <BarChart data={nivelData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Bar dataKey="value" name="Estudiantes" fill="#6366f1" radius={[4, 4, 0, 0]} />
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
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                  <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Estado de Matrícula</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {Object.entries(g.por_estado_matricula).sort((a,b) => b[1]-a[1]).map(([est, cnt]) => (
                      <div key={est} className="flex justify-between text-sm bg-gray-50 rounded-lg px-3 py-2">
                        <span className="text-gray-600 truncate" title={est}>{est}</span>
                        <span className="font-bold text-blue-700 ml-2">{cnt}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Pago matrícula */}
              {g.matriculas_pagadas && (g.matriculas_pagadas.SI > 0 || g.matriculas_pagadas.NO > 0) && (
                <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                  <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Estado de Pago de Matrícula</h3>
                  <div className="flex gap-4">
                    <div className="flex-1 text-center bg-green-50 rounded-lg py-3">
                      <div className="text-2xl font-bold text-green-700">{g.matriculas_pagadas.SI?.toLocaleString()}</div>
                      <div className="text-xs text-green-500 uppercase font-medium">Pagadas</div>
                    </div>
                    <div className="flex-1 text-center bg-red-50 rounded-lg py-3">
                      <div className="text-2xl font-bold text-red-700">{g.matriculas_pagadas.NO?.toLocaleString()}</div>
                      <div className="text-xs text-red-500 uppercase font-medium">No Pagadas</div>
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
              {/* Summary bar chart */}
              {carreraBarData.length > 0 && (
                <HBarChart title={`Estudiantes por Carrera (${porCarrera.length} carreras)`} data={carreraBarData} color="#6366f1" maxItems={20} />
              )}

              {/* Docentes por carrera */}
              {porCarrera.some(c => c.total_docentes > 0) && (
                <HBarChart
                  title="Docentes por Carrera"
                  data={porCarrera.filter(c => c.total_docentes > 0).sort((a,b) => b.total_docentes - a.total_docentes).map(c => ({
                    name: c.carrera?.length > 30 ? c.carrera.slice(0, 28) + "..." : c.carrera,
                    value: c.total_docentes
                  }))}
                  color="#3b82f6"
                />
              )}

              {/* Expandable carrera cards */}
              <div>
                <h3 className="text-sm font-bold text-gray-700 mb-3">Detalle por Carrera</h3>
                <div className="space-y-2">
                  {porCarrera.map(c => (
                    <div key={c.carrera} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                      <button onClick={() => setExpandedCarrera(expandedCarrera === c.carrera ? null : c.carrera)}
                        className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors">
                        <div className="flex items-center gap-4">
                          <h4 className="text-sm font-bold text-gray-800">{c.carrera}</h4>
                          <div className="flex gap-3 text-xs text-gray-500">
                            <span><strong className="text-blue-700">{c.total_estudiantes}</strong> est.</span>
                            <span><strong className="text-blue-600">{c.total_docentes}</strong> doc.</span>
                            <span>Prom: <strong>{c.promedio_calificaciones ?? "—"}</strong></span>
                            <span className="text-red-600"><strong>{c.por_riesgo?.Alto || 0}</strong> alto riesgo</span>
                          </div>
                        </div>
                        <span className="text-gray-400 text-lg">{expandedCarrera === c.carrera ? "−" : "+"}</span>
                      </button>
                      {expandedCarrera === c.carrera && (
                        <div className="border-t border-gray-100 px-5 py-4 bg-gray-50/50">
                          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                            <div className="text-center">
                              <div className="text-2xl font-bold text-blue-700">{c.total_estudiantes}</div>
                              <div className="text-[10px] text-gray-500 uppercase">Estudiantes</div>
                            </div>
                            <div className="text-center">
                              <div className="text-2xl font-bold text-gray-700">{c.promedio_calificaciones ?? "—"}</div>
                              <div className="text-[10px] text-gray-500 uppercase">Promedio</div>
                            </div>
                            <div className="text-center">
                              <div className="text-2xl font-bold text-gray-600">{c.promedio_edad ?? "—"}</div>
                              <div className="text-[10px] text-gray-500 uppercase">Edad prom.</div>
                            </div>
                            <div className="text-center">
                              <div className="text-2xl font-bold text-teal-600">{c.promedio_compromiso ? `${(c.promedio_compromiso * 100).toFixed(0)}%` : "—"}</div>
                              <div className="text-[10px] text-gray-500 uppercase">Compromiso</div>
                            </div>
                            <div className="text-center">
                              <div className="text-2xl font-bold text-blue-600">{c.total_docentes}</div>
                              <div className="text-[10px] text-gray-500 uppercase">Docentes</div>
                            </div>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div className="space-y-1.5">
                              <div className="text-[10px] font-semibold text-gray-500 uppercase">Riesgo</div>
                              <MiniBar label="Alto" value={c.por_riesgo?.Alto || 0} total={c.total_estudiantes} color="bg-red-500" />
                              <MiniBar label="Medio" value={c.por_riesgo?.Medio || 0} total={c.total_estudiantes} color="bg-yellow-500" />
                              <MiniBar label="Bajo" value={c.por_riesgo?.Bajo || 0} total={c.total_estudiantes} color="bg-green-500" />
                            </div>
                            <div className="space-y-1.5">
                              <div className="text-[10px] font-semibold text-gray-500 uppercase">Académico</div>
                              <div className="flex justify-between text-xs"><span className="text-gray-500">Reprobados</span><span className="font-bold text-red-600">{c.reprobados ?? 0}</span></div>
                              <div className="flex justify-between text-xs"><span className="text-gray-500">Repitentes</span><span className="font-bold text-orange-600">{c.repitentes ?? 0}</span></div>
                              <div className="flex justify-between text-xs"><span className="text-gray-500">Prob. deserción alta</span><span className="font-bold text-red-700">{c.desertores_prob ?? 0}</span></div>
                            </div>
                            <div className="space-y-1.5">
                              <div className="text-[10px] font-semibold text-gray-500 uppercase">Ciudades top</div>
                              {c.por_ciudad && Object.entries(c.por_ciudad).slice(0, 5).map(([city, cnt]) => (
                                <MiniBar key={city} label={city} value={cnt} total={c.total_estudiantes} color="bg-teal-400" />
                              ))}
                            </div>
                          </div>
                          {c.por_nivel && Object.keys(c.por_nivel).length > 0 && (
                            <div className="mt-3">
                              <div className="text-[10px] font-semibold text-gray-500 uppercase mb-1.5">Estudiantes por nivel</div>
                              <div className="flex flex-wrap gap-2">
                                {Object.entries(c.por_nivel).map(([niv, cnt]) => (
                                  <div key={niv} className="bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-xs">
                                    <span className="text-gray-500">Niv. {niv}:</span> <span className="font-bold text-blue-700">{cnt}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
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
