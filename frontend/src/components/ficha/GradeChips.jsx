/**
 * GradeChip y MallaChip — chips de calificaciones (Épica 1.5).
 */
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
         style={{ fontSize: "9px", borderColor: "rgba(0,0,0,0.06)" }}
         title={`${asignatura}${docente ? ` — Docente: ${docente}` : ""}`}>
      <span className={`font-semibold ${s.text}`}>{toTitleCase(asignatura)}</span>
      {nota_final != null && <span className={`ml-1 font-bold ${s.text}`}>{nota_final}</span>}
    </div>
  );
}

export function MallaCeldaFija({ asignatura }) {
  const { nombre, nota, estado, repitencias, docente } = asignatura;
  const st = getMallaEstado(estado);
  const hasRepitencia = repitencias && repitencias > 0;

  return (
    <div
      className={`rounded border ${st.bg} ${st.border} px-1 py-0.5 truncate relative`}
      style={{
        fontSize: "8px",
        lineHeight: "1.3",
        borderLeftWidth: hasRepitencia ? "2.5px" : undefined,
        borderLeftColor: hasRepitencia ? "#f97316" : undefined,
      }}
      title={[
        nombre,
        nota != null ? `Nota: ${nota}` : null,
        estado ? `Estado: ${estado}` : null,
        repitencias ? `Repeticiones: ${repitencias}` : null,
        docente ? `Docente: ${docente}` : null,
      ].filter(Boolean).join("\n")}
    >
      <div className={`font-semibold ${st.text} truncate`} style={{ maxWidth: "100%" }}>
        {abreviarAsignatura(nombre, 28)}
      </div>
      {nota != null && (
        <div className={`font-bold ${st.text}`} style={{ fontSize: "9px" }}>
          {nota}
        </div>
      )}
    </div>
  );
}
