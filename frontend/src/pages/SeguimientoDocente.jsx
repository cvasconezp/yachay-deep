import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { SummaryCard } from "../components/StatCard";
import ExportExcelButton from "../components/ExportExcelButton";

const TRACKING_EXPORT_COLS = [
  { key: "docente", label: "Docente" },
  { key: "total_cursos", label: "Cursos" },
  { key: "total_tareas", label: "Total Tareas" },
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

  const getEstadoBadge = (estado) => {
    if (estado === "critico") return { bg: "bg-red-100 text-red-700 border-red-200", label: "Crítico" };
    if (estado === "atencion") return { bg: "bg-yellow-100 text-yellow-700 border-yellow-200", label: "Atención" };
    return { bg: "bg-green-100 text-green-700 border-green-200", label: "Ok" };
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span className="text-gray-300 ml-1">↕</span>;
    return <span className="ml-1">{sortOrder === "asc" ? "▲" : "▼"}</span>;
  };

  return (
    <div>
      {!embedded && (
        <div className="flex items-center justify-between mb-1">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Seguimiento Docente</h1>
            <p className="text-gray-500 text-sm">Pendientes por calificar por docente</p>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
      )}

      {/* KPI Cards */}
      {!loading && resumen && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <SummaryCard label="Docentes" value={resumen.total_docentes || 0} color="blue" />
          <SummaryCard label="Total Pendientes" value={resumen.total_pendientes || 0} color="red" />
          <SummaryCard label="Prom. Calificación" value={`${(resumen.promedio_general_calificacion || 0).toFixed(0)}%`} color="green" />
          <SummaryCard label="En Atención" value={resumen.docentes_en_atencion || 0} color="yellow" />
          <SummaryCard label="Críticos" value={resumen.docentes_criticos || 0} color="red" />
        </div>
      )}

      {/* Search + Export */}
      <div className="flex items-center gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Buscar docente o asignatura..."
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <ExportExcelButton data={filteredData} columns={TRACKING_EXPORT_COLS} filename="seguimiento_docentes" />
        <span className="text-sm text-gray-500">{filteredData.length} docentes</span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">Cargando...</div>
        ) : sortedData.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <div className="text-4xl mb-3">📝</div>
            <div className="font-medium text-gray-500 mb-1">No hay datos de seguimiento</div>
            <div className="text-xs text-gray-400">Los datos se generan después del scraping de tareas AVAC</div>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100" onClick={() => handleSort("docente")}>
                  Docente <SortIcon field="docente" />
                </th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100" onClick={() => handleSort("total_cursos")}>
                  Cursos <SortIcon field="total_cursos" />
                </th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100" onClick={() => handleSort("total_tareas")}>
                  Total <SortIcon field="total_tareas" />
                </th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100" onClick={() => handleSort("actividades_calificadas")}>
                  Calificadas <SortIcon field="actividades_calificadas" />
                </th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100" onClick={() => handleSort("actividades_pendientes")}>
                  Pendientes <SortIcon field="actividades_pendientes" />
                </th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100" onClick={() => handleSort("porcentaje_calificacion")}>
                  % Calif. <SortIcon field="porcentaje_calificacion" />
                </th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Estado</th>
              </tr>
            </thead>
            <tbody>
              {sortedData.map((d, i) => {
                const badge = getEstadoBadge(d.alerta);
                return (
                  <tr
                    key={`${d.docente}-${i}`}
                    onClick={() => openDetalle(d.docente)}
                    className={`border-b border-gray-100 cursor-pointer hover:bg-blue-50 transition-colors ${
                      d.alerta === "critico" ? "bg-red-50/40" : d.alerta === "atencion" ? "bg-yellow-50/40" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{d.docente}</div>
                      <div className="text-xs text-gray-400 truncate max-w-[250px]">{d.cursos?.join(", ")}</div>
                    </td>
                    <td className="px-4 py-3 text-center font-semibold">{d.total_cursos}</td>
                    <td className="px-4 py-3 text-center text-gray-600">{d.total_tareas}</td>
                    <td className="px-4 py-3 text-center font-semibold text-green-600">{d.actividades_calificadas}</td>
                    <td className="px-4 py-3 text-center">
                      {d.actividades_pendientes > 0 ? (
                        <span className={`font-bold px-2 py-0.5 rounded-full text-xs ${
                          d.actividades_pendientes > 20 ? "bg-red-100 text-red-700" :
                          d.actividades_pendientes > 5 ? "bg-yellow-100 text-yellow-700" :
                          "bg-orange-100 text-orange-700"
                        }`}>{d.actividades_pendientes}</span>
                      ) : (
                        <span className="text-green-500 text-xs">✓</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <div className="w-16 h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              d.porcentaje_calificacion >= 80 ? "bg-green-500" :
                              d.porcentaje_calificacion >= 60 ? "bg-yellow-500" : "bg-red-500"
                            }`}
                            style={{ width: `${d.porcentaje_calificacion}%` }}
                          />
                        </div>
                        <span className={`font-mono font-semibold text-xs ${
                          d.porcentaje_calificacion >= 80 ? "text-green-600" :
                          d.porcentaje_calificacion >= 60 ? "text-yellow-600" : "text-red-600"
                        }`}>{d.porcentaje_calificacion}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs font-semibold px-2 py-1 rounded-full border ${badge.bg}`}>
                        {badge.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal detalle por curso */}
      {detalleDocente && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setDetalleDocente(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[85vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{detalleDocente}</h2>
                  <p className="text-sm text-gray-500 mt-1">Pendientes por calificar, desglosado por curso y estudiante</p>
                </div>
                <button onClick={() => setDetalleDocente(null)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {loadingDetalle ? (
                <div className="text-center py-8 text-gray-400">Cargando detalles...</div>
              ) : detalleData?.length > 0 ? (
                detalleData.map((curso, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-xl overflow-hidden">
                    <div className="bg-gray-50 px-4 py-3 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="font-semibold text-gray-800">{curso.asignatura}</span>
                        <span className="text-xs text-gray-400">{curso.codigo_curso}</span>
                      </div>
                      <div className="flex items-center gap-4 text-xs">
                        <span className="text-green-600 font-semibold">{curso.calificadas} calificadas</span>
                        {curso.pendientes > 0 && (
                          <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-bold">
                            {curso.pendientes} pendientes
                          </span>
                        )}
                        <span className="text-gray-500">{curso.total_tareas} total</span>
                      </div>
                    </div>

                    {curso.estudiantes_pendientes?.length > 0 ? (
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-100">
                            <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Estudiante</th>
                            <th className="text-center px-4 py-2 text-xs font-medium text-gray-500">Tareas Pendientes</th>
                            <th className="text-center px-4 py-2 text-xs font-medium text-gray-500">Última Entrega</th>
                          </tr>
                        </thead>
                        <tbody>
                          {curso.estudiantes_pendientes.map((est, ei) => (
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
                                  ? new Date(est.ultima_entrega).toLocaleDateString("es-EC", { day: "2-digit", month: "short" })
                                  : "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <div className="px-4 py-3 text-sm text-green-600">✓ Todas las entregas calificadas</div>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-gray-400">No hay datos disponibles para este docente</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
