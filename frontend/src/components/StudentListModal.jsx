import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";

const TIPO_LABELS = {
  repitentes: "Estudiantes Repitentes",
  condicionados: "Estudiantes Condicionados (3ra Matrícula)",
  riesgo_alto: "Estudiantes — Riesgo Alto",
  riesgo_medio: "Estudiantes — Riesgo Medio",
  riesgo_bajo: "Estudiantes — Riesgo Bajo",
};
const TIPO_COLORS = {
  repitentes: "text-orange-700",
  condicionados: "text-purple-700",
  riesgo_alto: "text-red-700",
  riesgo_medio: "text-yellow-700",
  riesgo_bajo: "text-green-700",
};

function ModalContent({ tipo, estudiantes, total, loading, onClose, onNavigate }) {
  const isRepitentes = tipo === "repitentes";
  const isCondicionados = tipo === "condicionados";
  const showAsignaturas = isRepitentes || isCondicionados;

  const exportCSV = () => {
    if (!estudiantes || estudiantes.length === 0) return;
    const headers = ["Cédula", "Nombre", "Correo", "Carrera", "Nivel", "Riesgo", "Promedio", "Días sin acceso", "% Tareas", "Estado matrícula"];
    if (isRepitentes) headers.push("Asignaturas con repitencia");
    if (isCondicionados) headers.push("Asignaturas condicionadas");
    const rows = estudiantes.map(e => {
      const row = [
        e.cedula || "", e.nombre || "", e.correo_institucional || "", e.carrera || "",
        e.nivel_academico ?? "", e.nivel_riesgo || "", e.promedio_calificaciones ?? "",
        e.dias_sin_acceso ?? "", e.porcentaje_tareas != null ? `${Math.round(e.porcentaje_tareas)}%` : "",
        e.estado_matricula || "",
      ];
      if (isRepitentes) row.push((e.asignaturas_repitencia || []).join(" | "));
      if (isCondicionados) row.push((e.asignaturas_condicionado || []).join(" | "));
      return row;
    });
    const csv = [headers, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${tipo}_estudiantes.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-[95vw] max-w-5xl max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className={`text-lg font-bold ${TIPO_COLORS[tipo] || "text-gray-800"}`}>
              {TIPO_LABELS[tipo] || tipo}
            </h2>
            <p className="text-xs text-gray-400">{total} estudiante{total !== 1 ? "s" : ""}</p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={exportCSV} disabled={!estudiantes?.length}
              className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors">
              {"📥"} Exportar CSV
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
          </div>
        </div>

        {/* Body */}
        <div className="overflow-auto flex-1 px-6 py-3">
          {loading ? (
            <div className="text-center py-12 text-gray-400">Cargando listado...</div>
          ) : !estudiantes?.length ? (
            <div className="text-center py-12 text-gray-400">No se encontraron estudiantes</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-200">
                  <th className="py-2 pr-2">Nombre</th>
                  <th className="py-2 pr-2">Cédula</th>
                  <th className="py-2 pr-2">Carrera</th>
                  {isRepitentes && <th className="py-2 pr-2">Asignatura(s) repitencia</th>}
                  {isCondicionados && <th className="py-2 pr-2">Asignatura(s) condicionada</th>}
                  <th className="py-2 pr-2 text-center">Nivel</th>
                  <th className="py-2 pr-2 text-center">Riesgo</th>
                  <th className="py-2 pr-2 text-center">Prom.</th>
                  <th className="py-2 pr-2 text-center">Días s/a</th>
                  <th className="py-2 pr-2 text-center">% Tareas</th>
                </tr>
              </thead>
              <tbody>
                {estudiantes.map((e, i) => (
                  <tr key={e.id || i} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 pr-2 max-w-[200px]">
                      <button
                        className="font-medium text-blue-700 hover:text-blue-900 hover:underline truncate block text-left max-w-full"
                        title={`${e.nombre} — abrir ficha`}
                        onClick={() => { onClose(); onNavigate(e.id); }}
                      >{e.nombre}</button>
                    </td>
                    <td className="py-2 pr-2 text-gray-500 text-xs">{e.cedula}</td>
                    <td className="py-2 pr-2 text-gray-600 text-xs max-w-[140px] truncate" title={e.carrera}>{e.carrera}</td>
                    {isRepitentes && (
                      <td className="py-2 pr-2 text-xs text-orange-700 max-w-[200px]">
                        <div className="flex flex-wrap gap-1">
                          {(e.asignaturas_repitencia || []).map((a, j) => (
                            <span key={j} className="bg-orange-50 border border-orange-200 rounded px-1.5 py-0.5 text-[10px] truncate max-w-[180px]" title={a}>{a}</span>
                          ))}
                        </div>
                      </td>
                    )}
                    {isCondicionados && (
                      <td className="py-2 pr-2 text-xs text-purple-700 max-w-[200px]">
                        <div className="flex flex-wrap gap-1">
                          {(e.asignaturas_condicionado || []).map((a, j) => (
                            <span key={j} className="bg-purple-50 border border-purple-200 rounded px-1.5 py-0.5 text-[10px] truncate max-w-[180px]" title={a}>{a}</span>
                          ))}
                        </div>
                      </td>
                    )}
                    <td className="py-2 pr-2 text-center text-gray-600">{e.nivel_academico ?? "—"}</td>
                    <td className="py-2 pr-2 text-center">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        e.nivel_riesgo === "Alto" ? "bg-red-100 text-red-700" :
                        e.nivel_riesgo === "Medio" ? "bg-yellow-100 text-yellow-700" :
                        e.nivel_riesgo === "Bajo" ? "bg-green-100 text-green-700" :
                        "bg-gray-100 text-gray-500"
                      }`}>{e.nivel_riesgo || "—"}</span>
                    </td>
                    <td className="py-2 pr-2 text-center text-gray-700">{e.promedio_calificaciones != null ? Math.round(e.promedio_calificaciones) : "—"}</td>
                    <td className="py-2 pr-2 text-center text-gray-700">{e.dias_sin_acceso ?? "—"}</td>
                    <td className="py-2 pr-2 text-center text-gray-700">{e.porcentaje_tareas != null ? `${Math.round(e.porcentaje_tareas)}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Hook + Component combo for the student list modal.
 * Usage:
 *   const { openStudentList, StudentListModalEl } = useStudentListModal({ periodo, carrera });
 *   // call openStudentList("repitentes") to open
 *   // render {StudentListModalEl} in JSX
 */
export function useStudentListModal({ periodo, carrera } = {}) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [tipo, setTipo] = useState("");
  const [estudiantes, setEstudiantes] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const openStudentList = async (tipoParam) => {
    setTipo(tipoParam);
    setOpen(true);
    setLoading(true);
    setEstudiantes([]);
    try {
      const params = { tipo: tipoParam };
      if (periodo) params.periodo = periodo;
      if (carrera) params.carrera = carrera;
      const res = await api.getEstudiantesListado(params);
      setEstudiantes(res.estudiantes || []);
      setTotal(res.total || 0);
    } catch (e) {
      console.error("Error loading student list:", e);
    } finally {
      setLoading(false);
    }
  };

  const StudentListModalEl = open ? (
    <ModalContent
      tipo={tipo}
      estudiantes={estudiantes}
      total={total}
      loading={loading}
      onClose={() => setOpen(false)}
      onNavigate={(id) => navigate(`/ficha/${id}`)}
    />
  ) : null;

  return { openStudentList, StudentListModalEl };
}

export default ModalContent;
