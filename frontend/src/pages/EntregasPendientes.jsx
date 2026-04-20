import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import BulkInterventionModal from "../components/BulkInterventionModal";

export default function EntregasPendientes() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Pestañas
  const [tab, setTab] = useState("asignatura"); // "asignatura" | "estudiante"

  // Filtros — null = pendiente de defaults del backend
  const [carrera, setCarrera] = useState("");
  const [asignatura, setAsignatura] = useState("");
  const [unidad, setUnidad] = useState(null);
  const [bloque, setBloque] = useState(null);
  const [search, setSearch] = useState("");
  const [defaultsLoaded, setDefaultsLoaded] = useState(false);

  // Control de filas expandidas (vista asignatura)
  const [expanded, setExpanded] = useState({});

  // Selección de estudiantes (vista estudiante)
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [showBulkModal, setShowBulkModal] = useState(false);

  // Primera carga: obtener defaults del backend (bloque y unidad actual)
  useEffect(() => {
    (async () => {
      try {
        const result = await api.getEntregasPendientes({});
        const defaults = result?.defaults || {};
        setBloque(defaults.bloque_actual || "1");
        setUnidad(defaults.unidad_actual || "");
        setDefaultsLoaded(true);
      } catch {
        setBloque("1");
        setUnidad("");
        setDefaultsLoaded(true);
      }
    })();
  }, []);

  useEffect(() => {
    if (defaultsLoaded) loadData();
  }, [carrera, unidad, bloque, defaultsLoaded]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (carrera) params.carrera = carrera;
      if (unidad) params.unidad = unidad;
      if (bloque) params.bloque = bloque;
      const result = await api.getEntregasPendientes(params);
      setData(result);
      setSelectedIds(new Set());
    } catch (e) {
      setError(e.message || "Error cargando datos");
    } finally {
      setLoading(false);
    }
  };

  // Extraer carreras y asignaturas únicas
  const { carreras, asignaturas } = useMemo(() => {
    if (!data?.actividades) return { carreras: [], asignaturas: [] };
    const cs = [...new Set(data.actividades.map(a => a.carrera).filter(Boolean))].sort();
    const as_ = [...new Set(data.actividades.map(a => a.asignatura).filter(Boolean))].sort();
    return { carreras: cs, asignaturas: as_ };
  }, [data]);

  // Filtrar actividades (asignatura y búsqueda)
  const filtered = useMemo(() => {
    if (!data?.actividades) return [];
    return data.actividades.filter(a => {
      if (asignatura && a.asignatura !== asignatura) return false;
      if (search) {
        const q = search.toLowerCase();
        const matchStudent = a.pendientes?.some(p =>
          p.nombre.toLowerCase().includes(q) || p.correo.toLowerCase().includes(q)
        );
        const matchAsig = a.asignatura?.toLowerCase().includes(q);
        const matchDocente = a.docente?.toLowerCase().includes(q);
        if (!matchStudent && !matchAsig && !matchDocente) return false;
      }
      return true;
    });
  }, [data, asignatura, search]);

  // ── Vista por estudiante: consolidar pendientes por estudiante ──
  const studentView = useMemo(() => {
    if (!filtered.length) return [];

    const map = {}; // student_id -> { ...student, pendientes: [{asignatura, unidad, docente}] }
    for (const act of filtered) {
      if (!act.pendientes) continue;
      for (const p of act.pendientes) {
        if (!map[p.student_id]) {
          map[p.student_id] = {
            student_id: p.student_id,
            nombre: p.nombre,
            correo: p.correo,
            pendientes: [],
          };
        }
        map[p.student_id].pendientes.push({
          asignatura: act.asignatura,
          unidad: act.unidad,
          docente: act.docente,
          codigo_curso: act.codigo_curso,
        });
      }
    }

    return Object.values(map).sort((a, b) => b.pendientes.length - a.pendientes.length);
  }, [filtered]);

  // Filtrar vista estudiante por búsqueda
  const filteredStudents = useMemo(() => {
    if (!search) return studentView;
    const q = search.toLowerCase();
    return studentView.filter(s =>
      s.nombre.toLowerCase().includes(q) ||
      s.correo.toLowerCase().includes(q) ||
      s.pendientes.some(p => p.asignatura?.toLowerCase().includes(q) || p.docente?.toLowerCase().includes(q))
    );
  }, [studentView, search]);

  const toggleExpanded = (key) => {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const expandAll = () => {
    if (tab === "asignatura") {
      const newExp = {};
      filtered.forEach(a => { newExp[`${a.codigo_curso}-${a.unidad}`] = true; });
      setExpanded(newExp);
    } else {
      const newExp = {};
      filteredStudents.forEach(s => { newExp[`stu-${s.student_id}`] = true; });
      setExpanded(newExp);
    }
  };

  const collapseAll = () => setExpanded({});

  // ── Selección de estudiantes ──
  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    setSelectedIds(new Set(filteredStudents.map(s => s.student_id)));
  };

  const selectNone = () => setSelectedIds(new Set());

  const selectedStudentsForModal = useMemo(() => {
    return filteredStudents
      .filter(s => selectedIds.has(s.student_id))
      .map(s => ({ id: s.student_id, nombre: s.nombre }));
  }, [filteredStudents, selectedIds]);

  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Entregas Pendientes</h1>
            <p className="text-sm text-gray-500 mt-1">
              Identifica estudiantes que no entregaron actividades para hacer acompañamiento
            </p>
          </div>
          {data?.resumen && (
            <div className="flex gap-4 text-sm">
              <div className="bg-white rounded-lg shadow-sm border px-4 py-2 text-center">
                <div className="text-2xl font-bold text-blue-600">{data.resumen.total_actividades}</div>
                <div className="text-gray-500 text-xs">Actividades</div>
              </div>
              <div className="bg-white rounded-lg shadow-sm border px-4 py-2 text-center">
                <div className="text-2xl font-bold text-orange-600">{studentView.length}</div>
                <div className="text-gray-500 text-xs">Estudiantes</div>
              </div>
              <div className="bg-white rounded-lg shadow-sm border px-4 py-2 text-center">
                <div className="text-2xl font-bold text-red-600">{data.resumen.total_pendientes}</div>
                <div className="text-gray-500 text-xs">Entregas pendientes</div>
              </div>
            </div>
          )}
        </div>

        {/* Pestañas */}
        <div className="flex gap-1 mb-4">
          <button
            onClick={() => setTab("asignatura")}
            className={`px-4 py-2 rounded-t-lg text-sm font-semibold transition-colors ${tab === "asignatura" ? "bg-white text-blue-700 border border-b-white shadow-sm -mb-px relative z-10" : "bg-gray-100 text-gray-500 hover:text-gray-700 border border-transparent"}`}
          >
            Por asignatura
          </button>
          <button
            onClick={() => setTab("estudiante")}
            className={`px-4 py-2 rounded-t-lg text-sm font-semibold transition-colors ${tab === "estudiante" ? "bg-white text-blue-700 border border-b-white shadow-sm -mb-px relative z-10" : "bg-gray-100 text-gray-500 hover:text-gray-700 border border-transparent"}`}
          >
            Por estudiante
            {studentView.length > 0 && <span className="ml-1.5 bg-red-100 text-red-700 text-xs font-bold px-1.5 py-0.5 rounded-full">{studentView.length}</span>}
          </button>
        </div>

        {/* Filtros */}
        <div className="bg-white rounded-xl shadow-sm border p-4 mb-4 flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[180px]">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">Carrera</label>
            <select
              value={carrera}
              onChange={e => setCarrera(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="">Todas las carreras</option>
              {carreras.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          {tab === "asignatura" && (
            <div className="flex-1 min-w-[180px]">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">Asignatura</label>
              <select
                value={asignatura}
                onChange={e => setAsignatura(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                <option value="">Todas las asignaturas</option>
                {asignaturas.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          )}
          <div className="w-24">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">Bloque</label>
            <select
              value={bloque || ""}
              onChange={e => setBloque(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="">Todos</option>
              <option value="1">B1</option>
              <option value="2">B2</option>
            </select>
          </div>
          <div className="w-24">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">Unidad</label>
            <select
              value={unidad || ""}
              onChange={e => setUnidad(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="">Todas</option>
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="3">3</option>
              <option value="4">4</option>
            </select>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">Buscar</label>
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Nombre, correo, asignatura o docente..."
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex gap-1">
            <button onClick={expandAll} className="text-xs text-blue-600 hover:text-blue-800 px-2 py-2 rounded hover:bg-blue-50" title="Expandir todo">
              ▼ Expandir
            </button>
            <button onClick={collapseAll} className="text-xs text-gray-500 hover:text-gray-700 px-2 py-2 rounded hover:bg-gray-50" title="Colapsar todo">
              ▲ Colapsar
            </button>
          </div>
        </div>

        {/* Barra de selección (vista estudiante) */}
        {tab === "estudiante" && filteredStudents.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border p-3 mb-4 flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={selectedIds.size === filteredStudents.length && filteredStudents.length > 0}
                onChange={e => e.target.checked ? selectAll() : selectNone()}
                className="rounded"
              />
              <span className="text-sm text-gray-600">
                {selectedIds.size > 0
                  ? <><strong>{selectedIds.size}</strong> seleccionado{selectedIds.size !== 1 ? "s" : ""}</>
                  : "Seleccionar todos"
                }
              </span>
            </div>
            {selectedIds.size > 0 && (
              <>
                <button
                  onClick={() => setShowBulkModal(true)}
                  className="bg-blue-600 text-white text-sm font-semibold px-4 py-1.5 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Registrar intervención ({selectedIds.size})
                </button>
                <button
                  onClick={selectNone}
                  className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-50"
                >
                  Limpiar selección
                </button>
              </>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="text-center py-12 text-gray-400">
            <div className="text-3xl mb-2">⏳</div>
            Cargando entregas...
          </div>
        )}

        {/* Sin datos */}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <div className="text-3xl mb-2">📋</div>
            No hay datos de entregas para los filtros seleccionados
          </div>
        )}

        {/* ═══ PESTAÑA: POR ASIGNATURA ═══ */}
        {!loading && filtered.length > 0 && tab === "asignatura" && (
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-4 py-3 font-semibold text-gray-600 w-8"></th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Asignatura</th>
                  <th className="text-left px-3 py-3 font-semibold text-gray-600">Docente</th>
                  <th className="text-center px-3 py-3 font-semibold text-gray-600 w-16">Unidad</th>
                  <th className="text-center px-3 py-3 font-semibold text-gray-600 w-20">Entregaron</th>
                  <th className="text-center px-3 py-3 font-semibold text-gray-600 w-20">Pendientes</th>
                  <th className="px-3 py-3 font-semibold text-gray-600 w-32">% Entrega</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((act) => {
                  const key = `${act.codigo_curso}-${act.unidad}`;
                  const isExpanded = expanded[key];
                  const pctColor = act.pct_entrega >= 80 ? "bg-green-500" : act.pct_entrega >= 60 ? "bg-yellow-400" : "bg-red-500";
                  const rowColor = act.no_entregaron === 0 ? "" : act.pct_entrega < 60 ? "bg-red-50/50" : "";

                  return [
                    <tr
                      key={key}
                      className={`border-b border-gray-100 hover:bg-blue-50/30 cursor-pointer transition-colors ${rowColor}`}
                      onClick={() => act.no_entregaron > 0 && toggleExpanded(key)}
                    >
                      <td className="px-4 py-2.5 text-gray-400">
                        {act.no_entregaron > 0 && (
                          <span className={`inline-block transition-transform ${isExpanded ? "rotate-90" : ""}`}>▶</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="font-medium text-gray-800">{act.asignatura}</div>
                        {act.carrera && <div className="text-xs text-gray-400">{act.carrera}</div>}
                      </td>
                      <td className="px-3 py-2.5 text-gray-600 text-xs">{act.docente || "—"}</td>
                      <td className="px-3 py-2.5 text-center">
                        <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2 py-0.5 rounded-full">
                          U{act.unidad}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-center text-green-700 font-semibold">
                        {act.entregaron}/{act.total_estudiantes}
                      </td>
                      <td className="px-3 py-2.5 text-center">
                        {act.no_entregaron > 0 ? (
                          <span className="bg-red-100 text-red-700 text-xs font-bold px-2 py-0.5 rounded-full">
                            {act.no_entregaron}
                          </span>
                        ) : (
                          <span className="text-green-600 text-xs font-bold">✓</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${pctColor}`} style={{ width: `${act.pct_entrega}%` }} />
                          </div>
                          <span className="text-xs font-mono text-gray-500 w-10 text-right">{act.pct_entrega}%</span>
                        </div>
                      </td>
                    </tr>,
                    isExpanded && act.pendientes?.length > 0 && (
                      <tr key={`${key}-detail`}>
                        <td colSpan={7} className="bg-red-50/30 px-4 py-0">
                          <div className="py-2 pl-8">
                            <div className="text-xs font-semibold text-red-700 mb-2 uppercase tracking-wide">
                              Estudiantes sin entregar — {act.asignatura} · Unidad {act.unidad}
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-1.5">
                              {act.pendientes.map((p) => (
                                <div
                                  key={p.student_id}
                                  className="flex items-center gap-2 bg-white rounded-lg border border-red-100 px-3 py-1.5 hover:border-blue-300 cursor-pointer transition-colors"
                                  onClick={(e) => { e.stopPropagation(); navigate(`/ficha/${p.student_id}`); }}
                                >
                                  <span className="text-red-400 text-xs">●</span>
                                  <div className="flex-1 min-w-0">
                                    <div className="text-xs font-medium text-gray-800 truncate">{p.nombre}</div>
                                    <div className="text-[10px] text-gray-400 truncate">{p.correo}</div>
                                  </div>
                                  <span className="text-[10px] text-gray-300 shrink-0">→</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
                      </tr>
                    ),
                  ];
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* ═══ PESTAÑA: POR ESTUDIANTE ═══ */}
        {!loading && tab === "estudiante" && filteredStudents.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="w-10 px-3 py-3"></th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600 w-8"></th>
                  <th className="text-left px-4 py-3 font-semibold text-gray-600">Estudiante</th>
                  <th className="text-left px-3 py-3 font-semibold text-gray-600">Correo</th>
                  <th className="text-center px-3 py-3 font-semibold text-gray-600 w-28">Pendientes</th>
                  <th className="text-left px-3 py-3 font-semibold text-gray-600">Asignaturas</th>
                </tr>
              </thead>
              <tbody>
                {filteredStudents.map((stu) => {
                  const key = `stu-${stu.student_id}`;
                  const isExpanded = expanded[key];
                  const isSelected = selectedIds.has(stu.student_id);
                  const severity = stu.pendientes.length >= 3 ? "bg-red-50/50" : stu.pendientes.length >= 2 ? "bg-orange-50/50" : "";

                  // Agrupar pendientes por asignatura para mostrar resumen
                  const asigResumen = {};
                  for (const p of stu.pendientes) {
                    if (!asigResumen[p.asignatura]) asigResumen[p.asignatura] = [];
                    asigResumen[p.asignatura].push(p.unidad);
                  }

                  return [
                    <tr
                      key={key}
                      className={`border-b border-gray-100 hover:bg-blue-50/30 cursor-pointer transition-colors ${severity}`}
                      onClick={() => toggleExpanded(key)}
                    >
                      <td className="px-3 py-2.5 text-center" onClick={e => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(stu.student_id)}
                          className="rounded"
                        />
                      </td>
                      <td className="px-4 py-2.5 text-gray-400">
                        <span className={`inline-block transition-transform ${isExpanded ? "rotate-90" : ""}`}>▶</span>
                      </td>
                      <td className="px-4 py-2.5">
                        <button
                          className="font-medium text-blue-700 hover:text-blue-900 hover:underline text-left"
                          onClick={(e) => { e.stopPropagation(); navigate(`/ficha/${stu.student_id}`); }}
                        >
                          {stu.nombre}
                        </button>
                      </td>
                      <td className="px-3 py-2.5 text-gray-500 text-xs">{stu.correo}</td>
                      <td className="px-3 py-2.5 text-center">
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${stu.pendientes.length >= 3 ? "bg-red-100 text-red-700" : stu.pendientes.length >= 2 ? "bg-orange-100 text-orange-700" : "bg-yellow-100 text-yellow-700"}`}>
                          {stu.pendientes.length} actividad{stu.pendientes.length !== 1 ? "es" : ""}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(asigResumen).map(([asig, units]) => (
                            <span key={asig} className="inline-flex items-center bg-gray-100 text-gray-700 text-[10px] px-1.5 py-0.5 rounded" title={`${asig}: Unidad ${units.join(", ")}`}>
                              {asig.length > 25 ? asig.slice(0, 25) + "…" : asig}
                              <span className="ml-1 text-blue-600 font-bold">U{units.join(",")}</span>
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>,
                    isExpanded && (
                      <tr key={`${key}-detail`}>
                        <td colSpan={6} className="bg-orange-50/30 px-4 py-0">
                          <div className="py-3 pl-14">
                            <div className="text-xs font-semibold text-orange-700 mb-2 uppercase tracking-wide">
                              Actividades pendientes de {stu.nombre}
                            </div>
                            <div className="space-y-1.5">
                              {stu.pendientes.map((p, i) => (
                                <div key={i} className="flex items-center gap-3 bg-white rounded-lg border border-orange-100 px-4 py-2">
                                  <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2 py-0.5 rounded-full shrink-0">
                                    U{p.unidad}
                                  </span>
                                  <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium text-gray-800">{p.asignatura}</div>
                                    {p.docente && <div className="text-xs text-gray-400">{p.docente}</div>}
                                  </div>
                                </div>
                              ))}
                            </div>
                            <button
                              className="mt-2 text-xs text-blue-600 hover:text-blue-800 font-semibold"
                              onClick={(e) => { e.stopPropagation(); navigate(`/ficha/${stu.student_id}`); }}
                            >
                              Ver ficha completa →
                            </button>
                          </div>
                        </td>
                      </tr>
                    ),
                  ];
                })}
              </tbody>
            </table>
          </div>
        )}

        {!loading && tab === "estudiante" && filteredStudents.length === 0 && filtered.length > 0 && (
          <div className="text-center py-12 text-gray-400">
            <div className="text-3xl mb-2">✅</div>
            Todos los estudiantes entregaron sus actividades
          </div>
        )}
      </div>

      {/* Modal de intervención masiva */}
      {showBulkModal && (
        <BulkInterventionModal
          selectedStudents={selectedStudentsForModal}
          periodo=""
          onClose={() => setShowBulkModal(false)}
          onSaved={() => {
            setShowBulkModal(false);
            setSelectedIds(new Set());
          }}
        />
      )}
    </div>
  );
}
