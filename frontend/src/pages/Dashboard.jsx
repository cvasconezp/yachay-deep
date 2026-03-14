import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge, CompromisoBar, PredictionBadge } from "../components/RiskBadge";

const RISK_ORDER = { Alto: 0, Medio: 1, Bajo: 2 };

export default function Dashboard() {
  const [students, setStudents] = useState([]);
  const [stats, setStats] = useState(null);
  const [carreras, setCarreras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtros, setFiltros] = useState({ carrera: "", nivel_riesgo: "", solo_sin_intervencion: false });
  const navigate = useNavigate();

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (filtros.carrera) params.carrera = filtros.carrera;
      if (filtros.nivel_riesgo) params.nivel_riesgo = filtros.nivel_riesgo;
      if (filtros.solo_sin_intervencion) params.solo_sin_intervencion = true;

      const [studentsData, statsData, carrerasData] = await Promise.all([
        api.getRiskDashboard(params),
        api.getStats(),
        api.getCarreras(),
      ]);

      const sorted = studentsData.sort((a, b) =>
        (RISK_ORDER[a.nivel_riesgo] ?? 9) - (RISK_ORDER[b.nivel_riesgo] ?? 9) ||
        (b.dias_sin_acceso ?? 0) - (a.dias_sin_acceso ?? 0)
      );

      setStudents(sorted);
      setStats(statsData);
      setCarreras(carrerasData);
    } catch (e) {
      console.error(e);
      setError(e.message || "No se pudieron cargar los datos. Verifique su conexión e intente de nuevo.");
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  useEffect(() => { loadData(); }, [loadData]);

  const riskCounts = stats?.por_nivel_riesgo?.reduce((acc, r) => ({ ...acc, [r.nivel]: r.total }), {}) || {};

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Dashboard de Riesgo</h1>
      <p className="text-gray-500 text-sm mb-6">Estudiantes identificados con indicadores de riesgo académico</p>

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Tarjetas de resumen */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total monitoreados" value={stats?.total_estudiantes ?? "—"} color="blue" />
        <StatCard label="Riesgo Alto" value={riskCounts["Alto"] ?? 0} color="red" />
        <StatCard label="Riesgo Medio" value={riskCounts["Medio"] ?? 0} color="yellow" />
        <StatCard label="Intervenciones" value={stats?.total_intervenciones ?? 0} color="green" />
      </div>

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
          {students.length} estudiantes
        </div>
      </div>

      {/* Tabla */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {error ? (
          <div className="text-center py-20">
            <p className="text-red-600 font-medium mb-2">Error al cargar datos</p>
            <p className="text-gray-500 text-sm mb-4">{error}</p>
            <button onClick={loadData} className="text-sm text-blue-600 hover:text-blue-800 font-medium">
              Reintentar
            </button>
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">Cargando...</div>
        ) : students.length === 0 ? (
          <div className="text-center py-20 text-gray-400">No hay estudiantes con los filtros seleccionados</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Estudiante</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Carrera</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Riesgo</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Dias transcurridos desde el ultimo acceso del estudiante al Aula Virtual (AVAC)">Dias sin AVAC</th>
                <th className="px-4 py-3 font-semibold text-gray-700 w-36 cursor-help" title="Indice de compromiso academico: acceso AVAC (30%), tareas entregadas (30%), rendimiento academico (25%), estado de matricula (15%). Alto >= 70%, Medio >= 40%, Bajo < 40%">Compromiso</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700 cursor-help" title="Probabilidad de desercion predicha por modelo ML entrenado con datos historicos P60-P67. Basado en: promedio, nota minima, dispersión de notas y materias reprobadas">Pred. Desercion</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Intervenciones</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-700">Última</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s, i) => (
                <tr
                  key={s.id}
                  onClick={() => navigate(`/ficha/${s.id}`)}
                  className={`border-b border-gray-100 cursor-pointer hover:bg-blue-50 transition-colors
                    ${s.nivel_riesgo === "Alto" ? "bg-red-50/30" : ""}`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{s.nombre}</div>
                    <div className="text-xs text-gray-400">{s.correo_institucional}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-600 max-w-[200px] truncate">{s.carrera || "—"}</td>
                  <td className="px-4 py-3 text-center"><RiskBadge nivel={s.nivel_riesgo} /></td>
                  <td className="px-4 py-3 text-center font-mono text-gray-700">
                    {s.dias_sin_acceso != null
                      ? <span className={s.dias_sin_acceso > 14 ? "text-red-600 font-bold" : ""}>{Math.round(s.dias_sin_acceso)}d</span>
                      : "—"}
                  </td>
                  <td className="px-4 py-3"><CompromisoBar valor={s.indice_compromiso} /></td>
                  <td className="px-4 py-3 text-center"><PredictionBadge value={s.prob_desercion} label="Desercion" /></td>
                  <td className="px-4 py-3 text-center">
                    <span className={`font-semibold ${s.total_intervenciones === 0 ? "text-gray-400" : "text-blue-600"}`}>
                      {s.total_intervenciones}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center text-xs text-gray-400">
                    {s.ultima_intervencion ? new Date(s.ultima_intervencion).toLocaleDateString("es-EC") : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color }) {
  const colors = {
    blue:   "bg-blue-50 text-blue-700 border-blue-200",
    red:    "bg-red-50 text-red-700 border-red-200",
    yellow: "bg-yellow-50 text-yellow-700 border-yellow-200",
    green:  "bg-green-50 text-green-700 border-green-200",
  };
  return (
    <div className={`rounded-xl border p-4 ${colors[color]}`}>
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-xs font-medium mt-1 opacity-80">{label}</div>
    </div>
  );
}
