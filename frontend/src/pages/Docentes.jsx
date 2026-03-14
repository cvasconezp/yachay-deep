import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge, CompromisoBar } from "../components/RiskBadge";

export default function Docentes() {
  const [docentes, setDocentes] = useState([]);
  const [carreras, setCarreras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtros, setFiltros] = useState({ carrera: "" });
  const [detalle, setDetalle] = useState(null);
  const [loadingDetalle, setLoadingDetalle] = useState(false);
  const navigate = useNavigate();

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (filtros.carrera) params.carrera = filtros.carrera;

      const [data, carrerasData] = await Promise.all([
        api.getDocentesAnalytics(params),
        api.getCarreras(),
      ]);
      setDocentes(data);
      setCarreras(carrerasData);
    } catch (e) {
      setError("No se pudieron cargar los datos de docentes.");
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  useEffect(() => { loadData(); }, [loadData]);

  const openDetalle = async (docente) => {
    setLoadingDetalle(true);
    try {
      const data = await api.getDocenteDetalle(docente.docente);
      setDetalle(data);
    } catch (e) {
      setError("No se pudo cargar el detalle del docente.");
    } finally {
      setLoadingDetalle(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Analitica Docente</h1>
      <p className="text-gray-500 text-sm mb-6">
        Ficha docente: asignaturas, estudiantes, concentracion de riesgo por curso
      </p>

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Resumen */}
      {!loading && docentes.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <SummaryCard label="Total docentes" value={docentes.length} color="blue" />
          <SummaryCard
            label="Estudiantes totales"
            value={docentes.reduce((s, d) => s + d.total_estudiantes, 0)}
            color="green"
          />
          <SummaryCard
            label="Riesgo alto total"
            value={docentes.reduce((s, d) => s + d.estudiantes_riesgo_alto, 0)}
            color="red"
          />
          <SummaryCard
            label="Intervenciones"
            value={docentes.reduce((s, d) => s + d.total_intervenciones, 0)}
            color="yellow"
          />
        </div>
      )}

      {/* Filtros */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4 flex flex-wrap gap-3 items-end">
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
        <div className="ml-auto text-sm text-gray-500">{docentes.length} docentes</div>
      </div>

      {/* Tabla */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">Cargando...</div>
        ) : docentes.length === 0 ? (
          <div className="text-center py-20 text-gray-400">No hay docentes registrados</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Docente</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Asignaturas</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Estudiantes</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Promedio general de notas finales de todos los estudiantes del docente (escala 0-100)">Promedio</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Porcentaje de estudiantes con nota final >= 70 sobre el total">Aprobacion</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Estudiantes clasificados en riesgo alto: nota promedio < 60, materias reprobadas o inactividad prolongada en AVAC">Riesgo Alto</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Estudiantes en riesgo moderado: rendimiento entre 60-69 o señales tempranas de dificultad academica">Riesgo Medio</th>
                <th className="px-4 py-3 font-semibold text-gray-700 w-28 cursor-help" title="Promedio del indice de compromiso de los estudiantes del docente. Mide: acceso AVAC (30%), tareas (30%), rendimiento (25%), matricula (15%)">Compromiso prom.</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Intervenciones</th>
              </tr>
            </thead>
            <tbody>
              {docentes.map((d, i) => (
                <tr
                  key={`${d.docente}-${i}`}
                  onClick={() => openDetalle(d)}
                  className={`border-b border-gray-100 cursor-pointer hover:bg-blue-50 transition-colors
                    ${d.estudiantes_riesgo_alto > 5 ? "bg-red-50/30" : ""}`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{d.docente}</div>
                    <div className="text-xs text-gray-400">{d.carreras?.join(", ")}</div>
                  </td>
                  <td className="px-4 py-3 text-center font-semibold">{d.total_asignaturas}</td>
                  <td className="px-4 py-3 text-center font-semibold">{d.total_estudiantes}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`font-mono font-semibold ${
                      d.promedio_general && d.promedio_general < 60 ? "text-red-600" :
                      d.promedio_general && d.promedio_general < 70 ? "text-yellow-600" :
                      "text-green-600"
                    }`}>
                      {d.promedio_general ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="text-green-600 font-semibold">
                      {d.porcentaje_aprobacion != null ? `${d.porcentaje_aprobacion}%` : "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {d.estudiantes_riesgo_alto > 0 ? (
                      <span className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full font-bold">{d.estudiantes_riesgo_alto}</span>
                    ) : <span className="text-green-500 text-xs">0</span>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {d.estudiantes_riesgo_medio > 0 ? (
                      <span className="bg-yellow-100 text-yellow-700 text-xs px-2 py-0.5 rounded-full font-semibold">{d.estudiantes_riesgo_medio}</span>
                    ) : <span className="text-gray-400 text-xs">0</span>}
                  </td>
                  <td className="px-4 py-3"><CompromisoBar valor={d.promedio_compromiso} /></td>
                  <td className="px-4 py-3 text-center">
                    <span className={`font-semibold ${d.total_intervenciones === 0 ? "text-gray-400" : "text-blue-600"}`}>
                      {d.total_intervenciones}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal detalle docente */}
      {detalle && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setDetalle(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[85vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{detalle.docente}</h2>
                  <p className="text-sm text-gray-500 mt-1">
                    {detalle.carreras?.join(", ")} | {detalle.total_asignaturas} asignaturas | {detalle.total_estudiantes} estudiantes
                  </p>
                </div>
                <button onClick={() => setDetalle(null)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {(detalle.asignaturas_detalle || []).map((asig, idx) => (
                <div key={idx} className="border border-gray-200 rounded-xl overflow-hidden">
                  <div className="bg-gray-50 px-4 py-3 flex items-center justify-between">
                    <div>
                      <span className="font-semibold text-gray-800">{asig.asignatura}</span>
                      {asig.nivel && <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">Nivel {asig.nivel}</span>}
                    </div>
                    <div className="flex gap-4 text-xs text-gray-500">
                      <span>Promedio: <b className={asig.promedio < 70 ? "text-red-600" : "text-green-600"}>{asig.promedio}</b></span>
                      <span>Aprobados: <b className="text-green-600">{asig.aprobados}</b></span>
                      <span>Reprobados: <b className="text-red-600">{asig.reprobados}</b></span>
                      {asig.riesgo_alto > 0 && <span>Riesgo alto: <b className="text-red-600">{asig.riesgo_alto}</b></span>}
                    </div>
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100">
                        <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">Estudiante</th>
                        <th className="text-center px-3 py-2 text-xs font-medium text-gray-500">Nota</th>
                        <th className="text-center px-3 py-2 text-xs font-medium text-gray-500">Riesgo</th>
                        <th className="px-3 py-2 text-xs font-medium text-gray-500 w-24 cursor-help" title="Indice de compromiso: acceso AVAC (30%), tareas (30%), rendimiento (25%), matricula (15%)">Compromiso</th>
                        <th className="text-center px-3 py-2 text-xs font-medium text-gray-500 cursor-help" title="Dias desde el ultimo acceso al Aula Virtual (AVAC)">Dias AVAC</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(asig.estudiantes || []).map((e, ei) => (
                        <tr
                          key={e.student_id}
                          onClick={() => navigate(`/ficha/${e.student_id}`)}
                          className="border-b border-gray-50 cursor-pointer hover:bg-blue-50"
                        >
                          <td className="px-3 py-1.5 text-gray-800">{e.nombre}</td>
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
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, color }) {
  const colors = {
    blue: "bg-blue-50 text-blue-700 border-blue-200",
    red: "bg-red-50 text-red-700 border-red-200",
    yellow: "bg-yellow-50 text-yellow-700 border-yellow-200",
    green: "bg-green-50 text-green-700 border-green-200",
  };
  return (
    <div className={`rounded-xl border p-4 ${colors[color]}`}>
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-xs font-medium mt-1 opacity-80">{label}</div>
    </div>
  );
}
