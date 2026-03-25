import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import { SummaryCard } from "../components/StatCard";
import ExportExcelButton from "../components/ExportExcelButton";

const TRACKING_EXPORT_COLS = [
  { key: "docente", label: "Docente" },
  { key: "total_actividades", label: "Actividades" },
  { key: "actividades_calificadas", label: "Calificadas" },
  { key: "actividades_pendientes", label: "Pendientes" },
  { key: "porcentaje_calificacion", label: "% Calificación" },
  { key: "promedio_dias_retraso", label: "Promedio Retraso (días)" },
  { key: "alerta", label: "Estado" },
];

export default function SeguimientoDocente({ embedded = false }) {
  const [data, setData] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sortField, setSortField] = useState("porcentaje_calificacion");
  const [sortOrder, setSortOrder] = useState("asc");
  const [detalleDocente, setDetalleDocente] = useState(null);
  const [loadingDetalle, setLoadingDetalle] = useState(false);
  const [detalleData, setDetalleData] = useState(null);

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

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("asc");
    }
  };

  const sortedData = [...data].sort((a, b) => {
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
      setError("No se pudo cargar el detalle del docente.");
      console.error(e);
    } finally {
      setLoadingDetalle(false);
    }
  };

  const getEstadoBadgeStyle = (estado) => {
    if (estado === "critico") {
      return "bg-red-100 text-red-700 border border-red-200";
    } else if (estado === "atencion") {
      return "bg-yellow-100 text-yellow-700 border border-yellow-200";
    }
    return "bg-green-100 text-green-700 border border-green-200";
  };

  const getRowBgStyle = (estado) => {
    if (estado === "critico") {
      return "bg-red-50";
    } else if (estado === "atencion") {
      return "bg-yellow-50";
    }
    return "";
  };

  return (
    <div>
      {!embedded && (
        <div className="flex items-center justify-between mb-1">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Seguimiento Docente</h1>
            <p className="text-gray-500 text-sm">Control de timeliness en calificación de actividades</p>
          </div>
          <ExportExcelButton data={data} columns={TRACKING_EXPORT_COLS} filename="seguimiento_docentes" />
        </div>
      )}
      {embedded && (
        <div className="flex justify-end mb-2">
          <ExportExcelButton data={data} columns={TRACKING_EXPORT_COLS} filename="seguimiento_docentes" />
        </div>
      )}

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Resumen de tarjetas */}
      {!loading && resumen && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <SummaryCard label="Total Docentes" value={resumen.total_docentes || 0} color="blue" />
          <SummaryCard
            label="Promedio Calificación %"
            value={`${(resumen.promedio_general_calificacion || 0).toFixed(1)}%`}
            color="green"
          />
          <SummaryCard
            label="Docentes en Alerta"
            value={resumen.docentes_en_atencion || 0}
            color="yellow"
          />
          <SummaryCard
            label="Docentes Críticos"
            value={resumen.docentes_criticos || 0}
            color="red"
          />
        </div>
      )}

      {/* Tabla */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">Cargando...</div>
        ) : data.length === 0 ? (
          <div className="text-center py-20 text-gray-400">No hay datos de seguimiento disponibles</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th
                  className="text-left px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort("docente")}
                >
                  Docente {sortField === "docente" && (sortOrder === "asc" ? "▲" : "▼")}
                </th>
                <th
                  className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort("total_actividades")}
                >
                  Actividades {sortField === "total_actividades" && (sortOrder === "asc" ? "▲" : "▼")}
                </th>
                <th
                  className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort("actividades_calificadas")}
                >
                  Calificadas {sortField === "actividades_calificadas" && (sortOrder === "asc" ? "▲" : "▼")}
                </th>
                <th
                  className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort("actividades_pendientes")}
                >
                  Pendientes {sortField === "actividades_pendientes" && (sortOrder === "asc" ? "▲" : "▼")}
                </th>
                <th
                  className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort("porcentaje_calificacion")}
                >
                  % Calificación {sortField === "porcentaje_calificacion" && (sortOrder === "asc" ? "▲" : "▼")}
                </th>
                <th
                  className="text-center px-4 py-3 font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort("promedio_dias_retraso")}
                >
                  Promedio Retraso (días) {sortField === "promedio_dias_retraso" && (sortOrder === "asc" ? "▲" : "▼")}
                </th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Estado</th>
              </tr>
            </thead>
            <tbody>
              {sortedData.map((d, i) => (
                <tr
                  key={`${d.docente}-${i}`}
                  onClick={() => openDetalle(d.docente)}
                  className={`border-b border-gray-100 cursor-pointer hover:bg-blue-50 transition-colors ${getRowBgStyle(d.alerta)}`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{d.docente}</div>
                  </td>
                  <td className="px-4 py-3 text-center font-semibold">{d.total_actividades}</td>
                  <td className="px-4 py-3 text-center font-semibold text-green-600">{d.actividades_calificadas}</td>
                  <td className="px-4 py-3 text-center font-semibold text-red-600">{d.actividades_pendientes}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`font-bold ${
                      d.porcentaje_calificacion >= 80 ? "text-green-600" :
                      d.porcentaje_calificacion >= 60 ? "text-yellow-600" :
                      "text-red-600"
                    }`}>
                      {d.porcentaje_calificacion?.toFixed(1) || "—"}%
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center font-mono text-gray-600">
                    {d.promedio_dias_retraso?.toFixed(1) || "—"}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-xs font-semibold px-2 py-1 rounded-full ${getEstadoBadgeStyle(d.alerta)}`}>
                      {d.alerta === "critico" ? "Crítico" : d.alerta === "atencion" ? "Atención" : "Ok"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal detalle docente */}
      {detalleDocente && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setDetalleDocente(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">Detalle: {detalleDocente}</h2>
                  <p className="text-sm text-gray-500 mt-1">Desglose por actividad</p>
                </div>
                <button onClick={() => setDetalleDocente(null)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
              </div>
            </div>

            <div className="p-6 space-y-4">
              {loadingDetalle ? (
                <div className="text-center text-gray-400">Cargando detalles...</div>
              ) : detalleData?.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left px-4 py-3 font-semibold text-gray-700">Curso</th>
                      <th className="text-left px-4 py-3 font-semibold text-gray-700">Actividad</th>
                      <th className="text-center px-4 py-3 font-semibold text-gray-700">Tipo</th>
                      <th className="text-center px-4 py-3 font-semibold text-gray-700">Calificada</th>
                      <th className="text-center px-4 py-3 font-semibold text-gray-700">Fecha Límite</th>
                      <th className="text-center px-4 py-3 font-semibold text-gray-700">Fecha Calificación</th>
                      <th className="text-center px-4 py-3 font-semibold text-gray-700">Días Retraso</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detalleData.map((act, idx) => (
                      <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-3 text-gray-800">{act.nombre_curso || "—"}</td>
                        <td className="px-4 py-3 text-gray-800">{act.actividad || "—"}</td>
                        <td className="px-4 py-3 text-center text-gray-600">{act.tipo_actividad || "—"}</td>
                        <td className="px-4 py-3 text-center font-semibold text-green-600">{act.calificada ? "Sí" : "No"}</td>
                        <td className="px-4 py-3 text-center text-gray-600">{act.fecha_limite || "—"}</td>
                        <td className="px-4 py-3 text-center text-gray-600">{act.fecha_calificacion || "—"}</td>
                        <td className="px-4 py-3 text-center font-mono text-gray-600">{act.dias_retraso?.toFixed(1) || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-center py-8 text-gray-400">No hay detalles disponibles</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
