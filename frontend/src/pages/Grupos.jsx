import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { SummaryCard } from "../components/StatCard";
import { PeriodSelector } from "../components/PeriodSelector";
import ExportExcelButton from "../components/ExportExcelButton";

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
  });
  const [search, setSearch] = useState("");
  // Orden por defecto: nombre A-Z (asc). Notas/promedio arrancan mayor→menor (desc).
  const [sort, setSort] = useState({ key: SORT_NOMBRE, dir: "asc" });
  const navigate = useNavigate();

  const asignaturas = grupo?.asignaturas || [];
  const estudiantes = grupo?.estudiantes || [];
  const kpis = grupo?.kpis || {};
  const notaAprob = grupo?.nota_aprobacion ?? 70;

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
    } catch (e) {
      setError("No se pudieron cargar los datos del grupo.");
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  useEffect(() => { loadData(); }, [loadData]);

  // Reconciliar la carrera por defecto con la lista real de carreras:
  // si existe una coincidencia (exacta o por contenido), adoptar el texto exacto
  // para que el <select> la muestre seleccionada.
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

  // Buscador: filtra por nombre de estudiante.
  const searched = useMemo(() => {
    if (!search.trim()) return estudiantes;
    const q = search.toLowerCase();
    return estudiantes.filter(e => (e.nombre || "").toLowerCase().includes(q));
  }, [estudiantes, search]);

  // Ordenamiento por columna.
  const sortedEstudiantes = useMemo(() => {
    const list = [...searched];
    const { key, dir } = sort;
    const mult = dir === "asc" ? 1 : -1;

    list.sort((a, b) => {
      if (key === SORT_NOMBRE) {
        return mult * (a.nombre || "").localeCompare(b.nombre || "", "es", { sensitivity: "base" });
      }
      let va, vb;
      if (key === SORT_PROMEDIO) {
        va = a.promedio; vb = b.promedio;
      } else {
        va = a.notas?.[key]; vb = b.notas?.[key];
      }
      // Nulos siempre al final, sin importar la dirección.
      const na = va == null, nb = vb == null;
      if (na && nb) return 0;
      if (na) return 1;
      if (nb) return -1;
      return mult * (va - vb);
    });
    return list;
  }, [searched, sort]);

  // Al hacer clic en un encabezado: nombre alterna asc/desc empezando en A-Z;
  // notas y promedio alternan empezando en mayor→menor (desc).
  const onSort = (key) => {
    setSort(prev => {
      if (prev.key === key) {
        return { key, dir: prev.dir === "asc" ? "desc" : "asc" };
      }
      return { key, dir: key === SORT_NOMBRE ? "asc" : "desc" };
    });
  };

  const sortIcon = (key) => {
    if (sort.key !== key) return <span className="text-gray-300 ml-1">↕</span>;
    return <span className="text-brand-dark ml-1">{sort.dir === "asc" ? "▲" : "▼"}</span>;
  };

  const notaClass = (nota) => {
    if (nota == null) return "text-gray-300";
    return nota < notaAprob ? "text-red-600" : "text-green-600";
  };

  // Exportación: nombre + una columna por asignatura + promedio.
  const exportCols = useMemo(() => ([
    { key: "nombre", label: "Estudiante" },
    { key: "nivel_riesgo", label: "Nivel Riesgo" },
    ...asignaturas.map(a => ({ key: a, label: a })),
    { key: "promedio", label: "Promedio" },
  ]), [asignaturas]);

  const exportData = useMemo(() => (
    sortedEstudiantes.map(e => ({
      nombre: e.nombre,
      nivel_riesgo: e.nivel_riesgo || "",
      ...Object.fromEntries(asignaturas.map(a => [a, e.notas?.[a] ?? ""])),
      promedio: e.promedio ?? "",
    }))
  ), [sortedEstudiantes, asignaturas]);

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
            onChange={e => setFiltros(f => ({ ...f, carrera: e.target.value }))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[240px]"
          >
            <option value="">Todas las carreras</option>
            {/* Si el valor por defecto aún no está en la lista, mostrarlo igual */}
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
            onChange={e => setFiltros(f => ({ ...f, nivel: e.target.value }))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            {[1,2,3,4,5,6,7,8].map(n => <option key={n} value={n}>Nivel {n}</option>)}
          </select>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <input
            type="text"
            placeholder="Buscar estudiante..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-500">
            {sortedEstudiantes.length} estudiantes
          </span>
        </div>
      </div>

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
          <div className="overflow-x-auto">
            <table className="text-sm border-collapse">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {/* Primera columna congelada */}
                  <th
                    onClick={() => onSort(SORT_NOMBRE)}
                    className="sticky left-0 z-20 bg-gray-50 text-left px-4 py-3 font-semibold text-gray-700 cursor-pointer select-none whitespace-nowrap border-r border-gray-200 min-w-[220px] hover:bg-gray-100"
                    title="Ordenar por nombre (A-Z / Z-A)"
                  >
                    Estudiante {sortIcon(SORT_NOMBRE)}
                  </th>
                  {asignaturas.map(a => (
                    <th
                      key={a}
                      onClick={() => onSort(a)}
                      className="px-3 py-3 font-semibold text-gray-700 cursor-pointer select-none text-center whitespace-nowrap hover:bg-gray-100 min-w-[110px] max-w-[180px]"
                      title={`${a} — ordenar por nota (mayor→menor / menor→mayor)`}
                    >
                      <span className="block truncate max-w-[160px] mx-auto">{a}</span>
                      <span className="text-[10px] font-normal text-gray-400">nota {sortIcon(a)}</span>
                    </th>
                  ))}
                  <th
                    onClick={() => onSort(SORT_PROMEDIO)}
                    className="px-3 py-3 font-semibold text-gray-700 cursor-pointer select-none text-center whitespace-nowrap hover:bg-gray-100 min-w-[110px] border-l border-gray-200 bg-gray-50"
                    title="Ordenar por promedio (mayor→menor / menor→mayor)"
                  >
                    Promedio {sortIcon(SORT_PROMEDIO)}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedEstudiantes.map((e) => (
                  <tr
                    key={e.student_id}
                    onClick={() => navigate(`/ficha/${e.student_id}`)}
                    className="border-b border-gray-100 cursor-pointer hover:bg-blue-50 transition-colors group"
                  >
                    {/* Nombre — congelado */}
                    <td className="sticky left-0 z-10 bg-white group-hover:bg-blue-50 px-4 py-2.5 border-r border-gray-200 min-w-[220px]">
                      <div className="font-medium text-gray-900 truncate max-w-[220px]">{e.nombre || "—"}</div>
                      {e.nivel_riesgo === "Alto" && (
                        <span className="text-[10px] text-red-600 font-semibold">riesgo alto</span>
                      )}
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
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
