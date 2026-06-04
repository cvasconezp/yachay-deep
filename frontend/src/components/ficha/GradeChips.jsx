/**
 * GradeChip, MallaChip, MallaCeldaFija — chips de calificaciones (Épica 1.5).
 */
import { useState } from "react";
import { getNoteStyleHistorico, toTitleCase, getMallaEstado, abreviarAsignatura } from "./fichaHelpers";

export function GradeChip({ asignatura, nota_final, docente }) {
  const s = getNoteStyleHistorico(nota_final);
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border ${s.bg} ${s.text}`}
         style={{ fontSize: "10px", borderColor: "rgba(0,0,0,0.08)" }}
         title={docente ? `Docente: ${docente}` : undefined}>
      <span className="font-semibold truncate max-w-[120px]">{toTitleCase(asignatura)}</span>
      <span className="font-bold">{nota_final ?? "—"}</span>
    </div>
  );
}

export function MallaChip({ asignatura, nota_final, docente }) {
  const s = getNoteStyleHistorico(nota_final);
  return (
    <div className={`rounded border px-1 py-0.5 truncate ${s.bg}`}
         style={{ fontSize: "10px", borderColor: "rgba(0,0,0,0.06)" }}
         title={`${asignatura}${docente ? ` — Docente: ${docente}` : ""}`}>
      <span className={`font-semibold ${s.text}`}>{toTitleCase(asignatura)}</span>
      {nota_final != null && <span className={`ml-1 font-bold ${s.text}`}>{nota_final}</span>}
    </div>
  );
}

export function MallaCeldaFija({ asignatura }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const s = getMallaEstado(asignatura.estado);
  const titleName = toTitleCase(asignatura.nombre) || "";
  const shortName = abreviarAsignatura(titleName);

  const esRepeticion = asignatura.es_repeticion;
  const numIntentos = asignatura.num_intentos;
  const nota = asignatura.nota_vigente;

  return (
    <div
      className={`relative border ${s.border} ${s.bg} rounded cursor-default transition-shadow hover:shadow-sm`}
      style={{
        padding: "5px 7px",
        ...(esRepeticion ? { borderLeftWidth: "3px", borderLeftColor: "#f97316", borderLeftStyle: "solid" } : {}),
      }}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* Badge de repetición */}
      {esRepeticion && (
        <div className="absolute -top-1.5 -right-1.5 bg-orange-500 text-white font-bold rounded-full flex items-center justify-center shadow-sm z-10"
             style={{ width: "16px", height: "16px", fontSize: "8px" }}
             title={`${numIntentos} intentos`}>
          {numIntentos}
        </div>
      )}

      {/* Nombre abreviado + nota */}
      <div className="overflow-hidden" style={{ minWidth: 0 }}>
        <div className="flex items-start gap-1" style={{ minWidth: 0 }}>
          <div className="leading-snug" style={{ fontSize: "10.5px", color: "#1f2937", flex: "1 1 0%", minWidth: 0, wordBreak: "break-word" }}>
            {shortName}
          </div>
          <div className={`font-bold ${s.text}`} style={{ fontSize: "12px", flexShrink: 0, textAlign: "right" }}>
            {nota != null ? nota : "—"}
          </div>
        </div>
      </div>

      {/* Tooltip: nombre completo + historial de intentos */}
      {showTooltip && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-1 bg-gray-900 text-white rounded-lg shadow-xl px-3 py-2"
             style={{ minWidth: "200px", maxWidth: "300px", fontSize: "10px" }}>
          <div className="font-bold mb-0.5" style={{ fontSize: "11px", color: esRepeticion ? "#fdba74" : "#e5e7eb", whiteSpace: "normal" }}>
            {titleName}
          </div>
          {esRepeticion && asignatura.intentos?.length > 0 && (
            <>
              <div className="font-semibold text-gray-300 mb-0.5">{numIntentos} intentos:</div>
              {asignatura.intentos.map((intento, i) => (
                <div key={i} className="flex justify-between gap-3 py-px border-t border-gray-700 whitespace-nowrap">
                  <span className="text-gray-300">{intento.periodo || "Actual"}</span>
                  <span className={
                    intento.estado === "aprobada" ? "text-green-400 font-bold" :
                    intento.estado === "reprobada" ? "text-red-400 font-bold" :
                    intento.estado === "cursando" ? "text-amber-400" :
                    "text-yellow-400"
                  }>
                    {intento.nota != null ? intento.nota : "—"}
                  </span>
                </div>
              ))}
            </>
          )}
          <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900"></div>
        </div>
      )}
    </div>
  );
}
