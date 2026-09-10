import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { SummaryCard } from "../components/StatCard";
import { PeriodSelector } from "../components/PeriodSelector";
import ExportExcelButton from "../components/ExportExcelButton";
import BulkInterventionModal from "../components/BulkInterventionModal";

// Carrera preseleccionada por defecto (según convención del módulo).
const DEFAULT_CARRERA = "ADMINISTRACIÓN DE EMPRESAS";
const DEFAULT_NIVEL = "1";

// Claves especiales de ordenamiento (no colisionan con nombres de asignatura).
const SORT_NOMBRE = "__nombre__";
const SORT_PROMEDIO = "__promedio__";

export default function Grupos() {
  const [grupo, setGrupo] = useState(null);
  const [carreras, setCarreras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtros, setFiltros] = useState({
    carrera: DEFAULT_CARRERA,
    nivel: DEFAULT_NIVEL,
    periodo: "",
    grupo: "",
    condicion: "",   // "" | "repitentes" | "condicionados"
    riesgo: "",      // "" | "Alto" | "Medio" | "Bajo"
  });
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState({ key: SORT_NOMBRE, dir: "asc" });
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkOpen, setBulkOpen] = useState(false);
  const navigate = useNavigate();

  const asignaturas = grupo?.asignaturas || [];
  const estudiantes = grupo?.estudiantes || [];
  const kpis = grupo?.kpis || {};
  const notaAprob = grupo?.nota_aprobacion ?? 70;

  // Grupos (paralelos) disponibles en los datos cargados.
  const gruposDisponibles = useMemo(() => {
    const set = new Set();
    estudiantes.forEach(e => { if (e.grupo) set.add(String(e.grupo)); });
    return [...set].sort((a, b) => a.localeCompare(b, "es", { numeric: true }));
  }, [estudiantes]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (filtros.periodo) params.periodo = filtros.periodo;
      if (filtros.carrera) params.carrera = filtros.carrera;
      if (filtros.nivel) params.nivel = filtros.nivel;

      const [data, carrerasData] = await Promise.all([
        api.getGruposAnalytics(params),
        api.getCarreras(),
      ]);
      setGrupo(data);
      setCarreras(carrerasData);
      setSelectedIds(new Set());  // limpiar selección al recargar el grupo
    } catch (e) {
      setError("No se pudieron cargar los datos del grupo.");
    } finally {
      setLoading(false);
    }
  }, [filtros.periodo, filtros.carrera, filtros.nivel]);

  useEffect(() => { loadData(); }, [loadData]);

  // Reconciliar la carrera por defecto con la lista real de carreras.
  useEffect(() => {
    if (!carreras.length || !filtros.carrera) return;
    if (carreras.includes(filtros.carrera)) return;
    const q = filtros.carrera.toLowerCase();
    const match = carreras.find(
      c => c.toLowerCase() === q || c.toLowerCase().includes(q) || q.includes(c.toLowerCase())
    );
    if (match && match !== filtros.carrera) {
      setFiltros(f => ({ ...f, carrera: match }));
    }
  }, [carreras]); // eslint-disable-line react-hooks/exhaustive-deps

  // Filtros del lado del cliente: buscador + grupo + condición + riesgo.
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return estudiantes.filter(e => {
      if (q && !(e.nombre || "").toLowerCase().includes(q)) return false;
      if (filtros.grupo && String(e.grupo || "") !== filtros.grupo) return false;
      if (filtros.riesgo && e.nivel_riesgo !== filtros.riesgo) return false;
      if (filtros.condicion === "condicionados" && !e.es_tercera_matricula) return false;
      if (filtros.condicion === "repitentes" && !e.es_repitente) return false;
      return true;
    });
  }, [estudiantes, search, filtros.grupo, filtros.riesgo, filtros.condicion]);

  const sortedEstudiantes = useMemo(() => {
    const list = [...filtered];
    const { key, dir } = sort;
    const mult = dir === "asc" ? 1 : -1;
    list.sort((a, b) => {
      if (key === SORT_NOMBRE) {
        return mult * (a.nombre || "").localeCompare(b.nombre || "", "es", { sensitivity: "base" });
      }
      let va, vb;
      if (key === SORT_PROMEDIO) { va = a.promedio; vb = b.promedio; }
      else { va = a.notas?.[key]; vb = b.notas?.[key]; }
      const na = va == null, nb = vb == null;
      if (na && nb) return 0;
      if (na) return 1;
      if (nb) return -1;
      return mult * (va - vb);
    });
    return list;
  }, [filtered, sort]);

  const onSort = (key) => {
    setSort(prev => prev.key === key
      ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
      : { key, dir: key === SORT_NOMBRE ? "asc" : "desc" });
  };

  const sortIcon = (key) => {
    if (sort.key !== key) return <span className="text-gray-300 ml-1">↕</span>;
    return <span className="text-brand-dark ml-1">{sort.dir === "asc" ? "▲" : "▼"}</span>;
  };

  const notaClass = (nota) => {
    if (nota == null) return "text-gray-300";
    return nota < notaAprob ? "text-red-600" : "text-green-600";
  };

  // ── Selección de filas ──
  const toggleSelect = (sid) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(sid) ? next.delete(sid) : next.add(sid);
      return next;
    });
  };
  const allVisibleSelected = sortedEstudiantes.length > 0 &&
    sortedEstudiantes.every(e => selectedIds.has(e.student_id));
  const toggleSelectAllVisible = () => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (allVisibleSelected) sortedEstudiantes.forEach(e => next.delete(e.student_id));
      else sortedEstudiantes.forEach(e => next.add(e.student_id));
      return next;
    });
  };
  const selectedStudents = useMemo(() => (
    estudiantes
      .filter(e => selectedIds.has(e.student_id))
      .map(e => ({ id: e.student_id, nombre: e.nombre, carrera: filtros.carrera || grupo?.carrera || "" }))
  ), [estudiantes, selectedIds, filtros.carrera, grupo]);

  // Exportación: nombre + grupo + condición + una columna por asignatura + promedio.
  const exportCols = useMemo(() => ([
    { key: "nombre", label: "Estudiante" },
    { key: "grupo", label: "Grupo" },
    { key: "nivel_riesgo", label: "Nivel Riesgo" },
    { key: "condicion", label: "Condición" },
    ...asignaturas.map(a => ({ key: a, label: a })),
    { key: "promedio", label: "Promedio" },
  ]), [asignaturas]);

  const exportData = useMemo(() => (
    sortedEstudiantes.map(e => ({
      nombre: e.nombre,
      grupo: e.grupo || "",
      nivel_riesgo: e.nivel_riesgo || "",
      condicion: e.es_tercera_matricula ? "3ra matrícula" : e.es_repitente ? "2da matrícula" : "",
      ...Object.fromEntries(asignaturas.map(a => [a, e.notas?.[a] ?? ""])),
      promedio: e.promedio ?? "",
    }))
  ), [sortedEstudiantes, asignaturas]);

  const selectClass = "border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analítica de Grupos</h1>
          <p className="text-gray-500 text-sm">
            Vista pivote del grupo (período · carrera · nivel): una fila por estudiante, una columna por asignatura, con la nota final en cada celda
          </p>
        </div>
        <ExportExcelButton
          data={exportData}
          columns={exportCols}
          filename="analitica_grupos"
          reportTitle="Analítica de Grupos"
        />
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {/* KPIs (mismo estilo que Asignaturas) */}
      {!loading && estudiantes.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <SummaryCard label="Total estudiantes del grupo" value={kpis.total_estudiantes ?? 0} color="blue" />
          <SummaryCard label="Asignaturas" value={kpis.total_asignaturas ?? 0} color="blue" />
          <SummaryCard label="Promedio del grupo" value={kpis.promedio_grupo ?? "—"} color="yellow" />
          <SummaryCard label="Estudiantes en riesgo alto" value={kpis.estudiantes_riesgo_alto ?? 0} color="red" />
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
            onChange={e => setFiltros(f => ({ ...f, carrera: e.target.value, grupo: "" }))}
            className={`${selectClass} min-w-[220px]`}
          >
            <option value="">Todas las carreras</option>
            {filtros.carrera && !carreras.includes(filtros.carrera) && (
              <option value={filtros.carrera}>{filtros.carrera}</option>
            )}
            {carreras.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Nivel</label>
          <select
            value={filtros.nivel}
            onChange={e => setFiltros(f => ({ ...f, nivel: e.target.value, grupo: "" }))}
            className={selectClass}
          >
            <option value="">Todos</option>
            {[1,2,3,4,5,6,7,8].map(n => <option key={n} value={n}>Nivel {n}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Grupo</label>
          <select
            value={filtros.grupo}
            onChange={e => setFiltros(f => ({ ...f, grupo: e.target.value }))}
            className={selectClass}
            disabled={gruposDisponibles.length === 0}
            title={gruposDisponibles.length <= 1 ? "Esta carrera/nivel tiene un solo grupo" : "Filtrar por grupo (paralelo)"}
          >
            <option value="">Todos</option>
            {gruposDisponibles.map(g => <option key={g} value={g}>Grupo {g}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Condición especial</label>
          <select
            value={filtros.condicion}
            onChange={e => setFiltros(f => ({ ...f, condicion: e.target.value }))}
            className={`${selectClass} ${filtros.condicion ? "border-purple-400 bg-purple-50 text-purple-700 font-medium" : ""}`}
          >
            <option value="">Todos</option>
            <option value="repitentes">Repitentes (2da matrícula)</option>
            <option value="condicionados">Condicionados (3ra matrícula)</option>
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Riesgo</label>
          <select
            value={filtros.riesgo}
            onChange={e => setFiltros(f => ({ ...f, riesgo: e.target.value }))}
            className={selectClass}
          >
            <option value="">Todos</option>
            <option value="Alto">Alto</option>
            <option value="Medio">Medio</option>
            <option value="Bajo">Bajo</option>
          </select>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <input
            type="text"
            placeholder="Buscar estudiante..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-500">
            {sortedEstudiantes.length} estudiantes
          </span>
        </div>
      </div>

      {/* Barra de selección → registrar intervención */}
      {selectedIds.size > 0 && (
        <div className="bg-purple-50 border border-purple-200 rounded-xl px-4 py-3 mb-3 flex items-center gap-4 flex-wrap">
          <span className="text-sm text-purple-800 font-medium">
            {selectedIds.size} estudiante{selectedIds.size !== 1 ? "s" : ""} seleccionado{selectedIds.size !== 1 ? "s" : ""}
          </span>
          <button
            onClick={() => setBulkOpen(true)}
            className="bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors"
          >
            🤝 Registrar Intervención ({selectedIds.size})
          </button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="text-sm text-purple-700 hover:text-purple-900 underline ml-auto"
          >
            Limpiar selección
          </button>
        </div>
      )}

      {/* Tabla pivote */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">Cargando...</div>
        ) : estudiantes.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-3xl mb-2 text-gray-300">👥</div>
            <div className="text-sm text-gray-400">No hay datos para el grupo seleccionado</div>
            <p className="text-xs text-gray-300 mt-1">Ajusta período, carrera o nivel. Los datos aparecerán cuando se carguen calificaciones.</p>
          </div>
        ) : (
          <div className="overflow-auto max-h-[65vh]">
            <table className="text-sm border-collapse">
              <thead>
                <tr>
                  {/* Primera columna congelada (arriba e izquierda) */}
                  <th
                    className="sticky left-0 top-0 z-30 bg-gray-50 text-left px-3 py-3 font-semibold text-gray-700 whitespace-nowrap border-r border-b border-gray-200 min-w-[260px]"
                  >
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={allVisibleSelected}
                        onChange={toggleSelectAllVisible}
                        className="rounded cursor-pointer"
                        title="Seleccionar todos los visibles"
                      />
                      <span
                        onClick={() => onSort(SORT_NOMBRE)}
                        className="cursor-pointer select-none hover:text-brand-dark"
                        title="Ordenar por nombre (A-Z / Z-A)"
                      >
                        Estudiante {sortIcon(SORT_NOMBRE)}
                      </span>
                    </div>
                  </th>
                  {asignaturas.map(a => (
                    <th
                      key={a}
                      onClick={() => onSort(a)}
                      className="sticky top-0 z-20 bg-gray-50 px-3 py-3 font-semibold text-gray-700 cursor-pointer select-none text-center whitespace-nowrap hover:bg-gray-100 border-b border-gray-200 min-w-[110px] max-w-[180px]"
                      title={`${a} — ordenar por nota (mayor→menor / menor→mayor)`}
                    >
                      <span className="block truncate max-w-[160px] mx-auto">{a}</span>
                      <span className="text-[10px] font-normal text-gray-400">nota {sortIcon(a)}</span>
                    </th>
                  ))}
                  <th
                    onClick={() => onSort(SORT_PROMEDIO)}
                    className="sticky top-0 z-20 bg-gray-50 px-3 py-3 font-semibold text-gray-700 cursor-pointer select-none text-center whitespace-nowrap hover:bg-gray-100 border-b border-l border-gray-200 min-w-[110px]"
                    title="Ordenar por promedio (mayor→menor / menor→mayor)"
                  >
                    Promedio {sortIcon(SORT_PROMEDIO)}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedEstudiantes.map((e) => {
                  const isSel = selectedIds.has(e.student_id);
                  return (
                    <tr
                      key={e.student_id}
                      className={`border-b border-gray-100 transition-colors group ${isSel ? "bg-purple-50/60" : "hover:bg-blue-50"}`}
                    >
                      {/* Nombre — congelado, con checkbox */}
                      <td className={`sticky left-0 z-10 px-3 py-2.5 border-r border-gray-200 min-w-[260px] ${isSel ? "bg-purple-50" : "bg-white group-hover:bg-blue-50"}`}>
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isSel}
                            onChange={(ev) => { ev.stopPropagation(); toggleSelect(e.student_id); }}
                            onClick={(ev) => ev.stopPropagation()}
                            className="rounded cursor-pointer flex-shrink-0"
                          />
                          <div
                            className="cursor-pointer min-w-0"
                            onClick={() => navigate(`/ficha/${e.student_id}`)}
                            title="Abrir ficha del estudiante"
                          >
                            <div className="font-medium text-gray-900 truncate max-w-[210px]">{e.nombre || "—"}</div>
                            <div className="flex items-center gap-1 mt-0.5">
                              {e.grupo && <span className="text-[10px] text-gray-400">G{e.grupo}</span>}
                              {e.es_tercera_matricula && (
                                <span className="text-[10px] bg-purple-100 text-purple-700 px-1 rounded font-semibold">3ra</span>
                              )}
                              {e.es_repitente && (
                                <span className="text-[10px] bg-orange-100 text-orange-700 px-1 rounded font-semibold">2da</span>
                              )}
                              {e.nivel_riesgo === "Alto" && (
                                <span className="text-[10px] text-red-600 font-semibold">riesgo alto</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      {asignaturas.map(a => {
                        const nota = e.notas?.[a];
                        return (
                          <td key={a} className="px-3 py-2.5 text-center">
                            <span className={`font-mono font-semibold ${notaClass(nota)}`}>
                              {nota != null ? nota : "—"}
                            </span>
                          </td>
                        );
                      })}
                      <td className="px-3 py-2.5 text-center border-l border-gray-100">
                        <span className={`font-mono font-bold ${notaClass(e.promedio)}`}>
                          {e.promedio != null ? e.promedio : "—"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {bulkOpen && selectedStudents.length > 0 && (
        <BulkInterventionModal
          selectedStudents={selectedStudents}
          periodo={filtros.periodo}
          onClose={() => setBulkOpen(false)}
          onSaved={() => { setBulkOpen(false); setSelectedIds(new Set()); }}
        />
      )}
    </div>
  );
}
