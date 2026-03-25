import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";

export default function Alertas() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generatingAlerts, setGeneratingAlerts] = useState(false);
  const { user } = useAuth();
  const navigate = useNavigate();

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getAlertsPending();
      setAlerts(data || []);
    } catch (e) {
      setError("No se pudieron cargar las alertas.");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  const handleMarkAsRead = async (id, e) => {
    e.stopPropagation();
    try {
      await api.markAlertRead(id);
      setAlerts(alerts.filter(a => a.id !== id));
    } catch (e) {
      setError("No se pudo marcar la alerta como leída.");
      console.error(e);
    }
  };

  const handleGenerateAlerts = async () => {
    if (!window.confirm("¿Generar nuevas alertas? Esta operación puede tomar un tiempo.")) {
      return;
    }
    setGeneratingAlerts(true);
    setError("");
    try {
      await api.generateAlerts();
      setError(""); // Clear any previous error
      setTimeout(() => {
        loadAlerts();
        // Show success message
        setError(""); // Reset
      }, 1000);
    } catch (e) {
      setError("Error al generar alertas: " + (e.message || "Intenta de nuevo"));
      console.error(e);
    } finally {
      setGeneratingAlerts(false);
    }
  };

  const getSeverityStyle = (severity) => {
    switch (severity) {
      case "critico":
        return "border-l-4 border-l-red-600 bg-red-50";
      case "alto":
        return "border-l-4 border-l-orange-500 bg-orange-50";
      case "medio":
        return "border-l-4 border-l-yellow-500 bg-yellow-50";
      default:
        return "border-l-4 border-l-blue-500 bg-blue-50";
    }
  };

  const getSeverityBadgeStyle = (severity) => {
    switch (severity) {
      case "critico":
        return "bg-red-100 text-red-700";
      case "alto":
        return "bg-orange-100 text-orange-700";
      case "medio":
        return "bg-yellow-100 text-yellow-700";
      default:
        return "bg-blue-100 text-blue-700";
    }
  };

  // Group alerts by severity
  const severityOrder = { critico: 0, alto: 1, medio: 2 };
  const groupedAlerts = {};
  alerts.forEach(alert => {
    const severity = alert.severidad || "medio";
    if (!groupedAlerts[severity]) {
      groupedAlerts[severity] = [];
    }
    groupedAlerts[severity].push(alert);
  });

  const sortedSeverities = Object.keys(groupedAlerts).sort((a, b) => severityOrder[a] - severityOrder[b]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alertas</h1>
          <p className="text-gray-500 text-sm">Monitoreo de estudiantes con riesgo académico</p>
        </div>
        {user?.role === "admin" && (
          <button
            onClick={handleGenerateAlerts}
            disabled={generatingAlerts}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {generatingAlerts ? "Generando..." : "Generar alertas"}
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20 text-gray-400">Cargando alertas...</div>
      ) : alerts.length === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-lg px-6 py-8 text-center">
          <div className="text-green-700 font-semibold">No hay alertas pendientes</div>
          <p className="text-green-600 text-sm mt-1">Todos los estudiantes están bajo control</p>
        </div>
      ) : (
        <div className="space-y-4">
          {sortedSeverities.map(severity => (
            <div key={severity}>
              <div className="mb-2 px-2">
                <span className={`text-xs font-bold uppercase tracking-wider text-gray-600`}>
                  {severity === "critico" ? "Crítico" : severity === "alto" ? "Alto" : "Medio"}
                </span>
              </div>
              <div className="space-y-3">
                {groupedAlerts[severity].map(alert => (
                  <div
                    key={alert.id}
                    className={`rounded-lg border border-gray-200 p-4 ${getSeverityStyle(severity)} hover:shadow-md transition-shadow`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-3 flex-1">
                        <span className={`text-xs font-bold px-2 py-1 rounded ${getSeverityBadgeStyle(severity)}`}>
                          {severity === "critico" ? "CRÍTICO" : severity === "alto" ? "ALTO" : "MEDIO"}
                        </span>
                        <div>
                          <button
                            onClick={() => navigate(`/ficha/${alert.estudiante_id}`)}
                            className="font-semibold text-gray-900 hover:text-blue-600 transition-colors"
                          >
                            {alert.nombre_estudiante || "Estudiante"}
                          </button>
                          <div className="text-sm text-gray-600 mt-0.5">{alert.carrera || "—"}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-gray-500">{alert.fecha || "—"}</div>
                      </div>
                    </div>

                    <div className="mb-3">
                      <div className="text-xs font-medium text-gray-600 mb-1">Tipo:</div>
                      <div className="text-sm text-gray-800">{alert.tipo_alerta || "—"}</div>
                    </div>

                    <div className="mb-4">
                      <div className="text-xs font-medium text-gray-600 mb-1">Mensaje:</div>
                      <div className="text-sm text-gray-800 leading-relaxed">{alert.mensaje || "—"}</div>
                    </div>

                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={(e) => handleMarkAsRead(alert.id, e)}
                        className="text-sm px-3 py-1.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded transition-colors"
                      >
                        Marcar como leída
                      </button>
                      {alert.estudiante_id && (
                        <button
                          onClick={() => navigate(`/ficha/${alert.estudiante_id}`)}
                          className="text-sm px-3 py-1.5 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded transition-colors"
                        >
                          Ver ficha
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
