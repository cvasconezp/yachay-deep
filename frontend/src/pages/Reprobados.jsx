import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { SummaryCard } from "../components/StatCard";
import { PeriodSelector } from "../components/PeriodSelector";

const CAUSA_STYLE = {
  "Desconexión": "bg-orange-100 text-orange-700",
  "Académica": "bg-blue-100 text-blue-700",
  "Administrativa": "bg-purple-100 text-purple-700",
  "Sin datos": "bg-gray-100 text-gray-500",
};

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const num = (v, d = 0) => (v == null ? "—" : Number(v).toFixed(d));

export default function Reprobados() {
  const [data, setData] = useState(null);
  const [carreras, setCarreras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtros, setFiltros] = useState({
    carrera: "",
    nivel: "",
    periodo: "",
    grupo: "",
    riesgo: "",
    causa: "",
    condicion: "",       // "" | "repitentes" | "condicionados"
    sin_interv: false,
  });
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const estudiantes = data?.estudiantes || [];
  const kpis = data?.kpis || {};
  const notaAprob = data?.nota_aprobacion ?? 70;

  const gruposDisponibles = useMemo(() => {
    const set = new Set();
    estudiantes.forEach(e => { if (e.grupo) set.add(String(e.grupo)); });
    return [...set].sort((a, b) => a.localeCompare(b, "es", { numeric: true }));
  }, [estudiantes]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (filtros.periodo) params.periodo = filtros.periodo;
      if (filtros.carrera) params.carrera = filtros.carrera;
      if (filtros.nivel) params.nivel = filtros.nivel;
      const [resp, carrerasData] = await Promise.all([
        api.getReprobadosAnalytics(params),
        api.getCarreras(),
      ]);
      setData(resp);
      setCarreras(carrerasData);
    } catch (e) {
      setError("No se pudieron cargar los datos de reprobados.");
    } finally {
      setLoading(false);
    }
  }, [filtros.periodo, filtros.carrera, filtros.nivel]);

  useEffect(() => { loadData(); }, [loadData]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return estudiantes.filter(e => {
      if (q && !(e.nombre || "").toLowerCase().includes(q)) return false;
      if (filtros.grupo && String(e.grupo || "") !== filtros.grupo) return false;
      if (filtros.riesgo && e.nivel_riesgo !== filtros.riesgo) return false;
      if (filtros.causa && e.causa_probable !== filtros.causa) return false;
      if (filtros.sin_interv && !e.sin_intervencion) return false;
      if (filtros.condicion === "condicionados" && !e.es_tercera_matricula) return false;
      if (filtros.condicion === "repitentes" && !e.es_repitente) return false;
      return true;
    });
  }, [estudiantes, search, filtros]);

  const [exporting, setExporting] = useState(false);
  const handleExport = async () => {
    setExporting(true);
    try {
      const params = {};
      if (filtros.periodo) params.periodo = filtros.periodo;
      if (filtros.carrera) params.carrera = filtros.carrera;
      if (filtros.nivel) params.nivel = filtros.nivel;
      const blob = await api.exportReprobadosExcel(params);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `informe_reprobados_${filtros.periodo || "actual"}.xlsx`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert("No se pudo exportar: " + (e.message || "error"));
    } finally {
      setExporting(false);
    }
  };

  const selectClass = "border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";
  const causaChip = (c) => (
    <span className={`text-[11px] px-2 py-0.5 rounded font-medium ${CAUSA_STYLE[c] || "bg-gray-100 text-gray-500"}`}>{c || "—"}</span>
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reprobados</h1>
          <p className="text-gray-500 text-sm">
            Estudiantes que reprobaron ≥1 asignatura (período · carrera · nivel), con indicadores de posible causa y abandono
          </p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting || loading}
          className="inline-flex items-center gap-2 bg-green-600 hover:bg-green-700 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg"
          title="Descarga un Excel con gráficas y una lectura automática de los datos"
        >
          {exporting ? "Generando…" : "📊 Exportar Excel (con análisis)"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
      )}

      {!loading && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
          <SummaryCard label="Total reprobados" value={kpis.total_reprobados ?? 0} color="red" />
          <SummaryCard label="Asignaturas reprobadas" value={kpis.total_asignaturas_reprobadas ?? 0} color="red" />
          <SummaryCard label="Promedio reprobados" value={kpis.promedio_reprobados ?? "—"} color="yellow" />
          <SummaryCard label="En riesgo alto" value={kpis.riesgo_alto ?? 0} color="red" />
          <SummaryCard label="Sin intervención" value={kpis.sin_intervencion ?? 0} color="blue" />
        </div>
      )}

      {/* Desglose por causa probable */}
      {!loading && kpis.por_causa && Object.keys(kpis.por_causa).length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4 text-sm">
          <span className="text-gray-500">Causa probable:</span>
          {Object.entries(kpis.por_causa).map(([c, n]) => (
            <span key={c} className={`px-2 py-0.5 rounded font-medium ${CAUSA_STYLE[c] || "bg-gray-100 text-gray-500"}`}>{c}: {n}</span>
          ))}
        </div>
      )}

      {/* Filtros */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4 flex flex-wrap gap-3 items-end">
        <PeriodSelector value={filtros.periodo} onChange={v => setFiltros(f => ({ ...f, periodo: v }))} />

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Carrera</label>
          <select value={filtros.carrera} onChange={e => setFiltros(f => ({ ...f, carrera: e.target.value, grupo: "" }))} className={`${selectClass} min-w-[220px]`}>
            <option value="">Todas las carreras</option>
            {filtros.carrera && !carreras.includes(filtros.carrera) && (<option value={filtros.carrera}>{filtros.carrera}</option>)}
            {carreras.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Nivel</label>
          <select value={filtros.nivel} onChange={e => setFiltros(f => ({ ...f, nivel: e.target.value, grupo: "" }))} className={selectClass}>
            <option value="">Todos</option>
            {[1,2,3,4,5,6,7,8].map(n => <option key={n} value={n}>Nivel {n}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Grupo</label>
          <select value={filtros.grupo} onChange={e => setFiltros(f => ({ ...f, grupo: e.target.value }))} className={selectClass} disabled={gruposDisponibles.length === 0}>
            <option value="">Todos</option>
            {gruposDisponibles.map(g => <option key={g} value={g}>Grupo {g}</option>)}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Riesgo</label>
          <select value={filtros.riesgo} onChange={e => setFiltros(f => ({ ...f, riesgo: e.target.value }))} className={selectClass}>
            <option value="">Todos</option>
            <option value="Alto">Alto</option>
            <option value="Medio">Medio</option>
            <option value="Bajo">Bajo</option>
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Causa probable</label>
          <select value={filtros.causa} onChange={e => setFiltros(f => ({ ...f, causa: e.target.value }))} className={selectClass}>
            <option value="">Todas</option>
            <option value="Desconexión">Desconexión</option>
            <option value="Académica">Académica</option>
            <option value="Administrativa">Administrativa</option>
            <option value="Sin datos">Sin datos</option>
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">Condición especial</label>
          <select value={filtros.condicion} onChange={e => setFiltros(f => ({ ...f, condicion: e.target.value }))} className={selectClass}>
            <option value="">Todos</option>
            <option value="repitentes">Repitentes (2da matrícula)</option>
            <option value="condicionados">Condicionados (3ra matrícula)</option>
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-600 pb-2">
          <input type="checkbox" checked={filtros.sin_interv} onChange={e => setFiltros(f => ({ ...f, sin_interv: e.target.checked }))} />
          Sin intervención
        </label>

        <div className="ml-auto flex items-center gap-3">
          <input type="text" placeholder="Buscar estudiante..." value={search} onChange={e => setSearch(e.target.value)}
                 className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <span className="text-sm text-gray-500">{filtered.length} estudiantes</span>
        </div>
      </div>

      {loading ? (
        <div className="text-gray-400 py-12 text-center">Cargando…</div>
      ) : filtered.length === 0 ? (
        <div className="text-gray-400 py-12 text-center">No hay reprobados con los filtros actuales.</div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-auto max-h-[70vh]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-gray-50">
              <tr className="text-left text-gray-600 border-b border-gray-200">
                <th className="px-3 py-2 font-semibold sticky left-0 bg-gray-50 z-20">Estudiante</th>
                <th className="px-3 py-2 font-semibold text-center">Niv.</th>
                <th className="px-3 py-2 font-semibold">Asignaturas reprobadas</th>
                <th className="px-3 py-2 font-semibold text-center">Prom.</th>
                <th className="px-3 py-2 font-semibold text-center">Riesgo</th>
                <th className="px-3 py-2 font-semibold text-center" title="Índice de compromiso">Comp.</th>
                <th className="px-3 py-2 font-semibold text-center" title="Días desde el último acceso a AVAC">Días s/AVAC</th>
                <th className="px-3 py-2 font-semibold text-center">% Tareas</th>
                <th className="px-3 py-2 font-semibold text-center">Matrícula</th>
                <th className="px-3 py-2 font-semibold text-center" title="Intervenciones registradas">Interv.</th>
                <th className="px-3 py-2 font-semibold text-center" title="Prob. reprobación / deserción (ML)">Prob. R / D</th>
                <th className="px-3 py-2 font-semibold text-center" title="Score de recuperabilidad">Recup.</th>
                <th className="px-3 py-2 font-semibold">Causa probable</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(e => (
                <tr key={e.student_id} className="border-b border-gray-100 hover:bg-blue-50/40 cursor-pointer"
                    onClick={() => navigate(`/students/${e.student_id}/ficha`)} title="Abrir ficha del estudiante">
                  <td className="px-3 py-2 sticky left-0 bg-white z-10">
                    <div className="font-medium text-gray-800">{e.nombre}</div>
                    <div className="text-[11px] text-gray-400">
                      {e.grupo ? `G${e.grupo} · ` : ""}{e.carrera}
                      {e.es_tercera_matricula ? " · 3ra matrícula" : e.es_repitente ? " · 2da matrícula" : ""}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-center text-gray-600">{e.nivel ?? "—"}</td>
                  <td className="px-3 py-2">
                    <span className="font-semibold text-red-600">{e.num_reprobadas}</span>
                    <span className="text-gray-500"> — </span>
                    <span className="text-gray-700">{(e.reprobadas || []).map(r => `${r.asignatura} (${r.nota})`).join(", ")}</span>
                  </td>
                  <td className={`px-3 py-2 text-center font-semibold ${e.promedio != null && e.promedio < notaAprob ? "text-red-600" : "text-gray-700"}`}>{e.promedio ?? "—"}</td>
                  <td className="px-3 py-2 text-center">{e.nivel_riesgo || "—"}</td>
                  <td className="px-3 py-2 text-center">{pct(e.indice_compromiso)}</td>
                  <td className={`px-3 py-2 text-center ${e.dias_sin_acceso != null && e.dias_sin_acceso >= 14 ? "text-red-600 font-semibold" : "text-gray-600"}`}>{e.dias_sin_acceso ?? "—"}</td>
                  <td className={`px-3 py-2 text-center ${e.porcentaje_tareas != null && e.porcentaje_tareas < 50 ? "text-red-600" : "text-gray-600"}`}>{e.porcentaje_tareas != null ? `${Math.round(e.porcentaje_tareas)}%` : "—"}</td>
                  <td className="px-3 py-2 text-center text-gray-600 text-[11px]">{e.estado_matricula || "—"}</td>
                  <td className="px-3 py-2 text-center">
                    {e.num_intervenciones}
                    {e.intervencion_sin_respuesta && <span className="ml-1 text-amber-600" title="Última intervención sin respuesta / con seguimiento pendiente">⚠</span>}
                    {e.sin_intervencion && <span className="text-gray-300" title="Sin intervención registrada"> ·</span>}
                  </td>
                  <td className="px-3 py-2 text-center text-gray-600 text-[11px]">{pct(e.prob_reprobacion)} / {pct(e.prob_desercion)}</td>
                  <td className="px-3 py-2 text-center text-gray-600">{num(e.score_recuperabilidad)}</td>
                  <td className="px-3 py-2">{causaChip(e.causa_probable)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
