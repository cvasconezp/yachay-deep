import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";

export default function EntregasPendientes() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filtros
  const [carrera, setCarrera] = useState("");
  const [asignatura, setAsignatura] = useState("");
  const [unidad, setUnidad] = useState("");
  const [bloque, setBloque] = useState("1"); // B1 por defecto (bimestre actual)
  const [search, setSearch] = useState("");

  // Control de filas expandidas
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    loadData();
  }, [carrera, unidad, bloque]);

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
    } catch (e) {
      setError(e.message || "Error cargando datos");
    } finally {
      setLoading(false);
    }
  };

  // Extraer carreras y asignaturas únicas de los datos
  const { carreras, asignaturas } = useMemo(() => {
    if (!data?.actividades) return { carreras: [], asignaturas: [] };
    const cs = [...new Set(data.actividades.map(a => a.carrera).filter(Boolean))].sort();
    const as_ = [...new Set(data.actividades.map(a => a.asignatura).filter(Boolean))].sort();
    return { carreras: cs, asignaturas: as_ };
  }, [data]);

  // Filtrar actividades en el frontend (asignatura y búsqueda de nombre)
  const filtered = useMemo(() => {
    if (!data?.actividades) return [];
    return data.actividades.filter(a => {
      if (asignatura && a.asignatura !== asignatura) return false;
      if (search) {
        const q = search.toLowerCase();
        // Buscar en nombre de estudiantes pendientes
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

  const toggleExpanded = (key) => {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const expandAll = () => {
    const newExp = {};
    filtered.forEach(a => { newExp[`${a.codigo_curso}-${a.unidad}`] = true; });
    setExpanded(newExp);
  };

  const collapseAll = () => setExpanded({});

  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Entregas Pendientes</h1>
            <p className="text-sm text-gray-500 mt-1">
              Reporte de estudiantes que no han entregado actividades por asignatura y unidad
            </p>
          </div>
          {data?.resumen && (
            <div className="flex gap-4 text-sm">
              <div className="bg-white rounded-lg shadow-sm border px-4 py-2 text-center">
                <div className="text-2xl font-bold text-blue-600">{data.resumen.total_actividades}</div>
                <div className="text-gray-500 text-xs">Actividades</div>
              </div>
              <div className="bg-white rounded-lg shadow-sm border px-4 py-2 text-center">
                <div className="text-2xl font-bold text-red-600">{data.resumen.total_pendientes}</div>
                <div className="text-gray-500 text-xs">Entregas pendientes</div>
              </div>
            </div>
          )}
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
          <div className="w-24">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 block">Bloque</label>
            <select
              value={bloque}
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
              value={unidad}
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
              placeholder="Nombre, correo o docente..."
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

        {/* Tabla de actividades */}
        {!loading && filtered.length > 0 && (
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
                    // Fila expandida: lista de pendientes
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
      </div>
    </div>
  );
}
