import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";
import { MOTIVOS, ESTADOS, RESULTADOS, EVENTOS_CRITICOS } from "../constants/interventions";
import { StatCard } from "../components/StatCard";
import { PeriodSelector } from "../components/PeriodSelector";

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
    periodo: "actual",
  });

  // Edit modal
  const [editItem, setEditItem] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);

  // Export
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [colsDisponibles, setColsDisponibles] = useState([]);
  const [colsSeleccionadas, setColsSeleccionadas] = useState(new Set([
    "nombre", "carrera", "nivel_riesgo", "medio", "motivo", "estado",
    "resultado", "requiere_seguimiento", "observacion", "monitor_nombre", "fecha",
  ]));

  useEffect(() => {
    api.getCarreras().then(setCarreras).catch(() => {});
    api.getIntervencionesColumnas().then(setColsDisponibles).catch(() => {});
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
      if (filtros.periodo && filtros.periodo !== "actual") params.periodo = filtros.periodo;
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

  const openEdit = (inv, e) => {
    e.stopPropagation();
    setEditItem(inv);
    setEditForm({
      estado: inv.estado || "",
      resultado: inv.resultado || "",
      requiere_seguimiento: inv.requiere_seguimiento || "",
      observacion: inv.observacion || "",
      derivar_bienestar: inv.derivar_bienestar || false,
      tipo_evento_critico: inv.tipo_evento_critico || "",
      reporte_bienestar: inv.reporte_bienestar || "",
    });
  };

  const handleSaveEdit = async () => {
    if (!editItem) return;
    setSaving(true);
    try {
      await api.updateIntervention(editItem.id, editForm);
      setEditItem(null);
      loadData();
    } catch (e) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  };

  const toggleCol = (key) => {
    setColsSeleccionadas(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const selectAllCols = () => setColsSeleccionadas(new Set(colsDisponibles.map(c => c.key)));
  const deselectAllCols = () => setColsSeleccionadas(new Set(["nombre", "motivo", "fecha"]));

  const handleExport = async () => {
    if (colsSeleccionadas.size === 0) return;
    setExporting(true);
    try {
      const params = new URLSearchParams();
      params.set("columnas", Array.from(colsSeleccionadas).join(","));
      if (filtros.carrera) params.set("carrera", filtros.carrera);
      if (filtros.motivo) params.set("motivo", filtros.motivo);
      if (filtros.estado) params.set("estado", filtros.estado);
      if (filtros.resultado) params.set("resultado", filtros.resultado);
      if (filtros.seguimiento) params.set("seguimiento", filtros.seguimiento);
      if (filtros.periodo && filtros.periodo !== "actual") params.set("periodo", filtros.periodo);

      const blob = await api.exportIntervencionesExcel(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "intervenciones.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message);
    } finally {
      setExporting(false);
    }
  };

  const resumen = data?.resumen || {};
  const items = data?.items || [];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Intervenciones</h1>
          <p className="text-gray-400 text-sm">Seguimiento y monitoreo de intervenciones realizadas</p>
        </div>
        <button
          onClick={() => setExportOpen(!exportOpen)}
          className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm"
        >
          {"📥"} Exportar Excel
        </button>
      </div>

      {/* Export panel */}
      {exportOpen && (
        <div className="bg-white rounded-xl border border-green-200 shadow-sm mb-5 p-5">
          <h3 className="text-sm font-bold text-gray-800 mb-3">Configurar exportación de intervenciones</h3>

          <p className="text-xs text-gray-500 mb-3">
            Los filtros activos del dashboard se aplican a la exportación.
            {(filtros.carrera || filtros.motivo || filtros.estado || filtros.resultado || filtros.seguimiento) ? (
              <span className="text-green-700 font-medium ml-1">
                Filtros activos: {[
                  filtros.carrera && `Carrera: ${filtros.carrera}`,
                  filtros.motivo && `Motivo: ${filtros.motivo}`,
                  filtros.estado && `Estado: ${filtros.estado}`,
                  filtros.resultado && `Resultado: ${filtros.resultado}`,
                  filtros.seguimiento && "Solo pendientes",
                ].filter(Boolean).join(" | ")}
              </span>
            ) : (
              <span className="text-gray-400 ml-1">(sin filtros — se exportan todas)</span>
            )}
          </p>

          {/* Column selection */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-600">Columnas a exportar ({colsSeleccionadas.size} seleccionadas)</span>
              <div className="flex gap-2">
                <button onClick={selectAllCols} className="text-[11px] text-blue-600 hover:underline">Seleccionar todas</button>
                <button onClick={deselectAllCols} className="text-[11px] text-gray-500 hover:underline">Mínimo</button>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-1.5">
              {colsDisponibles.map(col => (
                <label key={col.key} className="flex items-center gap-1.5 text-xs cursor-pointer hover:bg-gray-50 rounded px-1.5 py-1">
                  <input
                    type="checkbox"
                    checked={colsSeleccionadas.has(col.key)}
                    onChange={() => toggleCol(col.key)}
                    className="accent-green-600"
                  />
                  <span className="text-gray-700">{col.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleExport}
              disabled={exporting || colsSeleccionadas.size === 0}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {exporting ? "Generando..." : "Descargar Excel"}
            </button>
            <button onClick={() => setExportOpen(false)} className="text-sm text-gray-500 hover:text-gray-700">Cerrar</button>
          </div>
        </div>
      )}

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
        <PeriodSelector
          value={filtros.periodo}
          onChange={v => updateFiltro("periodo", v)}
        />
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
                  <th className="text-center px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Bienestar</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Monitor</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Fecha</th>
                  <th className="text-center px-3 py-2.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Acción</th>
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
                    <td className="px-3 py-2.5 text-center">
                      {inv.derivar_bienestar ? (
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${inv.email_enviado ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}
                          title={inv.tipo_evento_critico || ""}>
                          {inv.email_enviado ? "Enviado" : "Derivado"}
                        </span>
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
                    <td className="px-3 py-2.5 text-center">
                      <button
                        onClick={(e) => openEdit(inv, e)}
                        className="text-blue-600 hover:text-blue-800 text-xs font-medium hover:underline"
                      >
                        Editar
                      </button>
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

      {/* Edit modal */}
      {editItem && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setEditItem(null)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-gray-900 mb-1">Editar intervención</h3>
            <p className="text-xs text-gray-500 mb-4">{editItem.nombre} — {editItem.motivo}</p>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-600 block mb-1">Estado</label>
                <select value={editForm.estado} onChange={e => setEditForm(f => ({ ...f, estado: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">Sin estado</option>
                  {ESTADOS.map(e => <option key={e} value={e}>{e}</option>)}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-600 block mb-1">Resultado</label>
                <select value={editForm.resultado} onChange={e => setEditForm(f => ({ ...f, resultado: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">Sin resultado</option>
                  {RESULTADOS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-600 block mb-1">Requiere seguimiento</label>
                <select value={editForm.requiere_seguimiento} onChange={e => setEditForm(f => ({ ...f, requiere_seguimiento: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">—</option>
                  <option value="si">Sí</option>
                  <option value="no">No</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-600 block mb-1">Observación</label>
                <textarea value={editForm.observacion} onChange={e => setEditForm(f => ({ ...f, observacion: e.target.value }))}
                  rows={3}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  placeholder="Agregar o actualizar observación..."
                />
              </div>

              {/* Derivación a Bienestar */}
              <div className={`border rounded-lg p-3 ${editForm.derivar_bienestar ? "border-red-300 bg-red-50/50" : "border-gray-200"}`}>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={editForm.derivar_bienestar}
                    onChange={e => setEditForm(f => ({ ...f, derivar_bienestar: e.target.checked }))}
                    className="rounded accent-red-600" />
                  <span className={`font-medium ${editForm.derivar_bienestar ? "text-red-700" : "text-gray-700"}`}>
                    Derivar a Bienestar Estudiantil
                  </span>
                </label>
                {editForm.derivar_bienestar && (
                  <div className="mt-2 space-y-2">
                    <select value={editForm.tipo_evento_critico}
                      onChange={e => setEditForm(f => ({ ...f, tipo_evento_critico: e.target.value }))}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                      <option value="">Tipo de evento...</option>
                      {EVENTOS_CRITICOS.map(ev => <option key={ev} value={ev}>{ev}</option>)}
                    </select>
                    <textarea value={editForm.reporte_bienestar}
                      onChange={e => setEditForm(f => ({ ...f, reporte_bienestar: e.target.value }))}
                      rows={3}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                      placeholder="Reporte para Bienestar Estudiantil..."
                    />
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 mt-5">
              <button onClick={() => setEditItem(null)} className="text-sm text-gray-500 hover:text-gray-700">Cancelar</button>
              <button onClick={handleSaveEdit} disabled={saving}
                className="bg-brand hover:bg-brand/90 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors">
                {saving ? "Guardando..." : "Guardar cambios"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
