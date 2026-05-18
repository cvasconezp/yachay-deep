import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { SummaryCard } from "../components/StatCard";
import ExportExcelButton from "../components/ExportExcelButton";

const TRACKING_EXPORT_COLS = [
  { key: "docente", label: "Docente" },
  { key: "total_cursos", label: "Cursos" },
  { key: "total_tareas", label: "Total Entregas" },
  { key: "actividades_calificadas", label: "Calificadas" },
  { key: "actividades_pendientes", label: "Pendientes" },
  { key: "porcentaje_calificacion", label: "% Calificación" },
  { key: "alerta", label: "Estado" },
];

export default function SeguimientoDocente({ embedded = false }) {
  const [data, setData] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sortField, setSortField] = useState("actividades_pendientes");
  const [sortOrder, setSortOrder] = useState("desc");
  const [detalleDocente, setDetalleDocente] = useState(null);
  const [loadingDetalle, setLoadingDetalle] = useState(false);
  const [detalleData, setDetalleData] = useState(null);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [trackingData, resumenData] = await Promise.all([
        api.getDocenteTracking(),
        api.getDocenteTrackingResumen(),
      ]);
      setData(trackingData || []);
      setResumen(resumenData);
    } catch (e) {
      setError("No se pudieron cargar los datos de seguimiento docente.");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder(field === "docente" ? "asc" : "desc");
    }
  };

  const filteredData = search
    ? data.filter(d => d.docente?.toLowerCase().includes(search.toLowerCase()) ||
        d.cursos?.some(c => c.toLowerCase().includes(search.toLowerCase())))
    : data;

  const sortedData = [...filteredData].sort((a, b) => {
    const aVal = a[sortField];
    const bVal = b[sortField];
    if (aVal == null) return 1;
    if (bVal == null) return -1;
    const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return sortOrder === "asc" ? cmp : -cmp;
  });

  const openDetalle = async (docente) => {
    setDetalleDocente(docente);
    setLoadingDetalle(true);
    setDetalleData(null);
    try {
      const detail = await api.getDocenteTrackingDetalle(docente);
      setDetalleData(detail);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDetalle(false);
    }
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span className="text-gray-300 ml-0.5 text-[10px]">↕</span>;
    return <span className="ml-0.5 text-[10px]">{sortOrder === "asc" ? "▲" : "▼"}</span>;
  };

  return (
    <div>
      {!embedded && (
        <div className="mb-1">
          <h1 className="text-2xl font-bold text-gray-900">Seguimiento Docente</h1>
          <p className="text-gray-500 text-sm">Pendientes por calificar por docente</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
      )}

      {/* KPI Cards */}
      {!loading && resumen && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
          <SummaryCard label="Docentes" value={resumen.total_docentes || 0} color="blue" />
          <SummaryCard label="Total Pendientes" value={resumen.total_pendientes || 0} color="red" />
          <SummaryCard label="Prom. Calificación" value={`${(resumen.promedio_general_calificacion || 0).toFixed(0)}%`} color="green" />
          <SummaryCard label="En Atención" value={resumen.docentes_en_atencion || 0} color="yellow" />
          <SummaryCard label="Críticos" value={resumen.docentes_criticos || 0} color="red" />
        </div>
      )}

      {/* Búsqueda + Export */}
      <div className="bg-white rounded-xl border border-gray-200 p-3 mb-4 flex flex-wrap gap-3 items-center">
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar por docente o asignatura..."
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <ExportExcelButton data={filteredData} columns={TRACKING_EXPORT_COLS} filename="seguimiento_docentes" />
        <span className="text-sm text-gray-500">{filteredData.length} docentes</span>
      </div>

      {/* Tabla */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">Cargando...</div>
        ) : sortedData.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <div className="text-4xl mb-3">📝</div>
            <div className="font-medium text-gray-500 mb-1">No hay datos de seguimiento</div>
            <div className="text-xs text-gray-400">Los datos se generan después del scraping de tareas AVAC.<br/>Verifica que CourseConfig tenga docentes asignados.</div>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100" onClick={() => handleSort("docente")}>
                  Docente <SortIcon field="docente" />
                </th>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Asignaturas</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100" onClick={() => handleSort("actividades_pendientes")}>
                  Por calificar <SortIcon field="actividades_pendientes" />
                </th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100" onClick={() => handleSort("porcentaje_calificacion")}>
                  Progreso <SortIcon field="porcentaje_calificacion" />
                </th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Estado</th>
              </tr>
            </thead>
            <tbody>
              {sortedData.map((d, i) => {
                const pend = d.actividades_pendientes || 0;
                const total = d.total_tareas || 0;
                const cal = d.actividades_calificadas || 0;
                const pct = d.porcentaje_calificacion || 0;
                return (
                  <tr
                    key={`${d.docente}-${i}`}
                    onClick={() => openDetalle(d.docente)}
                    className={`border-b border-gray-100 cursor-pointer hover:bg-blue-50 transition-colors ${
                      d.alerta === "critico" ? "bg-red-50/50" : d.alerta === "atencion" ? "bg-yellow-50/40" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{d.docente}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-xs text-gray-500 truncate max-w-[300px]">{d.cursos?.join(", ") || "—"}</div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {pend > 0 ? (
                        <span className={`font-bold text-sm ${pend > 20 ? "text-red-600" : pend > 5 ? "text-yellow-600" : "text-orange-600"}`}>
                          ({pend}/{total})
                        </span>
                      ) : total > 0 ? (
                        <span className="text-green-600 font-semibold text-sm">✓ ({cal}/{total})</span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-2">
                        <div className="w-20 h-2.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              pct >= 80 ? "bg-green-500" : pct >= 60 ? "bg-yellow-500" : "bg-red-500"
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className={`font-mono text-xs font-semibold w-10 text-right ${
                          pct >= 80 ? "text-green-600" : pct >= 60 ? "text-yellow-600" : "text-red-600"
                        }`}>{pct}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {d.alerta === "critico" ? (
                        <span className="text-xs font-semibold px-2 py-1 rounded-full bg-red-100 text-red-700 border border-red-200">Crítico</span>
                      ) : d.alerta === "atencion" ? (
                        <span className="text-xs font-semibold px-2 py-1 rounded-full bg-yellow-100 text-yellow-700 border border-yellow-200">Atención</span>
                      ) : (
                        <span className="text-xs font-semibold px-2 py-1 rounded-full bg-green-100 text-green-700 border border-green-200">Ok</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Modal detalle: cursos + estudiantes pendientes ── */}
      {detalleDocente && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setDetalleDocente(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[85vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{detalleDocente}</h2>
                  <p className="text-sm text-gray-500 mt-1">Pendientes por calificar — desglose por curso y estudiante</p>
                </div>
                <button onClick={() => setDetalleDocente(null)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
              </div>
            </div>

            <div className="p-6 space-y-5">
              {loadingDetalle ? (
                <div className="text-center py-8 text-gray-400">Cargando detalles...</div>
              ) : detalleData?.length > 0 ? (
                detalleData.map((curso, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-xl overflow-hidden">
                    {/* Cabecera del curso */}
                    <div className={`px-4 py-3 flex items-center justify-between ${
                      curso.pendientes > 0 ? "bg-red-50" : "bg-green-50"
                    }`}>
                      <div className="flex items-center gap-3">
                        <span className="font-semibold text-gray-800">{curso.asignatura}</span>
                        <span className="text-xs text-gray-400 bg-white px-2 py-0.5 rounded">{curso.codigo_curso}</span>
                      </div>
                      <div className="flex items-center gap-3 text-sm">
                        {curso.pendientes > 0 ? (
                          <span className="bg-red-100 text-red-700 px-3 py-1 rounded-full font-bold">
                            ({curso.pendientes}/{curso.total_tareas}) por calificar
                          </span>
                        ) : (
                          <span className="bg-green-100 text-green-700 px-3 py-1 rounded-full font-semibold">
                            ✓ Todo calificado ({curso.calificadas}/{curso.total_tareas})
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Estudiantes pendientes */}
                    {curso.estudiantes_pendientes?.length > 0 ? (
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-100 bg-white">
                            <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Estudiante</th>
                            <th className="text-center px-4 py-2 text-xs font-medium text-gray-500">Tareas sin calificar</th>
                            <th className="text-center px-4 py-2 text-xs font-medium text-gray-500">Última entrega</th>
                          </tr>
                        </thead>
                        <tbody>
                          {curso.estudiantes_pendientes.map((est) => (
                            <tr
                              key={est.student_id}
                              onClick={(e) => { e.stopPropagation(); navigate(`/ficha/${est.student_id}`); }}
                              className="border-b border-gray-50 cursor-pointer hover:bg-blue-50"
                            >
                              <td className="px-4 py-2 text-gray-800">{est.nombre}</td>
                              <td className="px-4 py-2 text-center">
                                <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full text-xs font-bold">
                                  {est.tareas_pendientes}
                                </span>
                              </td>
                              <td className="px-4 py-2 text-center text-xs text-gray-500">
                                {est.ultima_entrega
                                  ? new Date(est.ultima_entrega).toLocaleDateString("es-EC", { day: "2-digit", month: "short", year: "numeric" })
                                  : "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : curso.pendientes > 0 ? (
                      <div className="px-4 py-3 text-sm text-gray-500 italic">Hay pendientes pero los estudiantes no pudieron ser identificados</div>
                    ) : (
                      <div className="px-4 py-3 text-sm text-green-600">✓ Todas las entregas han sido calificadas</div>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-gray-400">
                  <div className="text-3xl mb-2">📭</div>
                  <div>No hay datos de tareas para los cursos de este docente</div>
                  <div className="text-xs mt-1">Verifica que los cursos tengan código AVAC asignado en CourseConfig</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
