import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge, CompromisoBar } from "../components/RiskBadge";
import InterventionForm from "./InterventionForm";

export default function FichaEstudiante() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [ficha, setFicha] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const searchTimeout = useRef(null);

  // Si viene con ID en la URL, cargar directamente
  useEffect(() => {
    if (studentId) loadFicha(studentId);
  }, [studentId]);

  const handleSearch = (value) => {
    setQuery(value);
    clearTimeout(searchTimeout.current);
    if (value.length < 2) { setSearchResults([]); return; }
    searchTimeout.current = setTimeout(async () => {
      try {
        const results = await api.searchStudents(value);
        setSearchResults(results);
      } catch (e) { console.error(e); }
    }, 300);
  };

  const loadFicha = async (id) => {
    setLoading(true);
    setSearchResults([]);
    try {
      const data = await api.getFicha(id);
      setFicha(data);
      setQuery(data.nombre);
      navigate(`/ficha/${id}`, { replace: true });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleExportPDF = async () => {
    if (!ficha) return;
    const blob = await api.exportFichaPDF(ficha.id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ficha_${ficha.nombre.replace(/\s+/g, "_")}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Agrupar tareas por código de curso
  const tareasPorCurso = ficha?.tareas?.reduce((acc, t) => {
    if (!acc[t.codigo_curso]) acc[t.codigo_curso] = [];
    acc[t.codigo_curso].push(t);
    return acc;
  }, {}) || {};

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Ficha del Estudiante</h1>
      <p className="text-gray-500 text-sm mb-6">Busca por nombre, correo institucional, cédula o teléfono</p>

      {/* Buscador */}
      <div className="relative mb-6">
        <input
          type="text"
          value={query}
          onChange={e => handleSearch(e.target.value)}
          placeholder="Buscar estudiante..."
          className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 pr-10"
        />
        {loading && <span className="absolute right-3 top-3.5 text-gray-400 text-sm">⏳</span>}

        {searchResults.length > 0 && (
          <div className="absolute z-10 w-full bg-white border border-gray-200 rounded-xl shadow-lg mt-1 max-h-64 overflow-y-auto">
            {searchResults.map(s => (
              <button
                key={s.id}
                onClick={() => loadFicha(s.id)}
                className="w-full text-left px-4 py-3 hover:bg-blue-50 flex items-center justify-between border-b border-gray-100 last:border-0"
              >
                <div>
                  <div className="font-medium text-gray-900 text-sm">{s.nombre}</div>
                  <div className="text-xs text-gray-400">{s.correo_institucional} · {s.carrera}</div>
                </div>
                <RiskBadge nivel={s.nivel_riesgo} />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Ficha */}
      {ficha && (
        <div className="space-y-5">
          {/* Header de la ficha */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-bold text-gray-900">{ficha.nombre}</h2>
                <p className="text-gray-500 text-sm mt-0.5">{ficha.carrera}</p>
                <div className="flex flex-wrap gap-2 mt-3 text-sm text-gray-600">
                  {ficha.correo_institucional && <span>📧 {ficha.correo_institucional}</span>}
                  {ficha.cedula && <span>🪪 {ficha.cedula}</span>}
                  {ficha.telefono && <span>📱 {ficha.telefono}</span>}
                  {ficha.sede && <span>🏫 {ficha.sede}</span>}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleExportPDF}
                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                  📄 Exportar PDF
                </button>
                <button
                  onClick={() => setShowForm(true)}
                  className="bg-[#1B3A6B] hover:bg-blue-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                  + Registrar intervención
                </button>
              </div>
            </div>

            {/* Indicadores de riesgo */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5 pt-5 border-t border-gray-100">
              <IndicatorCard label="Nivel de Riesgo" value={<RiskBadge nivel={ficha.nivel_riesgo} size="lg" />} />
              <IndicatorCard
                label="Días sin AVAC"
                value={ficha.dias_sin_acceso != null ? `${Math.round(ficha.dias_sin_acceso)} días` : "—"}
                highlight={ficha.dias_sin_acceso > 14}
              />
              <IndicatorCard
                label="Índice Compromiso"
                value={<CompromisoBar valor={ficha.indice_compromiso} />}
              />
              <IndicatorCard
                label="Tareas entregadas"
                value={ficha.porcentaje_tareas != null ? `${Math.round(ficha.porcentaje_tareas)}%` : "—"}
              />
            </div>
          </div>

          {/* Calificaciones */}
          {ficha.calificaciones?.length > 0 && (
            <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <h3 className="px-5 py-4 font-semibold text-gray-800 border-b border-gray-100">
                Calificaciones Institucionales ({ficha.calificaciones.length} asignaturas)
              </h3>
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-left px-5 py-2.5 text-gray-600 font-medium">Asignatura</th>
                    <th className="text-left px-5 py-2.5 text-gray-600 font-medium">Docente</th>
                    <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Nota Final</th>
                  </tr>
                </thead>
                <tbody>
                  {ficha.calificaciones.map((g, i) => (
                    <tr key={i} className="border-t border-gray-100">
                      <td className="px-5 py-2.5 font-medium text-gray-800">{g.asignatura}</td>
                      <td className="px-5 py-2.5 text-gray-500">{g.docente || "—"}</td>
                      <td className="px-5 py-2.5 text-center">
                        <span className={`font-bold ${(g.nota_final ?? 0) < 28 ? "text-red-600" : "text-green-600"}`}>
                          {g.nota_final ?? "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {/* Tareas por curso */}
          {Object.keys(tareasPorCurso).length > 0 && (
            <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <h3 className="px-5 py-4 font-semibold text-gray-800 border-b border-gray-100">
                Actividades AVAC por Curso
              </h3>
              {Object.entries(tareasPorCurso).map(([curso, tareas]) => (
                <div key={curso} className="border-b border-gray-100 last:border-0">
                  <div className="px-5 py-2 bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Curso {curso}
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-gray-400">
                        <th className="text-left px-5 py-2">Unidad</th>
                        <th className="text-center px-5 py-2">Entregada</th>
                        <th className="text-center px-5 py-2">Calificación</th>
                        <th className="text-center px-5 py-2">Retrasada</th>
                        <th className="text-left px-5 py-2 max-w-xs">Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tareas.sort((a, b) => a.unidad.localeCompare(b.unidad)).map((t, i) => (
                        <tr key={i} className={`border-t border-gray-50 ${t.retrasada ? "bg-red-50/30" : ""}`}>
                          <td className="px-5 py-2 font-semibold">Unidad {t.unidad}</td>
                          <td className="px-5 py-2 text-center">{t.entregada ? "✅" : "❌"}</td>
                          <td className="px-5 py-2 text-center font-mono">
                            {t.calificacion != null ? `${t.calificacion}/${t.calificacion_maxima || "?"}` : "—"}
                          </td>
                          <td className="px-5 py-2 text-center">{t.retrasada ? "⚠️" : "—"}</td>
                          <td className="px-5 py-2 text-xs text-gray-500 max-w-xs truncate">{t.estado || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </section>
          )}

          {/* Historial de intervenciones */}
          <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h3 className="font-semibold text-gray-800">
                Historial de Intervenciones ({ficha.total_intervenciones})
              </h3>
            </div>
            {ficha.intervenciones?.length === 0 ? (
              <p className="text-center py-8 text-gray-400 text-sm">Sin intervenciones registradas</p>
            ) : (
              <div className="divide-y divide-gray-100">
                {ficha.intervenciones.map(inv => (
                  <div key={inv.id} className="px-5 py-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-xs font-medium px-2 py-0.5 rounded-full mr-2">
                          {inv.medio}
                        </span>
                        <span className="text-xs text-gray-500">{inv.motivo}</span>
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-gray-400">
                          {inv.created_at ? new Date(inv.created_at).toLocaleString("es-EC") : ""}
                        </div>
                        <div className="text-xs text-gray-500">{inv.monitor_nombre}</div>
                      </div>
                    </div>
                    {inv.observacion && (
                      <p className="mt-2 text-sm text-gray-700">{inv.observacion}</p>
                    )}
                    <div className="mt-2 flex gap-3 text-xs text-gray-500">
                      {inv.estado && <span>Estado → <strong>{inv.estado}</strong></span>}
                      {inv.asignatura && <span>Asignatura: {inv.asignatura}</span>}
                      {inv.resultado && <span>Resultado: {inv.resultado}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* Modal de intervención */}
      {showForm && ficha && (
        <InterventionForm
          student={ficha}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadFicha(ficha.id); }}
        />
      )}
    </div>
  );
}

function IndicatorCard({ label, value, highlight }) {
  return (
    <div className={`rounded-lg p-3 ${highlight ? "bg-red-50" : "bg-gray-50"}`}>
      <div className="text-xs font-medium text-gray-500 mb-1">{label}</div>
      <div className={`font-semibold ${highlight ? "text-red-700" : "text-gray-800"}`}>{value}</div>
    </div>
  );
}
