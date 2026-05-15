/**
 * MiBandeja — Bandeja de Trabajo Diaria del Monitor
 *
 * [Épica 2.3] Muestra acciones priorizadas para el monitor:
 * - Alertas críticas que requieren atención inmediata
 * - Alertas altas pendientes
 * - Estudiantes con deterioro progresivo
 *
 * Cada ítem muestra: estudiante, tipo, mensaje, acción sugerida.
 * El monitor puede marcar como leído o navegar a la ficha del estudiante.
 */
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";

const PRIORIDAD_LABELS = {
  1: { text: "URGENTE", bg: "bg-red-100", border: "border-red-300", text_color: "text-red-800", dot: "bg-red-500" },
  2: { text: "ALTA", bg: "bg-amber-50", border: "border-amber-300", text_color: "text-amber-800", dot: "bg-amber-500" },
  3: { text: "MEDIA", bg: "bg-blue-50", border: "border-blue-300", text_color: "text-blue-800", dot: "bg-blue-400" },
};

const TIPO_ICONS = {
  alerta_critica: "🚨",
  alerta_alta: "⚠️",
  alerta_media: "ℹ️",
  deterioro: "📉",
};

export default function MiBandeja() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [resumen, setResumen] = useState("");
  const [porPrioridad, setPorPrioridad] = useState({});
  const [filtroCarrera, setFiltroCarrera] = useState("");
  const navigate = useNavigate();

  const fetchWorkqueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (filtroCarrera) params.carrera = filtroCarrera;
      const data = await api.getWorkqueue(params);
      setItems(data.items || []);
      setResumen(data.resumen || "");
      setPorPrioridad(data.por_prioridad || {});
    } catch (err) {
      setError(err.message || "Error al cargar bandeja de trabajo");
    } finally {
      setLoading(false);
    }
  }, [filtroCarrera]);

  useEffect(() => {
    fetchWorkqueue();
  }, [fetchWorkqueue]);

  const handleMarkRead = async (alertId) => {
    try {
      await api.patch(`/alerts/${alertId}/read`);
      setItems((prev) => prev.filter((item) => item.id !== alertId));
    } catch {
      // silently fail
    }
  };

  const handleGoToStudent = (studentId) => {
    navigate(`/estudiante/${studentId}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600">Cargando bandeja de trabajo...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 m-6">
        <h3 className="text-red-800 font-semibold">Error</h3>
        <p className="text-red-600 mt-1">{error}</p>
        <button onClick={fetchWorkqueue} className="mt-3 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">
          Reintentar
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Mi Bandeja de Trabajo</h1>
        <p className="text-gray-500 mt-1">{resumen}</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-red-600">{porPrioridad[1] || 0}</div>
          <div className="text-sm text-red-800 mt-1">Urgentes</div>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-amber-600">{porPrioridad[2] || 0}</div>
          <div className="text-sm text-amber-800 mt-1">Prioridad Alta</div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
          <div className="text-3xl font-bold text-blue-600">{porPrioridad[3] || 0}</div>
          <div className="text-sm text-blue-800 mt-1">Media</div>
        </div>
      </div>

      {/* Filtro */}
      <div className="mb-4 flex items-center gap-3">
        <input
          type="text"
          placeholder="Filtrar por carrera..."
          value={filtroCarrera}
          onChange={(e) => setFiltroCarrera(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-64 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <button
          onClick={fetchWorkqueue}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
          Actualizar
        </button>
      </div>

      {/* Lista de ítems */}
      {items.length === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-8 text-center">
          <div className="text-4xl mb-3">✅</div>
          <h3 className="text-green-800 font-semibold text-lg">Sin acciones pendientes</h3>
          <p className="text-green-600 mt-1">Todos los estudiantes están al día.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const prio = PRIORIDAD_LABELS[item.prioridad] || PRIORIDAD_LABELS[3];
            const icon = TIPO_ICONS[item.tipo] || "📋";
            return (
              <div
                key={item.id}
                className={`${prio.bg} ${prio.border} border rounded-lg p-4 transition-all hover:shadow-md`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    {/* Header row */}
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${prio.text_color} ${prio.bg}`}>
                        <span className={`w-2 h-2 rounded-full ${prio.dot} mr-1`}></span>
                        {prio.text}
                      </span>
                      <span className="text-sm">{icon}</span>
                      <span className="text-xs text-gray-500 uppercase">{item.alert_tipo?.replace(/_/g, " ")}</span>
                    </div>

                    {/* Student info */}
                    <h3 className="font-semibold text-gray-900 mt-1">
                      {item.student_nombre || `Estudiante #${item.student_id}`}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {item.student_carrera}
                      {item.asignatura && ` — ${item.asignatura}`}
                    </p>

                    {/* Message */}
                    <p className="text-sm text-gray-700 mt-2">{item.mensaje}</p>

                    {/* Suggested action */}
                    <div className="mt-2 bg-white bg-opacity-60 rounded px-3 py-2">
                      <span className="text-xs font-semibold text-gray-500 uppercase">Acción sugerida:</span>
                      <p className="text-sm text-gray-800">{item.accion_sugerida}</p>
                    </div>
                  </div>

                  {/* Action buttons */}
                  <div className="flex flex-col gap-2 ml-4">
                    <button
                      onClick={() => handleGoToStudent(item.student_id)}
                      className="px-3 py-1.5 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 whitespace-nowrap"
                    >
                      Ver ficha
                    </button>
                    <button
                      onClick={() => handleMarkRead(item.id)}
                      className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded text-xs hover:bg-gray-300 whitespace-nowrap"
                    >
                      Marcar leído
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
