import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge, CompromisoBar } from "../components/RiskBadge";
import { SummaryCard } from "../components/StatCard";
import { PeriodSelector } from "../components/PeriodSelector";
import ExportExcelButton from "../components/ExportExcelButton";

const ASIG_EXPORT_COLS = [
  { key: "asignatura", label: "Asignatura" },
  { key: "docente", label: "Docente" },
  { key: "carrera", label: "Carrera" },
  { key: "nivel", label: "Nivel" },
  { key: "total_estudiantes", label: "Total estudiantes" },
  { key: "promedio_general", label: "Promedio general" },
  { key: "aprobados", label: "Aprobados" },
  { key: "reprobados", label: "Reprobados" },
  { key: "porcentaje_aprobacion", label: "% Aprobación" },
  { key: "total_repitentes", label: "Repitentes" },
  { key: "estudiantes_riesgo_alto", label: "Riesgo Alto" },
  { key: "promedio_compromiso", label: "Compromiso promedio" },
  { key: "total_intervenciones", label: "Intervenciones" },
];

const AVAC_BASE = "https://avac.ups.edu.ec/grado68";
const avacCourseUrl = (codigo) =>
  `${AVAC_BASE}/course/search.php?areaids=core_course-course&q=${encodeURIComponent(codigo)}`;

export default function Asignaturas() {
  const [asignaturas, setAsignaturas] = useState([]);
  const [carreras, setCarreras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtros, setFiltros] = useState({ carrera: "", nivel: "", solo_criticas: false, periodo: "" });
  const [search, setSearch] = useState("");
  const [detalle, setDetalle] = useState(null);
  const [loadingDetalle, setLoadingDetalle] = useState(false);
  const navigate = useNavigate();

  const filteredAsignaturas = useMemo(() => {
    if (!search.trim()) return asignaturas;
    const q = search.toLowerCase();
    return asignaturas.filter(a =>
      (a.asignatura && a.asignatura.toLowerCase().includes(q)) ||
      (a.docente && a.docente.toLowerCase().includes(q)) ||
      (a.codigo_avac && a.codigo_avac.toLowerCase().includes(q))
    );
  }, [asignaturas, search]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (filtros.carrera) params.carrera = filtros.carrera;
      if (filtros.nivel) params.nivel = filtros.nivel;
      if (filtros.solo_criticas) params.solo_criticas = true;
      if (filtros.periodo) params.periodo = filtros.periodo;

      const [data, carrerasData] = await Promise.all([
        api.getAsignaturasAnalytics(params),
        api.getCarreras(),
      ]);
      setAsignaturas(data);
      setCarreras(carrerasData);
    } catch (e) {
      setError("No se pudieron cargar los datos de asignaturas.");
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  useEffect(() => { loadData(); }, [loadData]);

  const openDetalle = async (asig) => {
    setLoadingDetalle(true);
    try {
      const data = await api.getAsignaturaDetalle(asig.asignatura, asig.docente, filtros.periodo);
      setDetalle(data);
    } catch (e) {
      setError("No se pudo cargar el detalle de la asignatura.");
    } finally {
      setLoadingDetalle(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analítica de Asignaturas</h1>
          <p className="text-gray-500 text-sm">Vista agregada por materia: promedios, aprobación, reprobación, repitencia y materias críticas</p>
        </div>
        <ExportExcelButton data={filteredAsignaturas} columns={ASIG_EXPORT_COLS} filename="analitica_asignaturas" reportTitle="Analítica de Asignaturas" />
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Resumen cards */}
      {!loading && asignaturas.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <SummaryCard
            label="Total asignaturas"
            value={asignaturas.length}
            color="blue"
          />
          <SummaryCard
            label="Materias críticas"
            value={asignaturas.filter(a =>
              (a.porcentaje_reprobacion && a.porcentaje_reprobacion > 50) ||
              (a.promedio_general && a.promedio_general < 60)
            ).length}
            color="red"
          />
          <SummaryCard
            label="Promedio general"
            value={
              Math.round(
                asignaturas.reduce((s, a) => s + (a.promedio_general || 0), 0) /
                Math.max(asignaturas.filter(a => a.promedio_general).length, 1)
              )
            }
            color="yellow"
          />
          <SummaryCard
            label="Estudiantes en riesgo alto"
            value={asignaturas.reduce((s, a) => s + (a.estudiantes_riesgo_alto || 0), 0)}
            color="red"
          />
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

        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input
            type="checkbox"
            checked={filtros.solo_criticas}
            onChange={e => setFiltros(f => ({ ...f, solo_criticas: e.target.checked }))}
            className="rounded"
          />
          Solo materias críticas
        </label>

        <div className="ml-auto flex items-center gap-3">
          <input
            type="text"
            placeholder="Buscar asignatura, docente o código..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-500">
            {filteredAsignaturas.length} asignaturas
          </span>
        </div>
      </div>

      {/* Tabla de asignaturas */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">Cargando...</div>
        ) : filteredAsignaturas.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-3xl mb-2 text-gray-300">📋</div>
            <div className="text-sm text-gray-400">No hay datos de asignaturas para el período seleccionado</div>
            <p className="text-xs text-gray-300 mt-1">Los datos aparecerán cuando se carguen calificaciones para este período</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Asignatura</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Docente</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Nivel</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Estudiantes</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Promedio general de notas finales de la asignatura (escala 0-100)">Promedio</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Porcentaje de estudiantes con nota final >= 70">Aprobación</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Porcentaje de estudiantes con nota final < 70">Reprobación</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Estudiantes que estan cursando la asignatura por segunda vez o mas">Repitentes</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Estudiantes en riesgo alto: nota < 60, materias reprobadas o inactividad en AVAC">Riesgo Alto</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700" title="Enlace al Aula Virtual (AVAC)">AVAC</th>
              </tr>
            </thead>
            <tbody>
              {filteredAsignaturas.map((a, i) => {
                const esCritica = (a.porcentaje_reprobacion && a.porcentaje_reprobacion > 50) ||
                                  (a.promedio_general && a.promedio_general < 60);
                return (
                  <tr
                    key={`${a.asignatura}-${a.docente}-${i}`}
                    onClick={() => openDetalle(a)}
                    className={`border-b border-gray-100 cursor-pointer hover:bg-blue-50 transition-colors
                      ${esCritica ? "bg-red-50/40" : ""}`}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{a.asignatura}</div>
                      <div className="flex items-center gap-1 mt-0.5">
                        {a.carrera && <span className="text-xs text-gray-400">{a.carrera}</span>}
                        {a.grupos?.length > 0 && (
                          <span className="text-xs text-purple-600 font-medium ml-1">
                            G{a.grupos.join(", G")}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-[180px] truncate">{a.docente || "—"}</td>
                    <td className="px-4 py-3 text-center">
                      {a.nivel ? <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full">{a.nivel}</span> : "—"}
                    </td>
                    <td className="px-4 py-3 text-center font-semibold">{a.total_estudiantes}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`font-mono font-semibold ${
                        a.promedio_general && a.promedio_general < 60 ? "text-red-600" :
                        a.promedio_general && a.promedio_general < 70 ? "text-yellow-600" :
                        "text-green-600"
                      }`}>
                        {a.promedio_general != null ? a.promedio_general : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="text-green-600 font-semibold">{a.porcentaje_aprobacion != null ? `${a.porcentaje_aprobacion}%` : "—"}</span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`font-semibold ${a.porcentaje_reprobacion > 50 ? "text-red-600" : "text-yellow-600"}`}>
                        {a.porcentaje_reprobacion != null ? `${a.porcentaje_reprobacion}%` : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {a.total_repitentes > 0 ? (
                        <span className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full font-semibold">{a.total_repitentes}</span>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {a.estudiantes_riesgo_alto > 0 ? (
                        <span className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full font-bold">{a.estudiantes_riesgo_alto}</span>
                      ) : <span className="text-green-500 text-xs">0</span>}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {a.codigo_avac ? (
                        <a
                          href={avacCourseUrl(a.codigo_avac)}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={e => e.stopPropagation()}
                          className="text-blue-600 hover:text-blue-800 hover:underline text-xs font-medium"
                        >
                          Abrir
                        </a>
                      ) : <span className="text-gray-300 text-xs">—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal detalle de asignatura — agrupado por grupo */}
      {detalle && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setDetalle(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[85vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{detalle.asignatura}</h2>
                  <p className="text-sm text-gray-500 mt-1">
                    {detalle.docente && `Docente: ${detalle.docente}`}
                    {detalle.carrera && ` | ${detalle.carrera}`}
                    {detalle.nivel && ` | Nivel ${detalle.nivel}`}
                  </p>
                </div>
                <button onClick={() => setDetalle(null)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
                <MiniCard label="Estudiantes" value={detalle.total_estudiantes} />
                <MiniCard label="Promedio" value={detalle.promedio_general} />
                <MiniCard label="Aprobados" value={detalle.aprobados} />
                <MiniCard label="Reprobados" value={detalle.reprobados} />
                <MiniCard label="Repitentes" value={detalle.total_repitentes} />
              </div>
            </div>

            <div className="p-6 space-y-6">
              {loadingDetalle ? (
                <div className="text-center py-10 text-gray-400">Cargando...</div>
              ) : (detalle.grupos_detalle || []).map((grp, idx) => {
                const grupoLabel = grp.grupo ? `Grupo ${grp.grupo}` : "Sin grupo";
                const exportFilename = `${detalle.asignatura}_${grupoLabel}`.replace(/\s+/g, "_");
                const exportCols = [
                  { key: "carrera", label: "Carrera" },
                  { key: "grupo", label: "Grupo" },
                  { key: "codigo_grupo", label: "Código Grupo" },
                  { key: "docente", label: "Docente" },
                  { key: "nombre", label: "Estudiante" },
                  { key: "correo_institucional", label: "Correo" },
                  { key: "nota_final", label: "Nota Final" },
                  { key: "nivel_riesgo", label: "Nivel Riesgo" },
                  { key: "indice_compromiso", label: "Compromiso" },
                  { key: "dias_sin_acceso", label: "Días sin acceso" },
                  { key: "numero_repitencias", label: "Repitencias" },
                ];
                const exportData = (grp.estudiantes || []).map(est => ({
                  ...est,
                  carrera: detalle.carrera || "",
                  grupo: grp.grupo || "",
                  codigo_grupo: grp.codigo_avac || "",
                  docente: detalle.docente || "",
                }));
                return (
                <div key={idx} className="border border-gray-200 rounded-xl overflow-hidden">
                  <div className="bg-gray-50 px-4 py-3 flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-gray-800">{grupoLabel}</span>
                      <span className="text-xs text-gray-500">({grp.total_estudiantes} estudiantes)</span>
                      {grp.codigo_avac && (
                        <a
                          href={avacCourseUrl(grp.codigo_avac)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-500 hover:text-blue-700 underline"
                          onClick={e => e.stopPropagation()}
                        >
                          Abrir AVAC
                        </a>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <span>Promedio: <b className={(grp.promedio ?? 100) < 70 ? "text-red-600" : "text-green-600"}>{grp.promedio ?? "—"}</b></span>
                      <span>Aprobados: <b className="text-green-600">{grp.aprobados}</b></span>
                      <span>Reprobados: <b className="text-red-600">{grp.reprobados}</b></span>
                      {grp.riesgo_alto > 0 && <span>Riesgo alto: <b className="text-red-600">{grp.riesgo_alto}</b></span>}
                      <ExportExcelButton
                        data={exportData}
                        columns={exportCols}
                        filename={exportFilename}
                        reportTitle={`Asignatura: ${asig.asignatura} — ${asig.docente}`}
                        label="Excel"
                        small
                      />
                    </div>
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100">
                        <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">Estudiante</th>
                        <th className="text-center px-3 py-2 text-xs font-medium text-gray-500">Nota</th>
                        <th className="text-center px-3 py-2 text-xs font-medium text-gray-500">Riesgo</th>
                        <th className="px-3 py-2 text-xs font-medium text-gray-500 w-24">Compromiso</th>
                        <th className="text-center px-3 py-2 text-xs font-medium text-gray-500">Días AVAC</th>
                        <th className="text-center px-3 py-2 text-xs font-medium text-gray-500">Repitencias</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(grp.estudiantes || []).map((e) => (
                        <tr
                          key={e.student_id}
                          onClick={() => navigate(`/ficha/${e.student_id}`)}
                          className="border-b border-gray-50 cursor-pointer hover:bg-blue-50"
                        >
                          <td className="px-3 py-1.5">
                            <div className="font-medium text-gray-900">{e.nombre}</div>
                            <div className="text-xs text-gray-400">{e.correo_institucional}</div>
                          </td>
                          <td className="px-3 py-1.5 text-center">
                            <span className={`font-mono font-bold ${e.nota_final != null && e.nota_final < 70 ? "text-red-600" : "text-green-600"}`}>
                              {e.nota_final ?? "—"}
                            </span>
                          </td>
                          <td className="px-3 py-1.5 text-center"><RiskBadge nivel={e.nivel_riesgo} /></td>
                          <td className="px-3 py-1.5"><CompromisoBar valor={e.indice_compromiso} /></td>
                          <td className="px-3 py-1.5 text-center font-mono text-gray-600 text-xs">
                            {e.dias_sin_acceso != null ? `${e.dias_sin_acceso}d` : "—"}
                          </td>
                          <td className="px-3 py-1.5 text-center">
                            {e.numero_repitencias > 0 ? (
                              <span className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full">{e.numero_repitencias}</span>
                            ) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


function MiniCard({ label, value }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3 text-center">
      <div className="text-lg font-bold text-gray-800">{value ?? "—"}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
