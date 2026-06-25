/**
 * RecoveryScoreCard — muestra el score de recuperabilidad del estudiante.
 * Se integra en la FichaEstudiante (Épica 1.4 + 1.5).
 */
import { useState, useEffect } from "react";
import { api } from "../../services/api";

const NIVEL_STYLES = {
  alto:  { bg: "bg-green-50",  text: "text-green-700",  ring: "ring-green-400", bar: "bg-green-500", icon: "✅" },
  medio: { bg: "bg-yellow-50", text: "text-yellow-700", ring: "ring-yellow-400", bar: "bg-yellow-500", icon: "⚠️" },
  bajo:  { bg: "bg-red-50",    text: "text-red-700",    ring: "ring-red-400", bar: "bg-red-500", icon: "🔴" },
};

const COMPONENT_LABELS = {
  actividad: "Actividad reciente",
  tareas: "Tareas entregadas",
  calificaciones: "Calificaciones",
  historial: "Historial matrícula",
  tendencia: "Tendencia",
};

export default function RecoveryScoreCard({ studentId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!studentId) return;
    setLoading(true);
    setError(null);
    api.getRecoveryScore(studentId)
      .then(setData)
      .catch(err => setError(err?.message || "Error al cargar score"))
      .finally(() => setLoading(false));
  }, [studentId]);

  if (loading) {
    return (
      <div className="px-3 py-2 text-[11px] text-gray-400 text-center">
        Calculando score de recuperabilidad...
      </div>
    );
  }

  if (error || !data) return null;

  const style = NIVEL_STYLES[data.nivel] || NIVEL_STYLES.medio;

  return (
    <div className={`border-t border-gray-200 ${style.bg}`}>
      <div className="bg-[#1B3A6B] text-white px-3 py-1 text-[10px] font-bold uppercase tracking-wider flex items-center justify-between">
        <span>Score de Recuperabilidad</span>
        <span className="text-white/60 normal-case tracking-normal font-normal">
          {style.icon} {data.nivel.charAt(0).toUpperCase() + data.nivel.slice(1)}
        </span>
      </div>
      <div className="px-3 py-2">
        {/* Score principal */}
        <div className="flex items-center gap-3 mb-2">
          <div className={`text-2xl font-bold ${style.text}`}>
            {data.score_total}
          </div>
          <div className="flex-1">
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${style.bar} transition-all duration-500`}
                style={{ width: `${data.score_total}%` }}
              />
            </div>
          </div>
          <span className="text-[10px] text-gray-400">/100</span>
        </div>

        {/* Componentes desglosados */}
        <div className="grid grid-cols-5 gap-1 mb-2">
          {Object.entries(data.componentes).map(([key, comp]) => (
            <div key={key} className="text-center">
              <div className="text-[9px] text-gray-500 truncate" title={COMPONENT_LABELS[key]}>
                {COMPONENT_LABELS[key]}
              </div>
              <div className="h-1 bg-gray-200 rounded-full overflow-hidden mt-0.5 mx-1">
                <div
                  className={`h-full rounded-full ${comp.score >= 65 ? "bg-green-400" : comp.score >= 35 ? "bg-yellow-400" : "bg-red-400"}`}
                  style={{ width: `${comp.score}%` }}
                />
              </div>
              <div className="text-[10px] font-semibold text-gray-700 mt-0.5">
                {comp.score}
              </div>
            </div>
          ))}
        </div>

        {/* Recomendación */}
        <div className="text-[10px] text-gray-600 bg-white/60 rounded px-2 py-1 border border-gray-200">
          💡 {data.recomendacion}
        </div>
      </div>
    </div>
  );
}
