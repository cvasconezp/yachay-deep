import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import { StatCard } from "../components/StatCard";
import { PeriodSelector } from "../components/PeriodSelector";
import { TrendCharts } from "../components/TrendCharts";

function MiniBar({ label, value, total, color = "bg-brand" }) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-24 text-gray-500 truncate" title={label}>{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2.5 overflow-hidden">
        <div className={`${color} h-full rounded-full transition-all`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="w-8 text-right font-medium text-gray-700">{value}</span>
    </div>
  );
}

const DEFAULT_EXPORT_COLS = [
  "cedula", "nombre", "correo_institucional", "carrera",
  "nivel_academico", "nivel_riesgo", "promedio_calificaciones",
];

export default function ResumenDatos() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [carreras, setCarreras] = useState([]);
  const [filtroCarrera, setFiltroCarrera] = useState("");
  const [filtroPeriodo, setFiltroPeriodo] = useState("actual");
  const [comparativa, setComparativa] = useState([]);

  // Export state
  const [exportOpen, setExportOpen] = useState(false);
  const [colsDisponibles, setColsDisponibles] = useState([]);
  const [colsSeleccionadas, setColsSeleccionadas] = useState(new Set(DEFAULT_EXPORT_COLS));
  const [exportCarrera, setExportCarrera] = useState("");
  const [exportNivel, setExportNivel] = useState("");
  const [exportRiesgo, setExportRiesgo] = useState("");
  const [exportPeriodo, setExportPeriodo] = useState("actual");
  const [exporting, setExporting] = useState(false);

  // Carrera detail expand
  const [expandedCarrera, setExpandedCarrera] = useState(null);

  useEffect(() => {
    api.getCarreras().then(setCarreras).catch(() => {});
    api.getExportColumnas().then(setColsDisponibles).catch(() => {});
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (filtroCarrera) params.carrera = filtroCarrera;
      if (filtroPeriodo && filtroPeriodo !== "actual") params.periodo = filtroPeriodo;
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
      if (next.has(key)) next.delete(key);
      else next.add(key);
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
      if (exportPeriodo && exportPeriodo !== "actual") params.set("periodo", exportPeriodo);

      const blob = await api.exportEstudiantesExcel(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "estudiantes.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message);
    } finally {
      setExporting(false);
    }
  };

  const g = data?.global || {};
  const porCarrera = data?.por_carrera || [];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Resumen de Datos</h1>
          <p className="text-gray-400 text-sm">Vista general de estudiantes, carreras y datos demográficos</p>
        </div>
        <button
          onClick={() => setExportOpen(!exportOpen)}
          className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm"
        >
          {"📥"} Exportar Excel
        </button>
      </div>

      {/* Export panel */}
      {exportOpen && (
        <div className="bg-white rounded-xl border border-green-200 shadow-sm mb-5 p-5">
          <h3 className="text-sm font-bold text-gray-800 mb-3">Configurar exportación Excel</h3>

          {/* Export filters */}
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

          {/* Column selection */}
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
                  <input
                    type="checkbox"
                    checked={colsSeleccionadas.has(col.key)}
                    onChange={() => toggleCol(col.key)}
                    className="accent-green-600"
                  />
                  <span className="text-gray-700">{col.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleExport}
              disabled={exporting || colsSeleccionadas.size === 0}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {exporting ? "Generando..." : "Descargar Excel"}
            </button>
            <button onClick={() => setExportOpen(false)} className="text-sm text-gray-500 hover:text-gray-700">Cerrar</button>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex flex-wrap gap-2 mb-5">
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

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4 text-red-700 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadData} className="text-red-600 hover:text-red-800 font-medium text-sm">Reintentar</button>
        </div>
      )}

      {/* Loading */}
      {loading && <div className="text-center py-12 text-gray-400">Cargando resumen...</div>}

      {/* Global stats */}
      {!loading && g.total_estudiantes && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-5">
            <StatCard label="Total estudiantes" value={g.total_estudiantes} color="text-brand" />
            <StatCard label="Docentes" value={g.total_docentes ?? "—"} color="text-blue-600" />
            <StatCard label="Promedio calificaciones" value={g.promedio_calificaciones ?? "—"} color="text-gray-700" sub="sobre 100" />
            <StatCard label="Edad promedio" value={g.promedio_edad ? `${g.promedio_edad} años` : "—"} color="text-gray-600" />
            <StatCard label="Compromiso promedio" value={g.promedio_compromiso ? `${(g.promedio_compromiso * 100).toFixed(0)}%` : "—"} color="text-teal-600" />
          </div>

          {/* Risk + Academic indicators */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            {/* Riesgo */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Distribución de riesgo</h3>
              <div className="space-y-2">
                <MiniBar label="Alto" value={g.por_riesgo?.Alto || 0} total={g.total_estudiantes} color="bg-red-500" />
                <MiniBar label="Medio" value={g.por_riesgo?.Medio || 0} total={g.total_estudiantes} color="bg-yellow-500" />
                <MiniBar label="Bajo" value={g.por_riesgo?.Bajo || 0} total={g.total_estudiantes} color="bg-green-500" />
              </div>
            </div>

            {/* Academic */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Indicadores académicos</h3>
              <div className="space-y-2.5">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Reprobados</span>
                  <span className="font-bold text-red-600">{g.reprobados ?? 0}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Repitentes</span>
                  <span className="font-bold text-orange-600">{g.repitentes ?? 0}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Prob. deserción alta</span>
                  <span className="font-bold text-red-700">{g.desertores_prob ?? 0}</span>
                </div>
              </div>
            </div>

            {/* Demographics */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Género</h3>
              <div className="space-y-2">
                {g.por_genero && Object.entries(g.por_genero).map(([gen, cnt]) => (
                  <MiniBar key={gen} label={gen} value={cnt} total={g.total_estudiantes} color="bg-indigo-400" />
                ))}
              </div>
            </div>
          </div>

          {/* Niveles + Ciudades + Etnias */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            {/* Niveles académicos */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Por nivel académico</h3>
              <div className="space-y-2">
                {g.por_nivel && Object.entries(g.por_nivel).map(([niv, cnt]) => (
                  <MiniBar key={niv} label={`Nivel ${niv}`} value={cnt} total={g.total_estudiantes} color="bg-blue-400" />
                ))}
              </div>
            </div>

            {/* Ciudades top 8 */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Principales ciudades</h3>
              <div className="space-y-2">
                {g.por_ciudad && Object.entries(g.por_ciudad).slice(0, 8).map(([city, cnt]) => (
                  <MiniBar key={city} label={city} value={cnt} total={g.total_estudiantes} color="bg-teal-400" />
                ))}
              </div>
            </div>

            {/* Etnias */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Autoidentificación étnica</h3>
              <div className="space-y-2">
                {g.por_etnia && Object.entries(g.por_etnia).slice(0, 8).map(([etnia, cnt]) => (
                  <MiniBar key={etnia} label={etnia} value={cnt} total={g.total_estudiantes} color="bg-purple-400" />
                ))}
              </div>
            </div>
          </div>

          {/* Intervenciones */}
          {g.intervenciones && g.intervenciones.total > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm mb-5 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100">
                <h3 className="text-sm font-bold text-gray-800">Intervenciones realizadas</h3>
                <p className="text-xs text-gray-400 mt-0.5">Seguimiento y resolución de casos</p>
              </div>
              <div className="p-5">
                {/* Summary cards */}
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
                      {g.intervenciones.total > 0
                        ? `${Math.round((g.intervenciones.resueltas / g.intervenciones.total) * 100)}%`
                        : "—"}
                    </div>
                    <div className="text-[10px] text-gray-500 uppercase font-medium">Tasa resolución</div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Por motivo */}
                  <div>
                    <div className="text-[10px] font-semibold text-gray-500 uppercase mb-2">Por motivo</div>
                    <div className="space-y-1.5">
                      {Object.entries(g.intervenciones.por_motivo || {})
                        .sort((a, b) => b[1] - a[1])
                        .map(([motivo, cnt]) => (
                          <MiniBar key={motivo} label={motivo} value={cnt} total={g.intervenciones.total} color="bg-blue-400" />
                        ))}
                    </div>
                  </div>
                  {/* Por resultado */}
                  <div>
                    <div className="text-[10px] font-semibold text-gray-500 uppercase mb-2">Por resultado</div>
                    <div className="space-y-1.5">
                      {Object.entries(g.intervenciones.por_resultado || {})
                        .sort((a, b) => b[1] - a[1])
                        .map(([resultado, cnt]) => (
                          <MiniBar key={resultado} label={resultado} value={cnt} total={g.intervenciones.total} color="bg-purple-400" />
                        ))}
                    </div>
                  </div>
                </div>

                {/* Por carrera */}
                {Object.keys(g.intervenciones.por_carrera || {}).length > 1 && (
                  <div className="mt-4">
                    <div className="text-[10px] font-semibold text-gray-500 uppercase mb-2">Intervenciones por carrera</div>
                    <div className="space-y-1.5">
                      {Object.entries(g.intervenciones.por_carrera)
                        .sort((a, b) => b[1] - a[1])
                        .map(([car, cnt]) => (
                          <MiniBar key={car} label={car} value={cnt} total={g.intervenciones.total} color="bg-teal-400" />
                        ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Sedes */}
          {g.por_sede && Object.keys(g.por_sede).length > 1 && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm mb-5">
              <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Por centro de apoyo (sede)</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {Object.entries(g.por_sede).map(([sede, cnt]) => (
                  <div key={sede} className="flex justify-between text-sm bg-gray-50 rounded-lg px-3 py-2">
                    <span className="text-gray-600 truncate" title={sede}>{sede}</span>
                    <span className="font-bold text-brand ml-2">{cnt}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tendencias comparativas */}
          <TrendCharts data={comparativa} />

          {/* Docentes por carrera */}
          {porCarrera.length > 0 && porCarrera.some(c => c.total_docentes > 0) && (
            <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-6">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Docentes por carrera</h3>
              <div className="space-y-1.5">
                {porCarrera
                  .filter(c => c.total_docentes > 0)
                  .sort((a, b) => b.total_docentes - a.total_docentes)
                  .map(c => (
                    <MiniBar
                      key={c.carrera}
                      label={c.carrera}
                      value={c.total_docentes}
                      total={Math.max(...porCarrera.map(x => x.total_docentes))}
                      color="bg-blue-500"
                    />
                  ))}
              </div>
            </div>
          )}

          {/* Desglose por carrera */}
          {porCarrera.length > 0 && (
            <div className="mb-5">
              <h2 className="text-lg font-bold text-gray-800 mb-3">Desglose por carrera</h2>
              <div className="space-y-3">
                {porCarrera.map(c => (
                  <div key={c.carrera} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                    <button
                      onClick={() => setExpandedCarrera(expandedCarrera === c.carrera ? null : c.carrera)}
                      className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center gap-4">
                        <h3 className="text-sm font-bold text-gray-800">{c.carrera}</h3>
                        <div className="flex gap-3 text-xs text-gray-500">
                          <span><strong className="text-brand">{c.total_estudiantes}</strong> est.</span>
                          <span><strong className="text-blue-600">{c.total_docentes}</strong> doc.</span>
                          <span>Prom: <strong>{c.promedio_calificaciones ?? "—"}</strong></span>
                          <span className="text-red-600"><strong>{c.por_riesgo?.Alto || 0}</strong> alto riesgo</span>
                          {c.intervenciones?.total > 0 && (
                            <span className="text-blue-500"><strong>{c.intervenciones.total}</strong> interv.</span>
                          )}
                        </div>
                      </div>
                      <span className="text-gray-400 text-lg">{expandedCarrera === c.carrera ? "−" : "+"}</span>
                    </button>

                    {expandedCarrera === c.carrera && (
                      <div className="border-t border-gray-100 px-5 py-4 bg-gray-50/50">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                          <div className="text-center">
                            <div className="text-2xl font-bold text-brand">{c.total_estudiantes}</div>
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
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          {/* Riesgo */}
                          <div className="space-y-1.5">
                            <div className="text-[10px] font-semibold text-gray-500 uppercase">Riesgo</div>
                            <MiniBar label="Alto" value={c.por_riesgo?.Alto || 0} total={c.total_estudiantes} color="bg-red-500" />
                            <MiniBar label="Medio" value={c.por_riesgo?.Medio || 0} total={c.total_estudiantes} color="bg-yellow-500" />
                            <MiniBar label="Bajo" value={c.por_riesgo?.Bajo || 0} total={c.total_estudiantes} color="bg-green-500" />
                          </div>

                          {/* Académico */}
                          <div className="space-y-1.5">
                            <div className="text-[10px] font-semibold text-gray-500 uppercase">Académico</div>
                            <div className="flex justify-between text-xs">
                              <span className="text-gray-500">Reprobados</span>
                              <span className="font-bold text-red-600">{c.reprobados ?? 0}</span>
                            </div>
                            <div className="flex justify-between text-xs">
                              <span className="text-gray-500">Repitentes</span>
                              <span className="font-bold text-orange-600">{c.repitentes ?? 0}</span>
                            </div>
                            <div className="flex justify-between text-xs">
                              <span className="text-gray-500">Prob. deserción alta</span>
                              <span className="font-bold text-red-700">{c.desertores_prob ?? 0}</span>
                            </div>
                          </div>

                          {/* Ciudades top 5 */}
                          <div className="space-y-1.5">
                            <div className="text-[10px] font-semibold text-gray-500 uppercase">Ciudades</div>
                            {c.por_ciudad && Object.entries(c.por_ciudad).slice(0, 5).map(([city, cnt]) => (
                              <MiniBar key={city} label={city} value={cnt} total={c.total_estudiantes} color="bg-teal-400" />
                            ))}
                          </div>
                        </div>

                        {/* Intervenciones de la carrera */}
                        {c.intervenciones && c.intervenciones.total > 0 && (
                          <div className="mt-3">
                            <div className="text-[10px] font-semibold text-gray-500 uppercase mb-1.5">Intervenciones</div>
                            <div className="grid grid-cols-3 gap-2 mb-2">
                              <div className="text-center bg-blue-50 rounded-lg px-2 py-1.5">
                                <div className="text-sm font-bold text-blue-700">{c.intervenciones.total}</div>
                                <div className="text-[9px] text-blue-500">Total</div>
                              </div>
                              <div className="text-center bg-green-50 rounded-lg px-2 py-1.5">
                                <div className="text-sm font-bold text-green-700">{c.intervenciones.resueltas}</div>
                                <div className="text-[9px] text-green-500">Resueltas</div>
                              </div>
                              <div className="text-center bg-orange-50 rounded-lg px-2 py-1.5">
                                <div className="text-sm font-bold text-orange-700">{c.intervenciones.pendientes}</div>
                                <div className="text-[9px] text-orange-500">Pendientes</div>
                              </div>
                            </div>
                            {Object.keys(c.intervenciones.por_motivo || {}).length > 0 && (
                              <div className="space-y-1">
                                {Object.entries(c.intervenciones.por_motivo).sort((a, b) => b[1] - a[1]).map(([mot, cnt]) => (
                                  <MiniBar key={mot} label={mot} value={cnt} total={c.intervenciones.total} color="bg-blue-400" />
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Niveles */}
                        {c.por_nivel && Object.keys(c.por_nivel).length > 0 && (
                          <div className="mt-3">
                            <div className="text-[10px] font-semibold text-gray-500 uppercase mb-1.5">Estudiantes por nivel</div>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(c.por_nivel).map(([niv, cnt]) => (
                                <div key={niv} className="bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-xs">
                                  <span className="text-gray-500">Niv. {niv}:</span>{" "}
                                  <span className="font-bold text-brand">{cnt}</span>
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
          )}
        </>
      )}

      {/* Empty state */}
      {!loading && !error && !g.total_estudiantes && (
        <div className="text-center py-16 text-gray-300">
          <div className="text-4xl mb-3">{"📊"}</div>
          <div className="text-sm">No hay datos disponibles</div>
          <p className="text-xs text-gray-400 mt-1">Ejecuta el proceso ETL para cargar datos de estudiantes</p>
        </div>
      )}
    </div>
  );
}
