import { useState, useMemo } from "react";
import { api } from "../services/api";
import { MEDIOS, MOTIVOS, ESTADOS, RESULTADOS, EVENTOS_CRITICOS, DERIVACIONES } from "../constants/interventions";

export default function InterventionForm({ student, onClose, onSaved }) {
  // Determine active periodo from student's enrollments or fallback
  const activePeriodo = useMemo(() => {
    if (student.enrollments?.length) {
      // Pick the most common periodo from enrollments
      const periodos = student.enrollments.map(e => e.periodo).filter(Boolean);
      if (periodos.length) return periodos[0];
    }
    return "";
  }, [student]);

  // Build unique asignaturas from enrollments (primary) or calificaciones (fallback)
  const asignaturas = useMemo(() => {
    if (student.enrollments?.length) {
      const seen = new Set();
      return student.enrollments
        .filter(e => {
          const key = (e.asignatura || "").toUpperCase();
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        })
        .map(e => ({
          asignatura: e.asignatura,
          docente: e.docente || "",
          nivel: e.nivel,
        }));
    }
    // Fallback to calificaciones
    if (student.calificaciones?.length) {
      const seen = new Set();
      return student.calificaciones
        .filter(g => {
          const key = (g.asignatura || "").toUpperCase();
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        })
        .map(g => ({
          asignatura: g.asignatura,
          docente: g.docente || "",
          nivel: null,
        }));
    }
    return [];
  }, [student]);

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
    // Derivaciones
    derivar_bienestar: false,
    derivar_financiero: false,
    derivar_coordinacion: false,
    derivar_docente: false,
    tipo_evento_critico: "",
    reporte_bienestar: "",
    reporte_derivacion: "",
    periodo: activePeriodo,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const update = (field, value) => setForm(f => ({ ...f, [field]: value }));

  // Auto-fill docente when asignatura is selected
  const handleAsignaturaChange = (value) => {
    update("asignatura", value);
    if (value) {
      const match = asignaturas.find(a => a.asignatura === value);
      if (match?.docente) {
        update("docente", match.docente);
      }
    } else {
      update("docente", "");
    }
  };

  const anyDerivacion = form.derivar_bienestar || form.derivar_financiero || form.derivar_coordinacion || form.derivar_docente;

  const isDirty = form.medio || form.motivo || form.observacion || form.resultado;

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
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={handleCancel}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
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

          <FormField label="Período">
            <input
              type="text"
              value={form.periodo}
              onChange={e => update("periodo", e.target.value)}
              className={inputClass}
              placeholder="P67, P68, etc."
              readOnly={!!activePeriodo}
            />
            {activePeriodo && (
              <p className="text-[10px] text-gray-400 mt-0.5">Auto-detectado del semestre activo</p>
            )}
          </FormField>

          <div className="grid grid-cols-2 gap-4">
            <FormField label="Asignatura">
              <select value={form.asignatura} onChange={e => handleAsignaturaChange(e.target.value)} className={selectClass}>
                <option value="">Todas / General</option>
                {asignaturas.map(a => (
                  <option key={a.asignatura} value={a.asignatura}>
                    {a.nivel ? `N${a.nivel} - ` : ""}{a.asignatura}
                  </option>
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

          {form.asignatura && (
            <FormField label="Docente">
              <input
                type="text"
                value={form.docente}
                onChange={e => update("docente", e.target.value)}
                className={inputClass}
                placeholder="Nombre del docente"
              />
              {form.docente && (
                <p className="text-[10px] text-gray-400 mt-0.5">Auto-llenado desde matrícula</p>
              )}
            </FormField>
          )}

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

          {/* ─── Sección de Derivaciones ─── */}
          <div className="border rounded-xl p-4 border-gray-200 bg-gray-50/50 space-y-3">
            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Derivaciones</p>

            {DERIVACIONES.map(d => {
              const fieldKey = `derivar_${d.key}`;
              const isActive = form[fieldKey];
              return (
                <div key={d.key} className={`rounded-lg p-3 transition-colors ${isActive ? "bg-amber-50 border border-amber-300" : "bg-white border border-gray-100"}`}>
                  <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!!isActive}
                      onChange={e => update(fieldKey, e.target.checked)}
                      className="rounded accent-amber-600"
                    />
                    <span className={isActive ? "text-amber-800" : "text-gray-700"}>
                      {d.label}
                    </span>
                  </label>
                  <p className="text-[11px] text-gray-400 mt-0.5 ml-6">{d.desc}</p>

                  {/* Bienestar specific fields */}
                  {d.key === "bienestar" && isActive && (
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
                          placeholder="Describa la situación del estudiante con el mayor detalle posible..."
                        />
                      </FormField>
                    </div>
                  )}

                  {/* Other derivations: optional note */}
                  {d.key !== "bienestar" && isActive && (
                    <div className="mt-3 ml-1">
                      <FormField label={`Nota para ${d.label}`}>
                        <textarea
                          value={form.reporte_derivacion}
                          onChange={e => update("reporte_derivacion", e.target.value)}
                          rows={2}
                          className={inputClass + " resize-none"}
                          placeholder={`Detalle para ${d.label}...`}
                        />
                      </FormField>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={handleCancel} className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-2.5 text-sm font-medium hover:bg-gray-50">
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
