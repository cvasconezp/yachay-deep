import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";

export default function Tutorias() {
  const [tutorias, setTutorias] = useState([]);
  const [carreras, setCarreras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtros, setFiltros] = useState({ carrera: "", nivel_riesgo: "Alto" });
  const [expanded, setExpanded] = useState(new Set());
  const navigate = useNavigate();

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = { nivel_riesgo: filtros.nivel_riesgo };
      if (filtros.carrera) params.carrera = filtros.carrera;

      const [data, carrerasData] = await Promise.all([
        api.getTutoriasPorAsignatura(params),
        api.getCarreras(),
      ]);
      setTutorias(data);
      setCarreras(carrerasData);
    } catch (e) {
      setError("No se pudieron cargar las listas de tutorias.");
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  useEffect(() => { loadData(); }, [loadData]);

  const toggleExpand = (asignatura) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(asignatura)) next.delete(asignatura);
      else next.add(asignatura);
      return next;
    });
  };

  const expandAll = () => {
    if (expanded.size === tutorias.length) {
      setExpanded(new Set());
    } else {
      setExpanded(new Set(tutorias.map(t => t.asignatura)));
    }
  };

  const totalEstudiantes = tutorias.reduce((s, t) => s + t.total_en_riesgo, 0);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Tutorias por Asignatura</h1>
      <p className="text-gray-500 text-sm mb-6">
        Listas de convocatoria a tutoria agrupadas por materia con motivos de riesgo
      </p>

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Resumen */}
      {!loading && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          <SummaryCard label="Asignaturas con riesgo" value={tutorias.length} color="red" />
          <SummaryCard label="Estudiantes a convocar" value={totalEstudiantes} color="yellow" />
          <SummaryCard
            label="Sin intervenciones previas"
            value={tutorias.reduce((s, t) =>
              s + t.estudiantes.filter(e => e.intervenciones_previas === 0).length, 0
            )}
            color="blue"
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

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Nivel de Riesgo</label>
          <select
            value={filtros.nivel_riesgo}
            onChange={e => setFiltros(f => ({ ...f, nivel_riesgo: e.target.value }))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="Alto">Solo Alto</option>
            <option value="Alto,Medio">Alto y Medio</option>
            <option value="Medio">Solo Medio</option>
          </select>
        </div>

        <button
          onClick={expandAll}
          className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          {expanded.size === tutorias.length ? "Colapsar todo" : "Expandir todo"}
        </button>

        <div className="ml-auto text-sm text-gray-500">
          {tutorias.length} asignaturas | {totalEstudiantes} estudiantes
        </div>
      </div>

      {/* Lista de asignaturas con estudiantes */}
      {loading ? (
        <div className="bg-white rounded-xl border border-gray-200 flex items-center justify-center py-20 text-gray-400">Cargando...</div>
      ) : tutorias.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 text-center py-20 text-gray-400">
          No hay estudiantes en riesgo con los filtros seleccionados
        </div>
      ) : (
        <div className="space-y-3">
          {tutorias.map((t, idx) => (
            <div key={`${t.asignatura}-${idx}`} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {/* Header de asignatura */}
              <button
                onClick={() => toggleExpand(t.asignatura)}
                className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="text-gray-400 text-sm">{expanded.has(t.asignatura) ? "v" : ">"}</span>
                  <div className="text-left">
                    <div className="font-semibold text-gray-900">{t.asignatura}</div>
                    <div className="text-xs text-gray-500">
                      {t.docente && `${t.docente} | `}
                      {t.carrera}
                      {t.nivel && ` | Nivel ${t.nivel}`}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="bg-red-100 text-red-700 text-sm px-3 py-1 rounded-full font-bold">
                    {t.total_en_riesgo} estudiante{t.total_en_riesgo !== 1 ? "s" : ""}
                  </span>
                </div>
              </button>

              {/* Tabla de estudiantes expandida */}
              {expanded.has(t.asignatura) && (
                <div className="border-t border-gray-200">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Estudiante</th>
                        <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Contacto</th>
                        <th className="text-center px-4 py-2 text-xs font-medium text-gray-500">Riesgo</th>
                        <th className="text-center px-4 py-2 text-xs font-medium text-gray-500">Nota</th>
                        <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Motivos</th>
                        <th className="text-center px-4 py-2 text-xs font-medium text-gray-500">Interv. previas</th>
                        <th className="text-center px-4 py-2 text-xs font-medium text-gray-500">Accion</th>
                      </tr>
                    </thead>
                    <tbody>
                      {t.estudiantes.map((e) => (
                        <tr key={e.student_id} className="border-b border-gray-50 hover:bg-blue-50/50">
                          <td className="px-4 py-2">
                            <div
                              className="font-medium text-blue-700 cursor-pointer hover:underline"
                              onClick={() => navigate(`/ficha/${e.student_id}`)}
                            >
                              {e.nombre}
                            </div>
                            <div className="text-xs text-gray-400">{e.correo_institucional}</div>
                          </td>
                          <td className="px-4 py-2 text-xs text-gray-600">
                            {e.telefono && <div>{e.telefono}</div>}
                            {e.whatsapp && <div className="text-green-600">WA: {e.whatsapp}</div>}
                          </td>
                          <td className="px-4 py-2 text-center"><RiskBadge nivel={e.nivel_riesgo} /></td>
                          <td className="px-4 py-2 text-center">
                            <span className={`font-mono font-bold ${
                              e.nota_asignatura != null && e.nota_asignatura < 70 ? "text-red-600" : "text-green-600"
                            }`}>
                              {e.nota_asignatura ?? "—"}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <div className="flex flex-wrap gap-1">
                              {e.motivos_riesgo?.map((m, mi) => (
                                <span key={mi} className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full">
                                  {m}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-4 py-2 text-center">
                            <span className={`font-semibold ${e.intervenciones_previas === 0 ? "text-red-500" : "text-blue-600"}`}>
                              {e.intervenciones_previas}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-center">
                            <button
                              onClick={() => navigate(`/ficha/${e.student_id}`)}
                              className="text-xs bg-blue-600 text-white px-3 py-1 rounded-lg hover:bg-blue-700 transition-colors"
                            >
                              Ver ficha
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
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
