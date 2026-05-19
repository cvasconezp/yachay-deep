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

/* ── Helper: genera mensaje formal de correo ── */
function buildEmailMessage(docenteName, cursos) {
  if (!cursos || cursos.length === 0) return "";
  const pendientes = cursos.filter(c => c.pendientes > 0);
  if (pendientes.length === 0) return "";

  // Capitalize name nicely
  const nombre = docenteName.split(" ").map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase()).join(" ");

  let lines = [];
  lines.push(`Estimada *${nombre}*,`);
  lines.push("");
  lines.push("Reciba un cordial saludo.");
  lines.push("");

  if (pendientes.length === 1) {
    const c = pendientes[0];
    const grupoLabel = c.grupo ? ` del grupo ${c.grupo}` : "";
    lines.push(`Por medio del presente, me permito informar que en la asignatura *${c.asignatura}* aún se registran actividades pendientes de calificación${grupoLabel}:`);
  } else {
    lines.push("Por medio del presente, me permito informar que aún se registran actividades pendientes de calificación en las siguientes asignaturas:");
  }
  lines.push("");

  for (const c of pendientes) {
    const grupoLabel = c.grupo ? `Grupo ${c.grupo}` : null;
    const acts = (c.actividades || []).filter(a => a.pendientes > 0);

    if (pendientes.length > 1) {
      lines.push(`*${c.asignatura}*${grupoLabel ? ` _(${grupoLabel})_` : ""}:`);
    }

    if (acts.length > 0) {
      if (grupoLabel && pendientes.length === 1) {
        lines.push(`_${grupoLabel}:_`);
      }
      for (const a of acts) {
        const nEst = a.estudiantes_pendientes?.length || 0;
        const plural = nEst === 1 ? "estudiante pendiente" : "estudiantes pendientes";
        lines.push(`• ${nEst} ${plural} de la *${a.actividad}*`);
      }
    } else {
      const nEst = c.estudiantes_pendientes?.length || 0;
      const plural = nEst === 1 ? "estudiante pendiente" : "estudiantes pendientes";
      lines.push(`• ${nEst} ${plural} de calificación${grupoLabel ? ` _(${grupoLabel})_` : ""}`);
    }
    lines.push("");
  }

  lines.push("Quedamos atentos y agradecemos de antemano su colaboración.");
  lines.push("");
  lines.push("Saludos cordiales.");

  return lines.join("\n");
}

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
  const [copied, setCopied] = useState(false);
  const [expandedActs, setExpandedActs] = useState({});
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
    setCopied(false);
    setExpandedActs({});
    try {
      const detail = await api.getDocenteTrackingDetalle(docente);
      setDetalleData(detail);
    } catch (e) {
      console.error("Error cargando detalle:", e);
      setDetalleData([]);
    } finally {
      setLoadingDetalle(false);
    }
  };

  const copyMessage = () => {
    const msg = buildEmailMessage(detalleDocente, detalleData);
    if (msg) {
      navigator.clipboard.writeText(msg).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2500);
      });
    }
  };

  const toggleAct = (key) => {
    setExpandedActs(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const SortIcon = ({ field }) => (
    <span className="ml-1 text-xs opacity-40">
      {sortField === field ? (sortOrder === "asc" ? "▲" : "▼") : "⇅"}
    </span>
  );

  return (
    <div className={embedded ? "" : "p-6 space-y-6 max-w-[1400px] mx-auto"}>
      {!embedded && (
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Seguimiento de Calificaciones</h1>
            <p className="text-sm text-gray-500 mt-1">Estado de calificación por docente — basado en entregas de tareas AVAC</p>
          </div>
          <ExportExcelButton data={data} columns={TRACKING_EXPORT_COLS} filename="seguimiento_docente" />
        </div>
      )}

      {/* KPI Cards */}
      {resumen && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <SummaryCard title="Docentes" value={resumen.total_docentes} />
          <SummaryCard title="Pendientes totales" value={resumen.total_pendientes} color={resumen.total_pendientes > 0 ? "red" : "green"} />
          <SummaryCard title="Promedio calif." value={`${resumen.promedio_general_calificacion}%`} />
          <SummaryCard title="Críticos" value={resumen.docentes_criticos} color={resumen.docentes_criticos > 0 ? "red" : "green"} />
          <SummaryCard title="Atención" value={resumen.docentes_en_atencion} color={resumen.docentes_en_atencion > 0 ? "yellow" : "green"} />
        </div>
      )}

      {/* Search */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            placeholder="Buscar docente o asignatura..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 bg-white"
          />
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <span className="text-xs text-gray-400">{filteredData.length} docentes</span>
      </div>

      {/* Main Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        {loading ? (
          <div className="text-center py-12 text-gray-400">Cargando seguimiento docente...</div>
        ) : error ? (
          <div className="text-center py-12 text-red-500">{error}</div>
        ) : sortedData.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            {search ? "No hay docentes que coincidan con la búsqueda" : "No hay datos de seguimiento docente disponibles"}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/60">
                <th className="text-left px-4 py-3 font-medium text-gray-600 cursor-pointer select-none" onClick={() => handleSort("docente")}>
                  Docente<SortIcon field="docente" />
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Asignaturas</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600 cursor-pointer select-none" onClick={() => handleSort("actividades_pendientes")}>
                  Por calificar<SortIcon field="actividades_pendientes" />
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-600 cursor-pointer select-none w-48" onClick={() => handleSort("porcentaje_calificacion")}>
                  Progreso<SortIcon field="porcentaje_calificacion" />
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-600">Estado</th>
              </tr>
            </thead>
            <tbody>
              {sortedData.map((d) => {
                const pct = d.porcentaje_calificacion || 0;
                return (
                  <tr
                    key={d.docente}
                    className="border-b border-gray-50 hover:bg-blue-50/40 cursor-pointer transition-colors"
                    onClick={() => openDetalle(d.docente)}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{d.docente}</div>
                      {d.correo_docente && <div className="text-xs text-gray-400">{d.correo_docente}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {d.cursos?.slice(0, 3).map((c, i) => (
                          <span key={i} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{c}</span>
                        ))}
                        {d.cursos?.length > 3 && <span className="text-xs text-gray-400">+{d.cursos.length - 3}</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`font-bold text-sm ${d.actividades_pendientes > 0 ? "text-red-600" : "text-green-600"}`}>
                        ({d.actividades_pendientes}/{d.total_tareas})
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
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

      {/* ── Modal detalle: cursos → actividades → estudiantes ── */}
      {detalleDocente && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setDetalleDocente(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[85vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{detalleDocente}</h2>
                  <p className="text-sm text-gray-500 mt-1">Pendientes por calificar — desglose por curso, grupo y actividad</p>
                </div>
                <div className="flex items-center gap-2">
                  {detalleData?.some(c => c.pendientes > 0) && (
                    <button
                      onClick={copyMessage}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                        copied
                          ? "bg-green-100 text-green-700 border border-green-200"
                          : "bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100"
                      }`}
                      title="Copiar mensaje para enviar por correo"
                    >
                      {copied ? (
                        <>
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                          Copiado
                        </>
                      ) : (
                        <>
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" /></svg>
                          Copiar mensaje
                        </>
                      )}
                    </button>
                  )}
                  <button onClick={() => setDetalleDocente(null)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none ml-2">&times;</button>
                </div>
              </div>
            </div>

            <div className="p-6 space-y-5">
              {loadingDetalle ? (
                <div className="text-center py-8 text-gray-400">Cargando detalles...</div>
              ) : detalleData?.length > 0 ? (
                detalleData.map((curso, cidx) => (
                  <div key={cidx} className="border border-gray-200 rounded-xl overflow-hidden">
                    {/* Cabecera del curso */}
                    <div className={`px-4 py-3 flex items-center justify-between ${
                      curso.pendientes > 0 ? "bg-red-50" : "bg-green-50"
                    }`}>
                      <div className="flex items-center gap-3">
                        <span className="font-semibold text-gray-800">{curso.asignatura}</span>
                        {curso.grupo && (
                          <span className="text-xs font-bold text-white bg-gray-500 px-2 py-0.5 rounded">Grupo {curso.grupo}</span>
                        )}
                        <a href={`https://avac.ups.edu.ec/grado68/course/search.php?areaids=core_course-course&q=${curso.codigo_curso}`} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="text-xs text-blue-500 hover:text-blue-700 underline bg-white px-2 py-0.5 rounded">{curso.codigo_curso}</a>
                      </div>
                      <div className="text-sm">
                        {curso.pendientes > 0 ? (
                          <span className="bg-red-100 text-red-700 px-3 py-1 rounded-full font-bold">
                            ({curso.pendientes}/{curso.total_tareas}) por calificar
                          </span>
                        ) : (
                          <span className="bg-green-100 text-green-700 px-3 py-1 rounded-full font-semibold">
                            Todo calificado ({curso.calificadas}/{curso.total_tareas})
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Actividades */}
                    {curso.actividades?.length > 0 ? (
                      <div className="divide-y divide-gray-100">
                        {curso.actividades.map((act, aidx) => {
                          const actKey = `${cidx}-${aidx}`;
                          const isExpanded = expandedActs[actKey];
                          const hasPend = act.pendientes > 0;

                          return (
                            <div key={aidx}>
                              {/* Activity header */}
                              <div
                                className={`px-4 py-2.5 flex items-center justify-between cursor-pointer hover:bg-gray-50 ${
                                  hasPend ? "" : "opacity-60"
                                }`}
                                onClick={() => hasPend && toggleAct(actKey)}
                              >
                                <div className="flex items-center gap-3">
                                  {hasPend && (
                                    <svg className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                  )}
                                  <span className={`text-sm font-medium ${hasPend ? "text-gray-800" : "text-gray-500"}`}>
                                    {act.actividad}
                                  </span>
                                </div>
                                <div className="flex items-center gap-3">
                                  {hasPend ? (
                                    <span className="text-xs font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
                                      {act.estudiantes_pendientes?.length || 0} estudiante{(act.estudiantes_pendientes?.length || 0) !== 1 ? "s" : ""} pendiente{(act.estudiantes_pendientes?.length || 0) !== 1 ? "s" : ""}
                                    </span>
                                  ) : (
                                    <span className="text-xs text-green-600">Calificado ({act.calificadas}/{act.total})</span>
                                  )}
                                </div>
                              </div>

                              {/* Student list for this activity */}
                              {isExpanded && act.estudiantes_pendientes?.length > 0 && (
                                <table className="w-full text-sm bg-gray-50/50">
                                  <thead>
                                    <tr className="border-b border-gray-100">
                                      <th className="text-left pl-12 pr-4 py-2 text-xs font-medium text-gray-500">Estudiante</th>
                                      <th className="text-center px-4 py-2 text-xs font-medium text-gray-500">Sin calificar</th>
                                      <th className="text-center px-4 py-2 text-xs font-medium text-gray-500">Última entrega</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {act.estudiantes_pendientes.map((est) => (
                                      <tr
                                        key={est.student_id}
                                        onClick={(e) => { e.stopPropagation(); navigate(`/ficha/${est.student_id}`); }}
                                        className="border-b border-gray-50 cursor-pointer hover:bg-blue-50"
                                      >
                                        <td className="pl-12 pr-4 py-2 text-gray-800">{est.nombre}</td>
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
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : curso.pendientes > 0 ? (
                      <div className="px-4 py-3 text-sm text-gray-500 italic">Hay pendientes pero no se identificaron actividades</div>
                    ) : (
                      <div className="px-4 py-3 text-sm text-green-600">Todas las entregas han sido calificadas</div>
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
