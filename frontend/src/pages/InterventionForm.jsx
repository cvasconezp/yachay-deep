import { useState } from "react";
import { api } from "../services/api";
import { MEDIOS, MOTIVOS, ESTADOS, RESULTADOS, EVENTOS_CRITICOS } from "../constants/interventions";

export default function InterventionForm({ student, onClose, onSaved }) {
  const [form, setForm] = useState({
    student_id: student.id,
    medio: "",
    motivo: "",
    estado: student.estado_matricula || "",
    asignatura: "",
    docente: "",
    observacion: "",
    resultado: "",
    requiere_seguimiento: "no",
    derivar_bienestar: false,
    tipo_evento_critico: "",
    reporte_bienestar: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const update = (field, value) => setForm(f => ({ ...f, [field]: value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.medio || !form.motivo || !form.estado) {
      setError("Medio, motivo y estado son obligatorios");
      return;
    }
    if (form.derivar_bienestar && (!form.tipo_evento_critico || !form.reporte_bienestar)) {
      setError("Para derivar a Bienestar debe indicar el tipo de evento y el reporte");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.createIntervention(form);
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-5 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Registrar Intervención</h2>
          <p className="text-sm text-gray-500 mt-0.5">{student.nombre}</p>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Medio de contacto *">
              <select value={form.medio} onChange={e => update("medio", e.target.value)} className={selectClass}>
                <option value="">Seleccionar...</option>
                {MEDIOS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </FormField>

            <FormField label="Motivo *">
              <select value={form.motivo} onChange={e => update("motivo", e.target.value)} className={selectClass}>
                <option value="">Seleccionar...</option>
                {MOTIVOS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </FormField>
          </div>

          <FormField label="Estado del estudiante *">
            <select value={form.estado} onChange={e => update("estado", e.target.value)} className={selectClass}>
              <option value="">Seleccionar...</option>
              {ESTADOS.map(e => <option key={e} value={e}>{e}</option>)}
            </select>
          </FormField>

          <div className="grid grid-cols-2 gap-4">
            <FormField label="Asignatura">
              <select value={form.asignatura} onChange={e => update("asignatura", e.target.value)} className={selectClass}>
                <option value="">Todas / General</option>
                {student.calificaciones?.map(g => (
                  <option key={g.asignatura} value={g.asignatura}>{g.asignatura}</option>
                ))}
              </select>
            </FormField>

            <FormField label="Resultado">
              <select value={form.resultado} onChange={e => update("resultado", e.target.value)} className={selectClass}>
                <option value="">Seleccionar...</option>
                {RESULTADOS.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </FormField>
          </div>

          <FormField label="Observaciones">
            <textarea
              value={form.observacion}
              onChange={e => update("observacion", e.target.value)}
              rows={3}
              className={inputClass + " resize-none"}
              placeholder="Descripción detallada de la intervención..."
            />
          </FormField>

          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={form.requiere_seguimiento === "si"}
              onChange={e => update("requiere_seguimiento", e.target.checked ? "si" : "no")}
              className="rounded"
            />
            Requiere seguimiento posterior
          </label>

          {/* Derivación a Bienestar Estudiantil */}
          <div className={`border rounded-xl p-4 transition-colors ${form.derivar_bienestar ? "border-red-300 bg-red-50/50" : "border-gray-200 bg-gray-50/50"}`}>
            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={form.derivar_bienestar}
                onChange={e => update("derivar_bienestar", e.target.checked)}
                className="rounded accent-red-600"
              />
              <span className={form.derivar_bienestar ? "text-red-700" : "text-gray-700"}>
                Derivar a Bienestar Estudiantil
              </span>
            </label>
            <p className="text-[11px] text-gray-400 mt-1 ml-6">
              Activar si el estudiante requiere atención psicológica o de bienestar
            </p>

            {form.derivar_bienestar && (
              <div className="mt-3 space-y-3 ml-1">
                <FormField label="Tipo de evento crítico *">
                  <select value={form.tipo_evento_critico} onChange={e => update("tipo_evento_critico", e.target.value)} className={selectClass}>
                    <option value="">Seleccionar evento...</option>
                    {EVENTOS_CRITICOS.map(ev => <option key={ev} value={ev}>{ev}</option>)}
                  </select>
                </FormField>

                <FormField label="Reporte para Bienestar *">
                  <textarea
                    value={form.reporte_bienestar}
                    onChange={e => update("reporte_bienestar", e.target.value)}
                    rows={4}
                    className={inputClass + " resize-none"}
                    placeholder="Describa la situación del estudiante con el mayor detalle posible. Esta información será enviada al departamento de Bienestar Estudiantil..."
                  />
                </FormField>
              </div>
            )}
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2.5 text-sm font-medium hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={saving} className="flex-1 bg-brand text-white rounded-lg py-2.5 text-sm font-semibold hover:bg-brand-light disabled:opacity-60">
              {saving ? "Guardando..." : "Guardar Intervención"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const selectClass = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white";
const inputClass = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

function FormField({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {children}
    </div>
  );
}
