import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";
import { PeriodSelector } from "../components/PeriodSelector";
import BulkInterventionModal from "../components/BulkInterventionModal";
import { useStudentListModal } from "../components/StudentListModal";

const TIPO_LABELS = {
  inactividad: "Inactividad AVAC",
  compromiso_bajo: "Compromiso Bajo",
  nota_cero: "Nota Cero",
  tareas_bajas: "Tareas Bajas",
  calificacion_docente_pendiente: "Calificación Pendiente",
  segunda_matricula: "2da Matrícula",
  tercera_matricula: "Condicionados",
};

const TIPO_ICONS = {
  inactividad: "🔕",
  compromiso_bajo: "📉",
  nota_cero: "🚨",
  tareas_bajas: "📝",
  calificacion_docente_pendiente: "⏳",
  segunda_matricula: "🔄",
  tercera_matricula: "⚠️",
};

const SEVERITY_CONFIG = {
  critico: {
    label: "CRÍTICO",
    card: "border-l-4 border-l-red-500 bg-gradient-to-r from-red-50 to-white",
    badge: "bg-red-600 text-white",
    icon: "🔴",
    headerBg: "bg-red-100 text-red-800",
  },
  alto: {
    label: "ALTO",
    card: "border-l-4 border-l-orange-400 bg-gradient-to-r from-orange-50 to-white",
    badge: "bg-orange-500 text-white",
    icon: "🟠",
    headerBg: "bg-orange-100 text-orange-800",
  },
  medio: {
    label: "MEDIO",
    card: "border-l-4 border-l-yellow-400 bg-gradient-to-r from-yellow-50 to-white",
    badge: "bg-yellow-500 text-white",
    icon: "🟡",
    headerBg: "bg-yellow-100 text-yellow-800",
  },
};

function formatDate(isoStr) {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString("es-EC", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}

export default function Alertas() {
  const [alerts, setAlerts] = useState([]);
  const [alertCounts, setAlertCounts] = useState({ total: 0, critico: 0, alto: 0, medio: 0, por_tipo: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [generatingAlerts, setGeneratingAlerts] = useState(false);
  const [filterSeverity, setFilterSeverity] = useState("all");
  const [filterTipo, setFilterTipo] = useState("all");
  const [filterCarrera, setFilterCarrera] = useState("");
  const [filterAsignatura, setFilterAsignatura] = useState("");
  const [filterPeriodo, setFilterPeriodo] = useState("");
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [carreras, setCarreras] = useState([]);
  const [asignaturas, setAsignaturas] = useState([]);
  const { user } = useAuth();
  const navigate = useNavigate();
  const { openStudentList, StudentListModalEl } = useStudentListModal({
    periodo: filterPeriodo,
    carrera: filterCarrera,
  });

  // Load carreras on mount
  useEffect(() => {
    api.getCarreras().then(data => setCarreras(data || [])).catch(() => {});
  }, []);

  // Load asignaturas when carrera changes
  useEffect(() => {
    setFilterAsignatura("");
    api.getAsignaturas(filterCarrera || undefined)
      .then(data => setAsignaturas(data || []))
      .catch(() => setAsignaturas([]));
  }, [filterCarrera]);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = { limit: 1000 };
      if (filterCarrera) params.carrera = filterCarrera;
      if (filterAsignatura) params.asignatura = filterAsignatura;
      if (filterPeriodo) params.periodo = filterPeriodo;
      const [data, counts] = await Promise.all([
        api.getAlertsPending(params),
        api.getAlertCount(),
      ]);
      setAlerts(data || []);
      setAlertCounts(counts || { total: 0, critico: 0, alto: 0, medio: 0, por_tipo: {} });
      setSelectedIds(new Set());
    } catch (e) {
      setError("No se pudieron cargar las alertas.");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [filterCarrera, filterAsignatura, filterPeriodo]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  const handleMarkAsRead = async (id, e) => {
    e.stopPropagation();
    try {
      await api.markAlertRead(id);
      setAlerts(prev => prev.filter(a => a.id !== id));
      setSelectedIds(prev => { const next = new Set(prev); next.delete(id); return next; });
      setSuccess("Alerta marcada como leída");
      setTimeout(() => setSuccess(""), 3000);
    } catch (e) {
      setError("No se pudo marcar la alerta como leída.");
      console.error(e);
    }
  };

  const handleMarkAllRead = async (severity) => {
    const toMark = alerts.filter(a => a.severidad === severity);
    if (!window.confirm(`¿Marcar ${toMark.length} alertas de nivel ${SEVERITY_CONFIG[severity]?.label || severity} como leídas?`)) return;
    try {
      for (const a of toMark) {
        await api.markAlertRead(a.id);
      }
      setAlerts(prev => prev.filter(a => a.severidad !== severity));
      setSuccess(`${toMark.length} alertas marcadas como leídas`);
      setTimeout(() => setSuccess(""), 3000);
    } catch (e) {
      setError("Error al marcar alertas.");
    }
  };

  const handleGenerateAlerts = async () => {
    if (!window.confirm("¿Regenerar alertas? Se eliminarán las alertas pendientes actuales y se crearán nuevas basadas en los datos más recientes.")) return;
    setGeneratingAlerts(true);
    setError("");
    try {
      const result = await api.generateAlerts();
      const parts = [];
      if (result.cleaned) parts.push(`${result.cleaned} anteriores eliminadas`);
      parts.push(`${result.created || 0} nuevas generadas`);
      if (result.detail) parts.push(result.detail);
      setSuccess(parts.join(" · "));
      setTimeout(() => setSuccess(""), 8000);
      loadAlerts();
    } catch (e) {
      setError("Error al generar alertas: " + (e.message || "Intenta de nuevo"));
      console.error(e);
    } finally {
      setGeneratingAlerts(false);
    }
  };

  // Apply client-side filters (severity + tipo)
  const filteredAlerts = alerts.filter(a => {
    if (filterSeverity !== "all" && a.severidad !== filterSeverity) return false;
    if (filterTipo !== "all" && a.tipo !== filterTipo) return false;
    return true;
  });

  // Group by severity
  const severityOrder = { critico: 0, alto: 1, medio: 2 };
  const groupedAlerts = {};
  filteredAlerts.forEach(alert => {
    const severity = alert.severidad || "medio";
    if (!groupedAlerts[severity]) groupedAlerts[severity] = [];
    groupedAlerts[severity].push(alert);
  });
  const sortedSeverities = Object.keys(groupedAlerts).sort((a, b) => (severityOrder[a] ?? 9) - (severityOrder[b] ?? 9));

  // Summary counts — use backend totals (accurate, not limited by fetch)
  const counts = {
    critico: alertCounts.critico || 0,
    alto: alertCounts.alto || 0,
    medio: alertCounts.medio || 0,
  };
  const totalAlerts = alertCounts.total || alerts.length;
  const tiposCounts = alertCounts.por_tipo || {};
  // Fallback: if por_tipo is empty, count from fetched alerts
  if (Object.keys(tiposCounts).length === 0) {
    alerts.forEach(a => { tiposCounts[a.tipo] = (tiposCounts[a.tipo] || 0) + 1; });
  }

  // carreras loaded from /dashboard/carreras on mount (all system carreras)

  // Selection handlers
  const toggleSelect = (alertObj, e) => {
    e.stopPropagation();
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(alertObj.id)) next.delete(alertObj.id); else next.add(alertObj.id);
      return next;
    });
  };

  const toggleSelectSeverity = (severity) => {
    const idsInGroup = (groupedAlerts[severity] || []).map(a => a.id);
    const allSelected = idsInGroup.every(id => selectedIds.has(id));
    setSelectedIds(prev => {
      const next = new Set(prev);
      idsInGroup.forEach(id => { if (allSelected) next.delete(id); else next.add(id); });
      return next;
    });
  };

  // Get unique student objects from selected alerts
  const selectedStudents = useMemo(() => {
    const map = new Map();
    alerts.filter(a => selectedIds.has(a.id)).forEach(a => {
      if (!map.has(a.student_id)) {
        map.set(a.student_id, { id: a.student_id, nombre: a.student_nombre, carrera: a.student_carrera });
      }
    });
    return [...map.values()];
  }, [alerts, selectedIds]);

  const handleBulkSaved = (result) => {
    setShowBulkModal(false);
    setSelectedIds(new Set());
    setSuccess(`${result.created} intervención${result.created !== 1 ? "es" : ""} registrada${result.created !== 1 ? "s" : ""}`);
    setTimeout(() => setSuccess(""), 5000);
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alertas Académicas</h1>
          <p className="text-gray-500 text-sm">Alertas automáticas basadas en indicadores de riesgo estudiantil</p>
          <p className="text-amber-600 text-xs mt-0.5">Las alertas se basan en el último scraping de AVAC disponible</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/entregas")}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium px-3 py-1.5 rounded-lg hover:bg-blue-50 border border-blue-200 transition-colors"
          >
            Entregas pendientes
          </button>
          {user?.role === "admin" && (
          <button
            onClick={handleGenerateAlerts}
            disabled={generatingAlerts}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 shadow-sm"
          >
            {generatingAlerts ? (
              <><span className="animate-spin">⟳</span> Analizando...</>
            ) : (
              <><span>⚡</span> Generar alertas</>
            )}
          </button>
          )}
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4 flex items-center gap-2">
          <span>⚠️</span> {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 text-green-700 border border-green-200 rounded-lg px-4 py-3 text-sm mb-4 flex items-center gap-2">
          <span>✓</span> {success}
        </div>
      )}

      {/* Summary Cards */}
      {!loading && alerts.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-5">
          <div
            className={`rounded-xl border p-4 cursor-pointer transition-all ${filterSeverity === "all" ? "bg-blue-50 border-blue-300 ring-2 ring-blue-400 shadow-md" : "bg-white border-gray-200 hover:shadow-sm"}`}
            onClick={() => setFilterSeverity(filterSeverity === "all" ? "all" : "all")}
            title={filterSeverity !== "all" ? "Clic para quitar filtro" : ""}
          >
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">Total Pendientes</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">{totalAlerts}</div>
            {filterSeverity !== "all" && <div className="text-[9px] text-gray-400 mt-1">Clic para ver todas</div>}
          </div>
          <div
            className={`rounded-xl border p-4 cursor-pointer transition-all ${filterSeverity === "critico" ? "bg-red-50 border-red-300 ring-2 ring-red-400 shadow-md scale-[1.02]" : "bg-white border-red-200 hover:shadow-sm"}`}
            onClick={() => setFilterSeverity(filterSeverity === "critico" ? "all" : "critico")}
            title={filterSeverity === "critico" ? "Clic para quitar filtro" : "Clic para filtrar críticas"}
          >
            <div className="text-xs font-medium text-red-600 uppercase tracking-wide">Críticas</div>
            <div className="text-2xl font-bold text-red-700 mt-1">{counts.critico}</div>
            {filterSeverity === "critico" && <div className="text-[9px] text-red-500 font-medium mt-1">✓ Filtro activo</div>}
          </div>
          <div
            className={`rounded-xl border p-4 cursor-pointer transition-all ${filterSeverity === "alto" ? "bg-orange-50 border-orange-300 ring-2 ring-orange-400 shadow-md scale-[1.02]" : "bg-white border-orange-200 hover:shadow-sm"}`}
            onClick={() => setFilterSeverity(filterSeverity === "alto" ? "all" : "alto")}
            title={filterSeverity === "alto" ? "Clic para quitar filtro" : "Clic para filtrar altas"}
          >
            <div className="text-xs font-medium text-orange-600 uppercase tracking-wide">Altas</div>
            <div className="text-2xl font-bold text-orange-600 mt-1">{counts.alto}</div>
            {filterSeverity === "alto" && <div className="text-[9px] text-orange-500 font-medium mt-1">✓ Filtro activo</div>}
          </div>
          <div
            className={`rounded-xl border p-4 cursor-pointer transition-all ${filterSeverity === "medio" ? "bg-yellow-50 border-yellow-300 ring-2 ring-yellow-400 shadow-md scale-[1.02]" : "bg-white border-yellow-200 hover:shadow-sm"}`}
            onClick={() => setFilterSeverity(filterSeverity === "medio" ? "all" : "medio")}
            title={filterSeverity === "medio" ? "Clic para quitar filtro" : "Clic para filtrar medias"}
          >
            <div className="text-xs font-medium text-yellow-600 uppercase tracking-wide">Medias</div>
            <div className="text-2xl font-bold text-yellow-600 mt-1">{counts.medio}</div>
            {filterSeverity === "medio" && <div className="text-[9px] text-yellow-600 font-medium mt-1">✓ Filtro activo</div>}
          </div>
          <div
            className="bg-orange-50 rounded-xl border border-orange-200 p-4 cursor-pointer hover:ring-2 hover:ring-orange-300 hover:shadow-md transition-all"
            onClick={() => openStudentList("repitentes")}
            title="Clic para ver listado de repitentes"
          >
            <div className="flex items-center justify-between">
              <div className="text-xs font-medium text-orange-700 uppercase tracking-wide">Repitentes</div>
              <span className="text-[10px] text-orange-400">▸ ver lista</span>
            </div>
            <div className="text-2xl font-bold text-orange-700 mt-1">{"📋"}</div>
          </div>
          <div
            className="bg-purple-50 rounded-xl border border-purple-200 p-4 cursor-pointer hover:ring-2 hover:ring-purple-300 hover:shadow-md transition-all"
            onClick={() => openStudentList("condicionados")}
            title="Clic para ver listado de condicionados (3ra matrícula)"
          >
            <div className="flex items-center justify-between">
              <div className="text-xs font-medium text-purple-700 uppercase tracking-wide">Condicionados</div>
              <span className="text-[10px] text-purple-400">▸ ver lista</span>
            </div>
            <div className="text-2xl font-bold text-purple-700 mt-1">{"📋"}</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-3 mb-4 flex flex-wrap gap-3 items-end">
        <PeriodSelector
          value={filterPeriodo}
          onChange={v => setFilterPeriodo(v)}
        />

        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Carrera</label>
          <select
            value={filterCarrera}
            onChange={e => setFilterCarrera(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todas las carreras</option>
            {carreras.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Asignatura</label>
          <select
            value={filterAsignatura}
            onChange={e => setFilterAsignatura(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todas las asignaturas</option>
            {asignaturas.map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Severidad</label>
          <select
            value={filterSeverity}
            onChange={e => setFilterSeverity(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">Todas</option>
            <option value="critico">Crítico ({counts.critico})</option>
            <option value="alto">Alto ({counts.alto})</option>
            <option value="medio">Medio ({counts.medio})</option>
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Tipo de Alerta</label>
          <select
            value={filterTipo}
            onChange={e => setFilterTipo(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">Todos los tipos</option>
            {Object.entries(tiposCounts)
              .sort(([, a], [, b]) => b - a)
              .map(([tipo, count]) => (
              <option key={tipo} value={tipo}>{TIPO_LABELS[tipo] || tipo} ({count})</option>
            ))}
          </select>
        </div>

        <div className="ml-auto text-sm text-gray-500">
          {filteredAlerts.length} de {totalAlerts} alertas
          {alerts.length < totalAlerts && <span className="text-xs text-gray-400 ml-1">(mostrando {alerts.length})</span>}
        </div>
      </div>

      {/* Selection bar */}
      {selectedIds.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-4 flex items-center justify-between">
          <span className="text-sm text-blue-800 font-medium">
            {selectedIds.size} alerta{selectedIds.size !== 1 ? "s" : ""} seleccionada{selectedIds.size !== 1 ? "s" : ""}
            {" "}({selectedStudents.length} estudiante{selectedStudents.length !== 1 ? "s" : ""} único{selectedStudents.length !== 1 ? "s" : ""})
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setSelectedIds(new Set())}
              className="text-xs px-3 py-1.5 border border-blue-300 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors"
            >
              Deseleccionar
            </button>
            <button
              onClick={() => setShowBulkModal(true)}
              className="text-xs px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              Registrar Intervención ({selectedStudents.length})
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-gray-400">Cargando alertas...</div>
      ) : alerts.length === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-xl px-6 py-12 text-center">
          <div className="text-4xl mb-3">✅</div>
          <div className="text-green-700 font-semibold text-lg">No hay alertas pendientes</div>
          <p className="text-green-600 text-sm mt-1">Todos los indicadores de riesgo están bajo control</p>
        </div>
      ) : (
        <div className="space-y-6">
          {sortedSeverities.map(severity => {
            const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.medio;
            const alertsInGroup = groupedAlerts[severity];
            const allGroupSelected = alertsInGroup.every(a => selectedIds.has(a.id));

            return (
              <div key={severity}>
                {/* Severity group header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={allGroupSelected}
                      onChange={() => toggleSelectSeverity(severity)}
                      className="rounded"
                      title={`Seleccionar todas las alertas ${config.label}`}
                    />
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${config.badge}`}>
                      {config.icon} {config.label}
                    </span>
                    <span className="text-sm text-gray-500">{alertsInGroup.length} alertas</span>
                  </div>
                  {alertsInGroup.length > 1 && (
                    <button
                      onClick={() => handleMarkAllRead(severity)}
                      className="text-xs text-gray-500 hover:text-gray-700 transition-colors"
                    >
                      Marcar todas como leídas
                    </button>
                  )}
                </div>

                {/* Alert cards */}
                <div className="space-y-3">
                  {alertsInGroup.map(alert => (
                    <div
                      key={alert.id}
                      className={`rounded-xl border ${selectedIds.has(alert.id) ? "border-blue-300 ring-1 ring-blue-200" : "border-gray-200"} ${config.card} hover:shadow-md transition-all duration-200 overflow-hidden`}
                    >
                      <div className="p-4">
                        {/* Top row: checkbox + student name + date */}
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <input
                              type="checkbox"
                              checked={selectedIds.has(alert.id)}
                              onChange={e => toggleSelect(alert, e)}
                              className="rounded mt-1 flex-shrink-0"
                            />
                            <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center text-lg font-bold text-gray-600 flex-shrink-0">
                              {alert.student_nombre?.charAt(0)?.toUpperCase() || "?"}
                            </div>
                            <div>
                              <button
                                onClick={() => navigate(`/ficha/${alert.student_id}`)}
                                className="font-semibold text-gray-900 hover:text-blue-600 transition-colors text-left"
                              >
                                {alert.student_nombre || "Estudiante desconocido"}
                              </button>
                              {alert.student_carrera && (
                                <div className="text-xs text-gray-500 mt-0.5">{alert.student_carrera}</div>
                              )}
                            </div>
                          </div>
                          <div className="text-xs text-gray-400 whitespace-nowrap ml-2">
                            {formatDate(alert.created_at)}
                          </div>
                        </div>

                        {/* Alert type badge + message */}
                        <div className="flex items-start gap-2 mb-3 ml-9">
                          <span className="text-lg flex-shrink-0">{TIPO_ICONS[alert.tipo] || "⚠️"}</span>
                          <div className="flex-1">
                            <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-0.5">
                              {TIPO_LABELS[alert.tipo] || alert.tipo || "Alerta"}
                              {alert.asignatura && (
                                <span className="ml-2 font-normal normal-case text-gray-500">· {alert.asignatura}</span>
                              )}
                              {!alert.asignatura && alert.codigo_curso && (
                                <span className="ml-2 font-normal normal-case text-gray-400 font-mono">· {alert.codigo_curso}</span>
                              )}
                            </div>
                            <div className="text-sm text-gray-700 leading-relaxed">
                              {alert.mensaje || "Sin detalle disponible"}
                            </div>
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex gap-2 justify-end pt-2 border-t border-gray-100">
                          <button
                            onClick={(e) => handleMarkAsRead(alert.id, e)}
                            className="text-xs px-3 py-1.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-600 rounded-lg transition-colors"
                          >
                            ✓ Leída
                          </button>
                          {alert.student_id && (
                            <button
                              onClick={() => navigate(`/ficha/${alert.student_id}`)}
                              className="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                            >
                              Ver ficha →
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Bulk intervention modal */}
      {showBulkModal && (
        <BulkInterventionModal
          selectedStudents={selectedStudents}
          periodo={filterPeriodo}
          onClose={() => setShowBulkModal(false)}
          onSaved={handleBulkSaved}
        />
      )}

      {/* Student list modal (repitentes) */}
      {StudentListModalEl}
    </div>
  );
}
