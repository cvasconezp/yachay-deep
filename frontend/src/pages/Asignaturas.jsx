import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge, CompromisoBar } from "../components/RiskBadge";

export default function Asignaturas() {
  const [asignaturas, setAsignaturas] = useState([]);
  const [carreras, setCarreras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtros, setFiltros] = useState({ carrera: "", nivel: "", solo_criticas: false });
  const [detalle, setDetalle] = useState(null);
  const [loadingDetalle, setLoadingDetalle] = useState(false);
  const navigate = useNavigate();

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (filtros.carrera) params.carrera = filtros.carrera;
      if (filtros.nivel) params.nivel = filtros.nivel;
      if (filtros.solo_criticas) params.solo_criticas = true;

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
      const data = await api.getAsignaturaDetalle(asig.asignatura, asig.docente);
      setDetalle(data);
    } catch (e) {
      setError("No se pudo cargar el detalle de la asignatura.");
    } finally {
      setLoadingDetalle(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Analitica de Asignaturas</h1>
      <p className="text-gray-500 text-sm mb-6">
        Vista agregada por materia: promedios, aprobacion, reprobacion, repitencia y materias criticas
      </p>

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
            label="Materias criticas"
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
          Solo materias criticas
        </label>

        <div className="ml-auto text-sm text-gray-500">
          {asignaturas.length} asignaturas
        </div>
      </div>

      {/* Tabla de asignaturas */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">Cargando...</div>
        ) : asignaturas.length === 0 ? (
          <div className="text-center py-20 text-gray-400">No hay asignaturas con los filtros seleccionados</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Asignatura</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Docente</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Nivel</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Estudiantes</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Promedio</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Aprobacion</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Reprobacion</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Repitentes</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Riesgo Alto</th>
              </tr>
            </thead>
            <tbody>
              {asignaturas.map((a, i) => {
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
                      {a.carrera && <div className="text-xs text-gray-400">{a.carrera}</div>}
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
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal detalle de asignatura */}
      {detalle && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setDetalle(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-auto" onClick={e => e.stopPropagation()}>
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

            <div className="p-6">
              <h3 className="font-semibold text-gray-700 mb-3">Estudiantes ({detalle.estudiantes?.length || 0})</h3>
              {loadingDetalle ? (
                <div className="text-center py-10 text-gray-400">Cargando...</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Estudiante</th>
                      <th className="text-center px-3 py-2 font-medium text-gray-600">Nota</th>
                      <th className="text-center px-3 py-2 font-medium text-gray-600">Riesgo</th>
                      <th className="px-3 py-2 font-medium text-gray-600 w-28">Compromiso</th>
                      <th className="text-center px-3 py-2 font-medium text-gray-600">Dias AVAC</th>
                      <th className="text-center px-3 py-2 font-medium text-gray-600">Repitencias</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detalle.estudiantes || []).map((e, i) => (
                      <tr
                        key={e.student_id}
                        onClick={() => navigate(`/ficha/${e.student_id}`)}
                        className="border-b border-gray-100 cursor-pointer hover:bg-blue-50"
                      >
                        <td className="px-3 py-2">
                          <div className="font-medium text-gray-900">{e.nombre}</div>
                          <div className="text-xs text-gray-400">{e.correo_institucional}</div>
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className={`font-mono font-bold ${
                            e.nota_final != null && e.nota_final < 70 ? "text-red-600" : "text-green-600"
                          }`}>
                            {e.nota_final != null ? e.nota_final : "—"}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center"><RiskBadge nivel={e.nivel_riesgo} /></td>
                        <td className="px-3 py-2"><CompromisoBar valor={e.indice_compromiso} /></td>
                        <td className="px-3 py-2 text-center font-mono text-gray-700">
                          {e.dias_sin_acceso != null ? `${e.dias_sin_acceso}d` : "—"}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {e.numero_repitencias > 0 ? (
                            <span className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full">{e.numero_repitencias}</span>
                          ) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
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

function MiniCard({ label, value }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3 text-center">
      <div className="text-lg font-bold text-gray-800">{value ?? "—"}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
