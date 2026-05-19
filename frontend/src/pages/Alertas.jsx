import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";
import { PeriodSelector } from "../components/PeriodSelector";
import BulkInterventionModal from "../components/BulkInterventionModal";

const TIPO_LABELS = {
  inactividad: "Inactividad AVAC",
  compromiso_bajo: "Compromiso Bajo",
  nota_cero: "Nota Cero",
  tareas_bajas: "Tareas Bajas",
  calificacion_docente_pendiente: "Calificación Pendiente",
  segunda_matricula: "2da Matrícula",
  tercera_matricula: "Condicionados",
  deterioro_progresivo: "Deterioro Progresivo",
  notas_bajas_tareas: "Notas Bajas en Tareas",
};

const TIPO_ICONS = {
  inactividad: "🔕",
  compromiso_bajo: "📉",
  nota_cero: "🚨",
  tareas_bajas: "📝",
  calificacion_docente_pendiente: "⏳",
  segunda_matricula: "🔄",
  tercera_matricula: "⚠️",
  deterioro_progresivo: "📊",
  notas_bajas_tareas: "📕",
};


const ACCIONES_SUGERIDAS = {
  inactividad: "Contactar al estudiante por email/WhatsApp para verificar situación",
  compromiso_bajo: "Agendar tutoría sincrónica con el docente de la materia",
  nota_cero: "Verificar si el estudiante entregó la actividad; contactar docente",
  tareas_bajas: "Enviar recordatorio de tareas pendientes y ofrecer apoyo",
  segunda_matricula: "Programar sesión de acompañamiento académico personalizado",
  tercera_matricula: "Derivar a Bienestar Estudiantil — seguimiento prioritario",
  deterioro_progresivo: "Intervención inmediata: contactar estudiante + docente + coordinador",
};

const SEVERITY_CONFIG = {
  alto: {
    label: "ALTO",
    card: "border-l-4 border-l-red-500 bg-gradient-to-r from-red-50 to-white",
    badge: "bg-red-600 text-white",
    icon: "🔴",
    headerBg: "bg-red-100 text-red-800",
    alertBg: "bg-red-50 border-red-200",
    alertText: "text-red-700",
    order: 0,
  },
  medio: {
    label: "MEDIO",
    card: "border-l-4 border-l-orange-400 bg-gradient-to-r from-orange-50 to-white",
    badge: "bg-orange-500 text-white",
    icon: "🟠",
    headerBg: "bg-orange-100 text-orange-800",
    alertBg: "bg-orange-50 border-orange-200",
    alertText: "text-orange-700",
    order: 1,
  },
  bajo: {
    label: "BAJO",
    card: "border-l-4 border-l-yellow-400 bg-gradient-to-r from-yellow-50 to-white",
    badge: "bg-yellow-500 text-white",
    icon: "🟡",
    headerBg: "bg-yellow-100 text-yellow-800",
    alertBg: "bg-yellow-50 border-yellow-200",
    alertText: "text-yellow-700",
    order: 2,
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

/** Determina el nivel de riesgo del estudiante = máxima severidad entre sus alertas */
function getMaxSeverity(alertList) {
  const order = { alto: 0, medio: 1, bajo: 2 };
  let best = "bajo";
  for (const a of alertList) {
    if ((order[a.severidad] ?? 9) < (order[best] ?? 9)) best = a.severidad;
  }
  return best;
}

export default function Alertas() {
  const [alerts, setAlerts] = useState([]);
  const [alertCounts, setAlertCounts] = useState({ total: 0, alto: 0, medio: 0, bajo: 0, por_tipo: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [filterSeverity, setFilterSeverity] = useState("all");
  const [filterTipo, setFilterTipo] = useState("all");
  const [filterCarrera, setFilterCarrera] = useState("");
  const [filterAsignatura, setFilterAsignatura] = useState("");
  const [filterPeriodo, setFilterPeriodo] = useState("");
  const [filterCondicion, setFilterCondicion] = useState("");
  const [condicionStudentIds, setCondicionStudentIds] = useState(null);
  const [selectedStudentIds, setSelectedStudentIds] = useState(new Set());
  const [expandedStudents, setExpandedStudents] = useState(new Set());
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [carreras, setCarreras] = useState([]);
  const [asignaturas, setAsignaturas] = useState([]);
  const { user } = useAuth();
  const navigate = useNavigate();


  useEffect(() => {
    api.getCarreras().then(data => setCarreras(data || [])).catch(() => {});
  }, []);

  useEffect(() => {
    setFilterAsignatura("");
    api.getAsignaturas(filterCarrera || undefined)
      .then(data => setAsignaturas(data || []))
      .catch(() => setAsignaturas([]));
  }, [filterCarrera]);

  // Load condicion especial student IDs when filter changes
  useEffect(() => {
    if (!filterCondicion) {
      setCondicionStudentIds(null);
      return;
    }
    const params = { tipo: filterCondicion };
    if (filterPeriodo) params.periodo = filterPeriodo;
    if (filterCarrera) params.carrera = filterCarrera;
    api.getEstudiantesListado(params)
      .then(res => {
        const ids = new Set((res.estudiantes || []).map(e => e.id));
        setCondicionStudentIds(ids);
      })
      .catch(() => setCondicionStudentIds(new Set()));
  }, [filterCondicion, filterPeriodo, filterCarrera]);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = { limit: 1000 };
      if (filterCarrera) params.carrera = filterCarrera;
      if (filterAsignatura) params.asignatura = filterAsignatura;
      if (filterPeriodo) params.periodo = filterPeriodo;
      const countParams = {};
      if (filterCarrera) countParams.carrera = filterCarrera;
      if (filterAsignatura) countParams.asignatura = filterAsignatura;
      const [data, counts] = await Promise.all([
        api.getAlertsPending(params),
        api.getAlertCount(countParams),
      ]);
      setAlerts(data || []);
      setAlertCounts(counts || { total: 0, alto: 0, medio: 0, bajo: 0, por_tipo: {} });
      setSelectedStudentIds(new Set());
    } catch (e) {
      setError("No se pudieron cargar las alertas.");
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [filterCarrera, filterAsignatura, filterPeriodo]);

  useEffect(() => { loadAlerts(); }, [loadAlerts]);

  // ── Agrupar alertas por estudiante ──
  const studentGroups = useMemo(() => {
    // Apply client-side filters
    const filtered = alerts.filter(a => {
      if (filterSeverity !== "all" && a.severidad !== filterSeverity) return false;
      if (filterTipo !== "all" && a.tipo !== filterTipo) return false;
      if (condicionStudentIds !== null && !condicionStudentIds.has(a.student_id)) return false;
      return true;
    });

    // Group by student — enrich with context from first alert
    const map = new Map();
    for (const alert of filtered) {
      const sid = alert.student_id;
      if (!map.has(sid)) {
        map.set(sid, {
          student_id: sid,
          student_nombre: alert.student_nombre || "Estudiante desconocido",
          student_carrera: alert.student_carrera || "",
          dias_sin_acceso: alert.dias_sin_acceso,
          porcentaje_tareas: alert.porcentaje_tareas,
          indice_compromiso: alert.indice_compromiso,
          nivel_riesgo: alert.nivel_riesgo,
          score_recuperabilidad: alert.score_recuperabilidad,
          tiene_intervencion: alert.tiene_intervencion,
          alerts: [],
        });
      }
      map.get(sid).alerts.push(alert);
    }

    // Compute max severity + urgency score per student
    const sevScore = { alto: 30, medio: 15, bajo: 5 };
    const riesgoScore = { Alto: 25, Medio: 10, Bajo: 0 };

    const groups = [...map.values()].map(g => {
      const maxSev = getMaxSeverity(g.alerts);
      // Urgency = severity weight + alert count + inactivity + low tasks + low recovery
      let urgency = (sevScore[maxSev] || 0) + Math.min(g.alerts.length * 3, 15);
      if (g.dias_sin_acceso != null) urgency += Math.min(g.dias_sin_acceso, 30);
      if (g.porcentaje_tareas != null) urgency += Math.round((100 - g.porcentaje_tareas) * 0.2);
      if (g.score_recuperabilidad != null) urgency += Math.round((100 - g.score_recuperabilidad) * 0.15);
      urgency += (riesgoScore[g.nivel_riesgo] || 0);
      if (!g.tiene_intervencion) urgency += 10; // no one is attending yet
      return { ...g, maxSeverity: maxSev, alertCount: g.alerts.length, urgency: Math.round(urgency) };
    });

    const sevOrder = { alto: 0, medio: 1, bajo: 2 };
    groups.sort((a, b) => {
      const sa = sevOrder[a.maxSeverity] ?? 9;
      const sb = sevOrder[b.maxSeverity] ?? 9;
      if (sa !== sb) return sa - sb;
      return b.urgency - a.urgency; // within same severity, sort by urgency
    });

    return groups;
  }, [alerts, filterSeverity, filterTipo, condicionStudentIds]);

  // Group studentGroups by severity for section headers
  const groupedBySeverity = useMemo(() => {
    const grouped = {};
    for (const sg of studentGroups) {
      const sev = sg.maxSeverity;
      if (!grouped[sev]) grouped[sev] = [];
      grouped[sev].push(sg);
    }
    return grouped;
  }, [studentGroups]);

  const sortedSeverities = ["alto", "medio", "bajo"].filter(s => groupedBySeverity[s]?.length > 0);

  const handleMarkAsRead = async (id, e) => {
    e?.stopPropagation();
    try {
      await api.markAlertRead(id);
      setAlerts(prev => prev.filter(a => a.id !== id));
      setSuccess("Alerta marcada como leída");
      setTimeout(() => setSuccess(""), 3000);
    } catch (e) {
      setError("No se pudo marcar la alerta como leída.");
    }
  };

  const handleMarkStudentRead = async (studentAlerts) => {
    if (!window.confirm(`¿Marcar ${studentAlerts.length} alertas de este estudiante como leídas?`)) return;
    try {
      for (const a of studentAlerts) {
        await api.markAlertRead(a.id);
      }
      const ids = new Set(studentAlerts.map(a => a.id));
      setAlerts(prev => prev.filter(a => !ids.has(a.id)));
      setSuccess(`${studentAlerts.length} alertas marcadas como leídas`);
      setTimeout(() => setSuccess(""), 3000);
    } catch {
      setError("Error al marcar alertas.");
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
    } catch {
      setError("Error al marcar alertas.");
    }
  };



  const toggleExpand = (sid) => {
    setExpandedStudents(prev => {
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid); else next.add(sid);
      return next;
    });
  };

  const toggleSelectStudent = (sid) => {
    setSelectedStudentIds(prev => {
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid); else next.add(sid);
      return next;
    });
  };

  const toggleSelectSeverity = (severity) => {
    const sids = (groupedBySeverity[severity] || []).map(g => g.student_id);
    const allSelected = sids.every(id => selectedStudentIds.has(id));
    setSelectedStudentIds(prev => {
      const next = new Set(prev);
      sids.forEach(id => { if (allSelected) next.delete(id); else next.add(id); });
      return next;
    });
  };

  const selectedStudents = useMemo(() => {
    return studentGroups
      .filter(g => selectedStudentIds.has(g.student_id))
      .map(g => ({ id: g.student_id, nombre: g.student_nombre, carrera: g.student_carrera }));
  }, [studentGroups, selectedStudentIds]);

  const handleBulkSaved = (result) => {
    setShowBulkModal(false);
    setSelectedStudentIds(new Set());
    setSuccess(`${result.created} intervención${result.created !== 1 ? "es" : ""} registrada${result.created !== 1 ? "s" : ""}`);
    setTimeout(() => setSuccess(""), 5000);
  };

  // Counts — basados en agrupación por estudiante (severidad máxima)
  const totalAlerts = alertCounts.total || alerts.length;
  const totalStudents = studentGroups.length;

  // Contar estudiantes por su severidad máxima (no alertas individuales)
  const studentSevCounts = useMemo(() => {
    const c = { alto: 0, medio: 0, bajo: 0 };
    // Use ALL alerts (before client-side filters) to count by student max severity
    const allMap = new Map();
    for (const a of alerts) {
      if (!allMap.has(a.student_id)) allMap.set(a.student_id, []);
      allMap.get(a.student_id).push(a);
    }
    for (const [, studentAlerts] of allMap) {
      const maxSev = getMaxSeverity(studentAlerts);
      c[maxSev] = (c[maxSev] || 0) + 1;
    }
    return c;
  }, [alerts]);

  const counts = studentSevCounts;
  const tiposCounts = alertCounts.por_tipo || {};
  if (Object.keys(tiposCounts).length === 0) {
    alerts.forEach(a => { tiposCounts[a.tipo] = (tiposCounts[a.tipo] || 0) + 1; });
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alertas Académicas</h1>
          <p className="text-gray-500 text-sm">Alertas agrupadas por estudiante — el nivel de riesgo refleja la alerta más grave</p>
          <p className="text-amber-600 text-xs mt-0.5">Se actualizan automáticamente con cada ejecución del ETL</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/entregas")}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium px-3 py-1.5 rounded-lg hover:bg-blue-50 border border-blue-200 transition-colors"
          >
            Entregas pendientes
          </button>
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
        <>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div
            className={`rounded-xl border p-4 cursor-pointer transition-all ${filterSeverity === "all" ? "bg-blue-50 border-blue-300 ring-2 ring-blue-400 shadow-md" : "bg-white border-gray-200 hover:shadow-sm"}`}
            onClick={() => setFilterSeverity("all")}
          >
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">Estudiantes</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">{totalStudents}</div>
            <div className="text-[10px] text-gray-400 mt-0.5">{totalAlerts} alertas</div>
          </div>
          <div
            className={`rounded-xl border p-4 cursor-pointer transition-all ${filterSeverity === "alto" ? "bg-red-50 border-red-300 ring-2 ring-red-400 shadow-md scale-[1.02]" : "bg-white border-red-200 hover:shadow-sm"}`}
            onClick={() => setFilterSeverity(filterSeverity === "alto" ? "all" : "alto")}
          >
            <div className="text-xs font-medium text-red-600 uppercase tracking-wide">Riesgo Alto</div>
            <div className="text-2xl font-bold text-red-700 mt-1">{counts.alto}</div>
            {filterSeverity === "alto" && <div className="text-[9px] text-red-500 font-medium mt-1">✓ Filtro activo</div>}
          </div>
          <div
            className={`rounded-xl border p-4 cursor-pointer transition-all ${filterSeverity === "medio" ? "bg-orange-50 border-orange-300 ring-2 ring-orange-400 shadow-md scale-[1.02]" : "bg-white border-orange-200 hover:shadow-sm"}`}
            onClick={() => setFilterSeverity(filterSeverity === "medio" ? "all" : "medio")}
          >
            <div className="text-xs font-medium text-orange-600 uppercase tracking-wide">Riesgo Medio</div>
            <div className="text-2xl font-bold text-orange-600 mt-1">{counts.medio}</div>
            {filterSeverity === "medio" && <div className="text-[9px] text-orange-500 font-medium mt-1">✓ Filtro activo</div>}
          </div>
          <div
            className={`rounded-xl border p-4 cursor-pointer transition-all ${filterSeverity === "bajo" ? "bg-yellow-50 border-yellow-300 ring-2 ring-yellow-400 shadow-md scale-[1.02]" : "bg-white border-yellow-200 hover:shadow-sm"}`}
            onClick={() => setFilterSeverity(filterSeverity === "bajo" ? "all" : "bajo")}
          >
            <div className="text-xs font-medium text-yellow-600 uppercase tracking-wide">Riesgo Bajo</div>
            <div className="text-2xl font-bold text-yellow-600 mt-1">{counts.bajo}</div>
            {filterSeverity === "bajo" && <div className="text-[9px] text-yellow-600 font-medium mt-1">✓ Filtro activo</div>}
          </div>
        </div>


        </>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-3 mb-4 flex flex-wrap gap-3 items-end">
        <PeriodSelector value={filterPeriodo} onChange={v => setFilterPeriodo(v)} />
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Carrera</label>
          <select value={filterCarrera} onChange={e => setFilterCarrera(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Todas las carreras</option>
            {carreras.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Asignatura</label>
          <select value={filterAsignatura} onChange={e => setFilterAsignatura(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Todas las asignaturas</option>
            {asignaturas.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Tipo de Alerta</label>
          <select value={filterTipo} onChange={e => setFilterTipo(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="all">Todos los tipos</option>
            {Object.entries(tiposCounts).sort(([,a],[,b]) => b - a).map(([tipo, count]) => (
              <option key={tipo} value={tipo}>{TIPO_LABELS[tipo] || tipo} ({count})</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Condición Especial</label>
          <select
            value={filterCondicion}
            onChange={e => setFilterCondicion(e.target.value)}
            className={`border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 ${filterCondicion ? "border-purple-400 bg-purple-50 text-purple-700 font-medium" : "border-gray-300"}`}
          >
            <option value="">Todos</option>
            <option value="repitentes">Repitentes (2da matrícula)</option>
            <option value="condicionados">Condicionados (3ra matrícula)</option>
          </select>
        </div>
        <div className="ml-auto text-sm text-gray-500">
          {totalStudents} estudiante{totalStudents !== 1 ? "s" : ""} · {alerts.length} alertas
        </div>
      </div>

      {/* Selection bar */}
      {selectedStudentIds.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-4 flex items-center justify-between">
          <span className="text-sm text-blue-800 font-medium">
            {selectedStudentIds.size} estudiante{selectedStudentIds.size !== 1 ? "s" : ""} seleccionado{selectedStudentIds.size !== 1 ? "s" : ""}
          </span>
          <div className="flex gap-2">
            <button onClick={() => setSelectedStudentIds(new Set())}
              className="text-xs px-3 py-1.5 border border-blue-300 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors">
              Deseleccionar
            </button>
            <button onClick={() => setShowBulkModal(true)}
              className="text-xs px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium">
              Registrar Intervención ({selectedStudentIds.size})
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
            const config = SEVERITY_CONFIG[severity];
            const studentsInGroup = groupedBySeverity[severity] || [];
            const allGroupSelected = studentsInGroup.every(g => selectedStudentIds.has(g.student_id));

            return (
              <div key={severity}>
                {/* Severity group header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <input type="checkbox" checked={allGroupSelected}
                      onChange={() => toggleSelectSeverity(severity)} className="rounded"
                      title={`Seleccionar todos los de riesgo ${config.label}`} />
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${config.badge}`}>
                      {config.icon} RIESGO {config.label}
                    </span>
                    <span className="text-sm text-gray-500">{studentsInGroup.length} estudiante{studentsInGroup.length !== 1 ? "s" : ""}</span>
                  </div>
                  <button onClick={() => handleMarkAllRead(severity)}
                    className="text-xs text-gray-500 hover:text-gray-700 transition-colors">
                    Marcar todo como leído
                  </button>
                </div>

                {/* Student cards */}
                <div className="space-y-3">
                  {studentsInGroup.map(group => {
                    const isExpanded = expandedStudents.has(group.student_id);
                    const isSelected = selectedStudentIds.has(group.student_id);

                    return (
                      <div key={group.student_id}
                        className={`rounded-xl border ${isSelected ? "border-blue-300 ring-1 ring-blue-200" : "border-gray-200"} ${config.card} hover:shadow-md transition-all duration-200 overflow-hidden`}>

                        {/* Student header — always visible */}
                        <div className="p-4 cursor-pointer" onClick={() => toggleExpand(group.student_id)}>
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-3 min-w-0">
                              <input type="checkbox" checked={isSelected}
                                onChange={(e) => { e.stopPropagation(); toggleSelectStudent(group.student_id); }}
                                className="rounded flex-shrink-0 mt-1" />
                              <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center text-lg font-bold text-gray-600 flex-shrink-0">
                                {group.student_nombre?.charAt(0)?.toUpperCase() || "?"}
                              </div>
                              <div className="min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <button onClick={(e) => { e.stopPropagation(); navigate(`/ficha/${group.student_id}`); }}
                                    className="font-semibold text-gray-900 hover:text-blue-600 transition-colors text-left">
                                    {group.student_nombre}
                                  </button>
                                  {group.tiene_intervencion ? (
                                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 border border-blue-200">EN INTERVENCIÓN</span>
                                  ) : (
                                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 border border-gray-200">SIN ATENDER</span>
                                  )}
                                  {group.nivel_riesgo && (
                                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                      group.nivel_riesgo === "Alto" ? "bg-red-100 text-red-700" :
                                      group.nivel_riesgo === "Medio" ? "bg-orange-100 text-orange-700" :
                                      "bg-green-100 text-green-700"
                                    }`}>ML: {group.nivel_riesgo}</span>
                                  )}
                                </div>
                                {group.student_carrera && (
                                  <div className="text-xs text-gray-500 mt-0.5">{group.student_carrera}</div>
                                )}
                                {/* Context metrics bar */}
                                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5">
                                  {group.dias_sin_acceso != null && (
                                    <span className={`text-[11px] ${group.dias_sin_acceso > 14 ? "text-red-600 font-semibold" : group.dias_sin_acceso > 7 ? "text-orange-600" : "text-gray-500"}`}>
                                      {group.dias_sin_acceso === 0 ? "Activo hoy" : `${group.dias_sin_acceso}d sin acceso`}
                                    </span>
                                  )}
                                  {group.porcentaje_tareas != null && (
                                    <span className={`text-[11px] ${group.porcentaje_tareas < 30 ? "text-red-600 font-semibold" : group.porcentaje_tareas < 60 ? "text-orange-600" : "text-gray-500"}`}>
                                      Tareas: {Math.round(group.porcentaje_tareas)}%
                                    </span>
                                  )}
                                  {group.indice_compromiso != null && (
                                    <span className={`text-[11px] ${group.indice_compromiso < 0.3 ? "text-red-600 font-semibold" : group.indice_compromiso < 0.6 ? "text-orange-600" : "text-gray-500"}`}>
                                      Compromiso: {Math.round(group.indice_compromiso * 100)}%
                                    </span>
                                  )}
                                  {group.score_recuperabilidad != null && (
                                    <span className={`text-[11px] ${group.score_recuperabilidad < 30 ? "text-red-600 font-semibold" : group.score_recuperabilidad < 60 ? "text-orange-600" : "text-gray-500"}`}>
                                      Recuperab: {Math.round(group.score_recuperabilidad)}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-start gap-3 flex-shrink-0">
                              {/* Alert type pills summary */}
                              <div className="flex flex-wrap gap-1.5 justify-end max-w-xs">
                                {group.alerts.map(a => (
                                  <span key={a.id} className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border ${SEVERITY_CONFIG[a.severidad]?.alertBg || "bg-gray-50 border-gray-200"} ${SEVERITY_CONFIG[a.severidad]?.alertText || "text-gray-600"}`}>
                                    {TIPO_ICONS[a.tipo] || "⚠️"} {TIPO_LABELS[a.tipo] || a.tipo}
                                  </span>
                                ))}
                              </div>
                              <span className={`text-lg transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}>▾</span>
                            </div>
                          </div>
                        </div>

                        {/* Expanded: alert details */}
                        {isExpanded && (
                          <div className="border-t border-gray-100 bg-white/60 px-4 pb-4 pt-3 space-y-2">
                            {group.alerts.map(alert => (
                              <div key={alert.id} className={`flex items-start gap-3 p-3 rounded-lg border ${SEVERITY_CONFIG[alert.severidad]?.alertBg || "bg-gray-50 border-gray-200"}`}>
                                <span className="text-lg flex-shrink-0 mt-0.5">{TIPO_ICONS[alert.tipo] || "⚠️"}</span>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-0.5">
                                    <span className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
                                      {TIPO_LABELS[alert.tipo] || alert.tipo}
                                    </span>
                                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${SEVERITY_CONFIG[alert.severidad]?.badge || "bg-gray-400 text-white"}`}>
                                      {SEVERITY_CONFIG[alert.severidad]?.label || alert.severidad}
                                    </span>
                                    {alert.asignatura && (
                                      <span className="text-xs text-gray-500">· {alert.asignatura}</span>
                                    )}
                                    {!alert.asignatura && alert.codigo_curso && (
                                      <span className="text-xs text-gray-400 font-mono">· {alert.codigo_curso}</span>
                                    )}
                                  </div>
                                  <div className="text-sm text-gray-700 leading-relaxed">{alert.mensaje || "Sin detalle"}</div>
                                  {ACCIONES_SUGERIDAS[alert.tipo] && (
                                    <div className="mt-1.5 flex items-start gap-1.5">
                                      <span className="text-[10px] font-semibold text-blue-600 uppercase whitespace-nowrap mt-0.5">Acción:</span>
                                      <span className="text-xs text-blue-700">{ACCIONES_SUGERIDAS[alert.tipo]}</span>
                                    </div>
                                  )}
                                  <div className="text-[10px] text-gray-400 mt-1">{formatDate(alert.created_at)}</div>
                                </div>
                                <button onClick={(e) => handleMarkAsRead(alert.id, e)}
                                  className="text-xs px-2 py-1 bg-white border border-gray-300 hover:bg-gray-50 text-gray-500 rounded-lg transition-colors flex-shrink-0">
                                  ✓ Leída
                                </button>
                              </div>
                            ))}

                            {/* Student actions */}
                            <div className="flex gap-2 justify-end pt-2">
                              <button onClick={() => handleMarkStudentRead(group.alerts)}
                                className="text-xs px-3 py-1.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-600 rounded-lg transition-colors">
                                ✓ Marcar todas como leídas
                              </button>
                              <button onClick={() => navigate(`/ficha/${group.student_id}`)}
                                className="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
                                Ver ficha →
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showBulkModal && (
        <BulkInterventionModal
          selectedStudents={selectedStudents}
          periodo={filterPeriodo}
          onClose={() => setShowBulkModal(false)}
          onSaved={handleBulkSaved}
        />
      )}
    </div>
  );
}
