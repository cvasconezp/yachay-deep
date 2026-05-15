/**
 * GradeChip, MallaChip, MallaCeldaFija — chips de calificaciones (Épica 1.5).
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
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

/* ─── Popup de intentos (hover) ─── */
function IntentosPopup({ asignatura, anchorRect }) {
  const { nombre, nota, estado, intentos, docente, repitencias } = asignatura;
  const popupRef = useRef(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  useEffect(() => {
    if (!anchorRect || !popupRef.current) return;
    const popup = popupRef.current;
    const pw = popup.offsetWidth;
    const ph = popup.offsetHeight;
    let top = anchorRect.top - ph - 6;
    let left = anchorRect.left + anchorRect.width / 2 - pw / 2;
    if (top < 10) top = anchorRect.bottom + 6;
    if (left < 10) left = 10;
    if (left + pw > window.innerWidth - 10) left = window.innerWidth - pw - 10;
    setPos({ top, left });
  }, [anchorRect]);

  const st = getMallaEstado(estado);
  const estadoLabels = { aprobada: "Aprobada", reprobada: "Reprobada", cursando: "Cursando", no_cursado: "No cursada" };

  return createPortal(
    <div
      ref={popupRef}
      className="fixed z-[9999] bg-white rounded-lg shadow-xl border border-gray-200 p-3 min-w-[220px] max-w-[300px] pointer-events-none"
      style={{ top: pos.top, left: pos.left }}
    >
      <div className="flex items-start gap-2 mb-2">
        <span className={`w-2.5 h-2.5 rounded-full mt-0.5 flex-shrink-0 ${st.bg} border ${st.border}`} />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-bold text-gray-800 leading-tight">{toTitleCase(nombre)}</div>
          <div className={`text-[10px] font-semibold ${st.text} mt-0.5`}>{estadoLabels[estado] || estado}</div>
        </div>
        {nota != null && (
          <span className={`text-sm font-bold ${st.text} flex-shrink-0`}>{nota}</span>
        )}
      </div>

      {docente && (
        <div className="text-[10px] text-gray-500 mb-2 truncate" title={docente}>Docente: {docente}</div>
      )}

      {repitencias > 0 && (
        <div className="text-[10px] text-orange-600 font-semibold mb-1">
          Repeticiones: {repitencias}
        </div>
      )}

      {intentos && intentos.length > 0 && (
        <div className="border-t border-gray-100 pt-2 mt-1">
          <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Historial de matrículas</div>
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-gray-400">
                <th className="text-left font-medium pb-0.5">Período</th>
                <th className="text-center font-medium pb-0.5">Nota</th>
                <th className="text-right font-medium pb-0.5">Estado</th>
              </tr>
            </thead>
            <tbody>
              {intentos.map((int_, i) => {
                const intSt = getMallaEstado(int_.estado);
                return (
                  <tr key={i} className="border-t border-gray-50">
                    <td className="py-0.5 text-gray-700 font-medium">{int_.periodo || "—"}</td>
                    <td className={`py-0.5 text-center font-bold ${intSt.text}`}>{int_.nota != null ? int_.nota : "—"}</td>
                    <td className={`py-0.5 text-right text-[9px] ${intSt.text}`}>
                      {estadoLabels[int_.estado] || int_.estado}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>,
    document.body
  );
}

export function MallaCeldaFija({ asignatura }) {
  const { nombre, nota, estado, repitencias } = asignatura;
  const st = getMallaEstado(estado);
  const hasRepitencia = repitencias && repitencias > 0;
  const [hovered, setHovered] = useState(false);
  const [anchorRect, setAnchorRect] = useState(null);
  const cellRef = useRef(null);
  const timerRef = useRef(null);

  const handleEnter = useCallback(() => {
    clearTimeout(timerRef.current);
    if (cellRef.current) {
      setAnchorRect(cellRef.current.getBoundingClientRect());
      setHovered(true);
    }
  }, []);

  const handleLeave = useCallback(() => {
    timerRef.current = setTimeout(() => setHovered(false), 150);
  }, []);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  return (
    <>
      <div
        ref={cellRef}
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
        className={`rounded border ${st.bg} ${st.border} px-1.5 py-1 truncate relative cursor-default hover:brightness-95 transition-all`}
        style={{
          fontSize: "9px",
          lineHeight: "1.4",
          borderLeftWidth: hasRepitencia ? "2.5px" : undefined,
          borderLeftColor: hasRepitencia ? "#f97316" : undefined,
        }}
      >
        <div className={`font-semibold ${st.text} truncate`} style={{ maxWidth: "100%" }}>
          {abreviarAsignatura(nombre, 28)}
        </div>
        {nota != null && (
          <div className={`font-bold ${st.text}`} style={{ fontSize: "10px" }}>
            {nota}
          </div>
        )}
      </div>
      {hovered && anchorRect && (
        <IntentosPopup asignatura={asignatura} anchorRect={anchorRect} />
      )}
    </>
  );
}
