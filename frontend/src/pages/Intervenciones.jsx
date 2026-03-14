import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";

const MOTIVOS = [
  "Inactividad en AVAC",
  "Tareas no entregadas",
  "Bajo rendimiento",
  "Matrículas/Pagos",
  "Problemas personales",
  "Conectividad",
  "Otro",
];

const ESTADOS = ["Activo", "SNA (Sin Novedad Aparente)", "En riesgo", "Retirado", "Recuperado"];

const RESULTADOS = [
  "Contactado - comprometido a mejorar",
  "Contactado - situación compleja",
  "No contestó",
  "Buzón de voz",
  "Mensaje enviado sin respuesta",
];

function StatCard({ label, value, color = "text-brand", sub }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 px-5 py-4 shadow-sm">
      <div className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color}`}>{value}</div>
      {sub && <div className="text-[11px] text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

export default function Intervenciones() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [carreras, setCarreras] = useState([]);

  const [filtros, setFiltros] = useState({
    carrera: "",
    motivo: "",
    estado: "",
    resultado: "",
    seguimiento: "",
  });

  useEffect(() => {
    api.getCarreras().then(setCarreras).catch(() => {});
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (filtros.carrera) params.carrera = filtros.carrera;
      if (filtros.motivo) params.motivo = filtros.motivo;
      if (filtros.estado) params.estado = filtros.estado;
      if (filtros.resultado) params.resultado = filtros.resultado;
      if (filtros.seguimiento) params.seguimiento = filtros.seguimiento;
      const result = await api.getInterventionsDashboard(params);
      setData(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  useEffect(() => { loadData(); }, [loadData]);

  const updateFiltro = (key, value) => {
    setFiltros(prev => ({ ...prev, [key]: value }));
  };

  const resumen = data?.resumen || {};
  const items = data?.items || [];

  return (
    <div>
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Intervenciones</h1>
        <p className="text-gray-400 text-sm">Seguimiento y monitoreo de intervenciones realizadas</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <StatCard
          label="Total intervenciones"
          value={resumen.total_intervenciones ?? "—"}
          color="text-brand"
        />
        <StatCard
          label="Estudiantes intervenidos"
          value={resumen.estudiantes_intervenidos ?? "—"}
          color="text-blue-600"
        />
        <StatCard
          label="Pendientes de seguimiento"
          value={resumen.pendientes_seguimiento ?? "—"}
          color={resumen.pendientes_seguimiento > 0 ? "text-orange-600" : "text-green-600"}
        />
        <StatCard
          label="Carreras activas"
          value={resumen.por_carrera?.length ?? "—"}
          color="text-gray-700"
        />
      </div>

      {/* Cards por carrera */}
      {resumen.por_carrera?.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-5">
          {resumen.por_carrera.map(c => (
            <div key={c.carrera} className="bg-white rounded-lg border border-gray-200 px-4 py-3 shadow-sm">
              <div className="text-[11px] text-gray-500 font-medium uppercase tracking-wider truncate" title={c.carrera}>
                {c.carrera}
              </div>
              <div className="flex items-baseline gap-3 mt-1">
                <span className="text-lg font-bold text-brand">{c.estudiantes}</span>
                <span className="text-xs text-gray-400">est.</span>
                <span className="text-lg font-bold text-gray-600">{c.intervenciones}</span>
                <span className="text-xs text-gray-400">int.</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <select value={filtros.carrera} onChange={e => updateFiltro("carrera", e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[160px]">
          <option value="">Todas las carreras</option>
          {carreras.map(c => <option key={c} value={c}>{c}</option>)}
        </select>

        <select value={filtros.motivo} onChange={e => updateFiltro("motivo", e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">Todos los motivos</option>
          {MOTIVOS.map(m => <option key={m} value={m}>{m}</option>)}
        </select>

        <select value={filtros.estado} onChange={e => updateFiltro("estado", e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">Todos los estados</option>
          {ESTADOS.map(e => <option key={e} value={e}>{e}</option>)}
        </select>

        <select value={filtros.resultado} onChange={e => updateFiltro("resultado", e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">Todos los resultados</option>
          {RESULTADOS.map(r => <option key={r} value={r}>{r}</option>)}
        </select>

        <label className="flex items-center gap-2 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white shadow-sm cursor-pointer">
          <input type="checkbox" checked={filtros.seguimiento === "si"}
            onChange={e => updateFiltro("seguimiento", e.target.checked ? "si" : "")}
            className="accent-brand" />
          <span className="text-gray-600">Solo pendientes</span>
        </label>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4 text-red-700 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadData} className="text-red-600 hover:text-red-800 font-medium text-sm">Reintentar</button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="text-center py-12 text-gray-400">Cargando intervenciones...</div>
      )}

      {/* Table */}
      {!loading && items.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-4 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Estudiante</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Carrera</th>
                  <th className="text-center px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Riesgo</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Motivo</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Medio</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Resultado</th>
                  <th className="text-center px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Seg.</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Monitor</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Fecha</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map(inv => (
                  <tr key={inv.id}
                    className="hover:bg-blue-50/50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/ficha/${inv.student_id}`)}
                  >
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-gray-900 text-sm">{inv.nombre || "—"}</div>
                      {inv.observacion && (
                        <div className="text-[11px] text-gray-400 truncate max-w-[200px]" title={inv.observacion}>
                          {inv.observacion}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-500 max-w-[120px] truncate" title={inv.carrera}>
                      {inv.carrera || "—"}
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <RiskBadge nivel={inv.nivel_riesgo} />
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="text-xs text-gray-700">{inv.motivo || "—"}</span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="bg-blue-100 text-blue-700 text-[10px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap">
                        {inv.medio || "—"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      {inv.resultado ? (
                        <span className={`text-[11px] font-medium ${
                          inv.resultado.includes("comprometido") ? "text-green-700"
                          : inv.resultado.includes("No contestó") || inv.resultado.includes("Buzón") ? "text-red-600"
                          : "text-gray-600"
                        }`}>
                          {inv.resultado}
                        </span>
                      ) : <span className="text-gray-300 text-xs">—</span>}
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      {inv.requiere_seguimiento === "si" ? (
                        <span className="bg-orange-100 text-orange-700 text-[10px] font-bold px-2 py-0.5 rounded-full">Pend.</span>
                      ) : (
                        <span className="text-gray-300 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap">
                      {inv.monitor_nombre || "—"}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-400 whitespace-nowrap">
                      {inv.created_at ? new Date(inv.created_at).toLocaleDateString("es-EC", {
                        day: "2-digit", month: "short", year: "numeric"
                      }) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-xs text-gray-400">
            Mostrando {items.length} intervenciones · Click en una fila para ver la ficha del estudiante
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && items.length === 0 && (
        <div className="text-center py-16 text-gray-300">
          <div className="text-4xl mb-3">📋</div>
          <div className="text-sm">No hay intervenciones registradas</div>
          <p className="text-xs text-gray-400 mt-1">Las intervenciones se registran desde la ficha del estudiante</p>
        </div>
      )}
    </div>
  );
}
