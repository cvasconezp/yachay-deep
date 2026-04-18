import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge, CompromisoBar, PredictionBadge } from "../components/RiskBadge";
import { PeriodSelector } from "../components/PeriodSelector";
import ExportExcelButton from "../components/ExportExcelButton";
import BulkInterventionModal from "../components/BulkInterventionModal";

const RISK_ORDER = { Alto: 0, Medio: 1, Bajo: 2 };

/** Sub-row: desglose de inactividad por asignatura */
function InactivityDetail({ studentId, periodo }) {
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.getStudentInactivity(studentId, periodo)
      .then(data => { if (!cancelled) setRows(data); })
      .catch(() => { if (!cancelled) setRows([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [studentId, periodo]);

  if (loading) return <div className="px-8 py-3 text-xs text-gray-400">Cargando desglose...</div>;
  if (!rows || rows.length === 0) return <div className="px-8 py-3 text-xs text-gray-400">Sin datos de acceso por asignatura</div>;

  return (
    <div className="px-8 py-3">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-500 border-b border-gray-100">
            <th className="text-left py-1.5 font-medium">Asignatura</th>
            <th className="text-left py-1.5 font-medium">Código</th>
            <th className="text-center py-1.5 font-medium">Días sin acceso</th>
            <th className="text-left py-1.5 font-medium">Último acceso</th>
            <th className="text-left py-1.5 font-medium">Estado</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.codigo_curso} className="border-b border-gray-50">
              <td className="py-1.5 text-gray-700">{r.asignatura || "—"}</td>
              <td className="py-1.5 text-gray-400 font-mono">{r.codigo_curso}</td>
              <td className="py-1.5 text-center">
                <span className={r.dias_sin_acceso > 14 ? "text-red-600 font-bold" : r.dias_sin_acceso > 7 ? "text-yellow-600 font-semibold" : "text-green-700"}>
                  {r.dias_sin_acceso}d
                </span>
              </td>
              <td className="py-1.5 text-gray-500">{r.ultimo_acceso_texto || "—"}</td>
              <td className="py-1.5 text-gray-500">{r.estado_avac || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Columnas disponibles para exportar
const EXPORT_COLUMNS = [
  { key: "nombre", label: "Nombre" },
  { key: "correo_institucional", label: "Correo institucional" },
  { key: "cedula", label: "Cédula" },
  { key: "carrera", label: "Carrera" },
  { key: "nivel_riesgo", label: "Nivel de riesgo" },
  { key: "dias_sin_acceso", label: "Días sin AVAC" },
  { key: "indice_compromiso", label: "Compromiso" },
  { key: "porcentaje_tareas", label: "% Tareas" },
  { key: "prob_desercion", label: "Prob. deserción" },
  { key: "prob_reprobacion", label: "Prob. reprobación" },
  { key: "total_intervenciones", label: "Intervenciones" },
];

export default function Dashboard() {
  const [students, setStudents] = useState([]);
  const [stats, setStats] = useState(null);
  const [carreras, setCarreras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtros, setFiltros] = useState({ carrera: "", asignatura: "", nivel_riesgo: "", solo_sin_intervencion: false, periodo: "" });
  const [asignaturas, setAsignaturas] = useState([]);
  const [cardFilter, setCardFilter] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [expandedId, setExpandedId] = useState(null);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const navigate = useNavigate();

  // Load asignaturas when carrera changes
  useEffect(() => {
    setFiltros(f => ({ ...f, asignatura: "" }));
    api.getAsignaturas(filtros.carrera || undefined)
      .then(data => setAsignaturas(data || []))
      .catch(() => setAsignaturas([]));
  }, [filtros.carrera]);

  const loadData = useCallback(async () => {
    if (!filtros.periodo) return;

    setLoading(true);
    setError("");
    try {
      const params = {};
      if (filtros.carrera) params.carrera = filtros.carrera;
      if (filtros.asignatura) params.asignatura = filtros.asignatura;
      if (filtros.nivel_riesgo) params.nivel_riesgo = filtros.nivel_riesgo;
      if (filtros.solo_sin_intervencion) params.solo_sin_intervencion = true;
      params.periodo = filtros.periodo;

      const statsParams = { periodo: filtros.periodo };
      if (filtros.carrera) statsParams.carrera = filtros.carrera;

      const [studentsData, statsData, carrerasData] = await Promise.all([
        api.getRiskDashboard(params),
        api.getStats(statsParams),
        api.getCarreras(),
      ]);

      const sorted = studentsData.sort((a, b) =>
        (RISK_ORDER[a.nivel_riesgo] ?? 9) - (RISK_ORDER[b.nivel_riesgo] ?? 9) ||
        (b.dias_sin_acceso ?? 0) - (a.dias_sin_acceso ?? 0)
      );

      setStudents(sorted);
      setStats(statsData);
      setCarreras(carrerasData);
      setSelectedIds(new Set());
    } catch (e) {
      console.error(e);
      setError(e.message || "No se pudieron cargar los datos.");
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  useEffect(() => { loadData(); }, [loadData]);

  const riskCounts = stats?.por_nivel_riesgo?.reduce((acc, r) => ({ ...acc, [r.nivel]: r.total }), {}) || {};

  const filteredStudents = useMemo(() => {
    if (!cardFilter) return students;
    switch (cardFilter) {
      case "alto": return students.filter(s => s.nivel_riesgo === "Alto");
      case "medio": return students.filter(s => s.nivel_riesgo === "Medio");
      case "bajo": return students.filter(s => s.nivel_riesgo === "Bajo" || !s.nivel_riesgo);
      case "intervenciones": return students.filter(s => s.total_intervenciones > 0);
      default: return students;
    }
  }, [students, cardFilter]);

  // Selection handlers
  const toggleSelect = (id, e) => {
    e.stopPropagation();
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredStudents.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredStudents.map(s => s.id)));
    }
  };

  const selectedStudents = filteredStudents.filter(s => selectedIds.has(s.id));

  const handleBulkSaved = (result) => {
    setShowBulkModal(false);
    setSelectedIds(new Set());
    setSuccessMsg(`${result.created} intervención${result.created !== 1 ? "es" : ""} registrada${result.created !== 1 ? "s" : ""}`);
    setTimeout(() => setSuccessMsg(""), 5000);
    loadData();
  };

  const cards = [
    { key: null, label: "Total monitoreados", value: stats?.total_estudiantes ?? "—", color: "text-blue-700", bg: "bg-blue-50 border-blue-200" },
    { key: "alto", label: "Riesgo Alto", value: riskCounts["Alto"] ?? 0, color: "text-red-700", bg: "bg-red-50 border-red-200" },
    { key: "medio", label: "Riesgo Medio", value: riskCounts["Medio"] ?? 0, color: "text-yellow-700", bg: "bg-yellow-50 border-yellow-200" },
    { key: "aulas", label: "Aulas virtuales", value: stats?.total_aulas_virtuales ?? 0, color: "text-purple-700", bg: "bg-purple-50 border-purple-200", noFilter: true },
    { key: "intervenciones", label: "Intervenciones", value: stats?.total_intervenciones ?? 0, color: "text-green-700", bg: "bg-green-50 border-green-200" },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard de Riesgo</h1>
          <p className="text-gray-500 text-sm">Estudiantes identificados con indicadores de riesgo académico</p>
        </div>
        <ExportExcelButton data={filteredStudents} columns={EXPORT_COLUMNS} filename="dashboard_riesgo" />
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4 mt-4">
          {error}
        </div>
      )}
      {successMsg && (
        <div className="bg-green-50 text-green-700 border border-green-200 rounded-lg px-4 py-3 text-sm mb-4 mt-4 flex items-center gap-2">
          <span>✓</span> {successMsg}
        </div>
      )}

      {/* Aviso: período sin datos de AVAC/calificaciones */}
      {!loading && stats && stats.tiene_datos_periodo === false && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl px-5 py-8 text-center my-5">
          <div className="text-3xl mb-2">📋</div>
          <h3 className="text-lg font-semibold text-amber-800 mb-1">Aún no hay datos de AVAC ni calificaciones para este período</h3>
          <p className="text-sm text-amber-700">
            Los indicadores de riesgo, compromiso y predicciones se actualizarán cuando se realice el primer scraping de AVAC y se carguen calificaciones para el período seleccionado.
          </p>
          <p className="text-xs text-amber-500 mt-2">Los estudiantes matriculados se pueden ver en la Ficha Estudiante.</p>
        </div>
      )}

      {/* Tarjetas interactivas */}
      {stats?.tiene_datos_periodo !== false && <div className="grid grid-cols-2 md:grid-cols-5 gap-3 my-5">
        {cards.map(card => {
          const isActive = !card.noFilter && cardFilter === card.key;
          const clickable = !card.noFilter && card.key;
          return (
            <div
              key={card.key ?? "total"}
              onClick={clickable ? () => setCardFilter(isActive ? null : card.key) : undefined}
              className={`rounded-xl border px-4 py-3 transition-all duration-200
                ${clickable ? "cursor-pointer" : ""}
                ${isActive ? "ring-2 ring-blue-500 shadow-md scale-[1.02]" : clickable ? "hover:shadow-sm" : ""}
                ${card.bg}`}
              title={isActive ? "Click para quitar filtro" : clickable ? `Click para filtrar por ${card.label}` : ""}
            >
              <div className={`text-2xl font-bold ${card.color}`}>{card.value}</div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mt-0.5">{card.label}</div>
              {isActive && <div className="text-[9px] text-blue-600 font-medium mt-1">✓ Filtro activo</div>}
            </div>
          );
        })}
      </div>}

      {/* Botón limpiar filtro de tarjeta */}
      {cardFilter && (
        <div className="mb-3">
          <button
            onClick={() => setCardFilter(null)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-gray-500 hover:text-red-600 hover:bg-red-50 border border-gray-200 transition-colors"
          >
            ✕ Limpiar filtro de tarjeta · Mostrando: {filteredStudents.length} de {students.length}
          </button>
        </div>
      )}

      {/* Filtros */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4 flex flex-wrap gap-3 items-end">
        <PeriodSelector
          value={filtros.periodo}
          onChange={v => setFiltros(f => ({ ...f, periodo: v }))}
        />

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Carrera</label>
          <select
            value={filtros.carrera}
            onChange={e => setFiltros(f => ({ ...f, carrera: e.target.value }))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todas las carreras</option>
            {carreras.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Asignatura</label>
          <select
            value={filtros.asignatura}
            onChange={e => setFiltros(f => ({ ...f, asignatura: e.target.value }))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todas las asignaturas</option>
            {asignaturas.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Nivel de Riesgo</label>
          <select
            value={filtros.nivel_riesgo}
            onChange={e => setFiltros(f => ({ ...f, nivel_riesgo: e.target.value }))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            <option value="Alto">Alto</option>
            <option value="Medio">Medio</option>
            <option value="Bajo">Bajo</option>
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input
            type="checkbox"
            checked={filtros.solo_sin_intervencion}
            onChange={e => setFiltros(f => ({ ...f, solo_sin_intervencion: e.target.checked }))}
            className="rounded"
          />
          Solo sin intervención
        </label>

        <div className="ml-auto text-sm text-gray-500">
          {filteredStudents.length} estudiantes
        </div>
      </div>

      {/* Selection bar */}
      {selectedIds.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-4 flex items-center justify-between">
          <span className="text-sm text-blue-800 font-medium">
            {selectedIds.size} estudiante{selectedIds.size !== 1 ? "s" : ""} seleccionado{selectedIds.size !== 1 ? "s" : ""}
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
              Registrar Intervención ({selectedIds.size})
            </button>
          </div>
        </div>
      )}

      {/* Tabla */}
      {stats?.tiene_datos_periodo !== false && <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {error ? (
          <div className="text-center py-20">
            <p className="text-red-600 font-medium mb-2">Error al cargar datos</p>
            <p className="text-gray-500 text-sm mb-4">{error}</p>
            <button onClick={loadData} className="text-sm text-blue-600 hover:text-blue-800 font-medium">Reintentar</button>
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">Cargando...</div>
        ) : filteredStudents.length === 0 ? (
          <div className="text-center py-20 text-gray-400">No hay estudiantes con los filtros seleccionados</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-3 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={selectedIds.size === filteredStudents.length && filteredStudents.length > 0}
                    onChange={toggleSelectAll}
                    className="rounded"
                    title="Seleccionar todos"
                  />
                </th>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Estudiante</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Carrera</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Riesgo</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Días sin AVAC</th>
                <th className="px-4 py-3 font-semibold text-gray-700 w-36">Compromiso</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Pred. Deserción</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Intervenciones</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Última</th>
              </tr>
            </thead>
            <tbody>
              {filteredStudents.map((s) => {
                const isExpanded = expandedId === s.id;
                return (
                  <React.Fragment key={s.id}>
                    <tr
                      onClick={() => navigate(`/ficha/${s.id}`)}
                      className={`border-b border-gray-100 cursor-pointer hover:bg-blue-50 transition-colors
                        ${selectedIds.has(s.id) ? "bg-blue-50/60" : s.nivel_riesgo === "Alto" ? "bg-red-50/30" : ""}`}
                    >
                      <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(s.id)}
                          onChange={e => toggleSelect(s.id, e)}
                          className="rounded"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{s.nombre}</div>
                        <div className="text-xs text-gray-400">{s.correo_institucional}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-600 max-w-[200px] truncate">{s.carrera || "—"}</td>
                      <td className="px-4 py-3 text-center"><RiskBadge nivel={s.nivel_riesgo} /></td>
                      <td className="px-4 py-3 text-center font-mono text-gray-700">
                        <div className="flex items-center justify-center gap-1">
                          {s.dias_sin_acceso != null
                            ? <span className={s.dias_sin_acceso > 14 ? "text-red-600 font-bold" : ""}>{Math.round(s.dias_sin_acceso)}d</span>
                            : "—"}
                          <button
                            onClick={e => { e.stopPropagation(); setExpandedId(isExpanded ? null : s.id); }}
                            className="ml-1 text-gray-400 hover:text-blue-600 transition-colors"
                            title="Ver desglose por asignatura"
                          >
                            <svg className={`w-3.5 h-3.5 transition-transform ${isExpanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                        </div>
                      </td>
                      <td className="px-4 py-3"><CompromisoBar valor={s.indice_compromiso} /></td>
                      <td className="px-4 py-3 text-center"><PredictionBadge value={s.prob_desercion} label="Deserción" /></td>
                      <td className="px-4 py-3 text-center">
                        <span className={`font-semibold ${s.total_intervenciones === 0 ? "text-gray-400" : "text-blue-600"}`}>
                          {s.total_intervenciones}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center text-xs text-gray-400">
                        {s.ultima_intervencion ? new Date(s.ultima_intervencion).toLocaleDateString("es-EC") : "—"}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-gray-50/80">
                        <td colSpan={9}>
                          <InactivityDetail studentId={s.id} periodo={filtros.periodo} />
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>}

      {/* Bulk intervention modal */}
      {showBulkModal && (
        <BulkInterventionModal
          selectedStudents={selectedStudents}
          periodo={filtros.periodo}
          onClose={() => setShowBulkModal(false)}
          onSaved={handleBulkSaved}
        />
      )}
    </div>
  );
}
