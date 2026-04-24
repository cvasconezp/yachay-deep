import { useState } from "react";
import { api } from "../services/api";
import { MEDIOS, MOTIVOS, ESTADOS, RESULTADOS } from "../constants/interventions";

const selectClass = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white";
const inputClass = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

/**
 * Modal para registrar la misma intervención a múltiples estudiantes.
 * Props:
 *   selectedStudents: [{ id, nombre, carrera }]
 *   periodo: string (auto-detected)
 *   onClose: () => void
 *   onSaved: () => void
 */
export default function BulkInterventionModal({ selectedStudents, periodo, prefill, onClose, onSaved }) {
  // If prefill has context (e.g. "No entregó actividad de Unidad 1 — Matemáticas"),
  // keep it as a fixed prefix and let user add their own notes
  const contextLine = prefill?.observacion || "";
  const [form, setForm] = useState({
    medio: prefill?.medio || "",
    motivo: prefill?.motivo || "",
    estado: prefill?.estado || "",
    observacion_extra: "",   // user's custom notes (appended to contextLine)
    resultado: prefill?.resultado || "",
    requiere_seguimiento: prefill?.requiere_seguimiento || "no",
    periodo: periodo || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const update = (field, value) => setForm(f => ({ ...f, [field]: value }));

  const isDirty = form.medio || form.motivo || form.observacion_extra;

  const handleCancel = () => {
    if (isDirty && !confirm("Tienes datos sin guardar. ¿Cerrar de todos modos?")) return;
    onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.medio || !form.motivo || !form.estado) {
      setError("Medio, motivo y estado son obligatorios");
      return;
    }
    setSaving(true);
    setError("");
    try {
      // Combine context + user notes into final observacion
      const observacionFinal = [contextLine, form.observacion_extra].filter(Boolean).join(" — ");
      const { observacion_extra, ...rest } = form;
      const payload = {
        student_ids: selectedStudents.map(s => s.id),
        ...rest,
        observacion: observacionFinal,
      };
      const result = await api.bulkCreateInterventions(payload);
      if (result.errors?.length) {
        setError(`Se crearon ${result.created} intervenciones, pero hubo ${result.errors.length} errores.`);
      }
      onSaved(result);
    } catch (err) {
      setError(err.message || "Error al crear intervenciones");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={handleCancel}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="px-6 py-5 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Intervención Masiva</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {selectedStudents.length} estudiante{selectedStudents.length !== 1 ? "s" : ""} seleccionado{selectedStudents.length !== 1 ? "s" : ""}
          </p>
        </div>

        {/* Students list preview */}
        <div className="px-6 pt-4 pb-2">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 max-h-28 overflow-y-auto">
            <div className="flex flex-wrap gap-1.5">
              {selectedStudents.map(s => (
                <span key={s.id} className="inline-flex items-center bg-white border border-blue-200 rounded-full px-2.5 py-0.5 text-xs text-blue-800">
                  {s.nombre?.split(" ").slice(0, 2).join(" ") || `#${s.id}`}
                </span>
              ))}
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Medio de contacto *</label>
              <select value={form.medio} onChange={e => update("medio", e.target.value)} className={selectClass}>
                <option value="">Seleccionar...</option>
                {MEDIOS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Motivo *</label>
              <select value={form.motivo} onChange={e => update("motivo", e.target.value)} className={selectClass}>
                <option value="">Seleccionar...</option>
                {MOTIVOS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Estado del estudiante *</label>
              <select value={form.estado} onChange={e => update("estado", e.target.value)} className={selectClass}>
                <option value="">Seleccionar...</option>
                {ESTADOS.map(e => <option key={e} value={e}>{e}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Resultado</label>
              <select value={form.resultado} onChange={e => update("resultado", e.target.value)} className={selectClass}>
                <option value="">Seleccionar...</option>
                {RESULTADOS.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Observaciones</label>
            {contextLine && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 mb-2 text-xs text-blue-800">
                {contextLine}
              </div>
            )}
            <textarea
              value={form.observacion_extra}
              onChange={e => update("observacion_extra", e.target.value)}
              rows={3}
              className={inputClass + " resize-none"}
              placeholder={contextLine ? "Agregar observaciones adicionales (opcional)..." : "Descripción de la intervención (se aplicará a todos los seleccionados)..."}
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={form.requiere_seguimiento === "si"}
              onChange={e => update("requiere_seguimiento", e.target.checked ? "si" : "no")}
              className="rounded"
            />
            Requiere seguimiento posterior
          </label>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={handleCancel} className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2.5 text-sm font-medium hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={saving} className="flex-1 bg-blue-600 text-white rounded-lg py-2.5 text-sm font-semibold hover:bg-blue-700 disabled:opacity-60">
              {saving ? "Guardando..." : `Guardar ${selectedStudents.length} Intervención${selectedStudents.length !== 1 ? "es" : ""}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
