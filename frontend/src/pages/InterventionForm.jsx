import { useState } from "react";
import { api } from "../services/api";

const MEDIOS = ["WhatsApp", "Llamada telefónica", "Email", "Presencial", "Plataforma AVAC"];
const MOTIVOS = ["Inactividad en AVAC", "Tareas no entregadas", "Bajo rendimiento", "Matrículas/Pagos", "Problemas personales", "Conectividad", "Otro"];
const ESTADOS = ["Activo", "SNA (Sin Novedad Aparente)", "En riesgo", "Retirado", "Recuperado"];
const RESULTADOS = ["Contactado - comprometido a mejorar", "Contactado - situación compleja", "No contestó", "Buzón de voz", "Mensaje enviado sin respuesta"];

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

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2.5 text-sm font-medium hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={saving} className="flex-1 bg-[#1B3A6B] text-white rounded-lg py-2.5 text-sm font-semibold hover:bg-blue-800 disabled:opacity-60">
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
