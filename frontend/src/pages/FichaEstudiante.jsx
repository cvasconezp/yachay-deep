import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";
import InterventionForm from "./InterventionForm";

// ── Helpers de color ──────────────────────────────────────────────────────────
function getNoteStyle(nota, max = 40) {
  if (nota == null) return { bg: "", text: "text-gray-400", border: "" };
  const pct = nota / max;
  if (pct >= 0.70) return { bg: "bg-green-100",  text: "text-green-800",  border: "border-green-300" };
  if (pct >= 0.50) return { bg: "bg-yellow-100", text: "text-yellow-800", border: "border-yellow-300" };
  return               { bg: "bg-red-100",    text: "text-red-700",   border: "border-red-300" };
}

/**
 * Mapea el diagnóstico computado (Framework_FichaEst §3.5) a colores + etiqueta.
 * 4 estados: Aprobación | Riesgo Académico | Riesgo de Deserción | En riesgo
 */
function getDiagnosticoStyle(diagnostico) {
  switch (diagnostico) {
    case "Aprobación":
      return { bg: "bg-green-100",  text: "text-green-800",  badge: "bg-green-500",  label: "Aprobación" };
    case "Riesgo Académico":
      return { bg: "bg-yellow-100", text: "text-yellow-800", badge: "bg-yellow-500", label: "Riesgo Académico" };
    case "Riesgo de Deserción":
      return { bg: "bg-orange-100", text: "text-orange-700", badge: "bg-orange-500", label: "Riesgo de Deserción" };
    case "En riesgo":
      return { bg: "bg-red-100",    text: "text-red-700",    badge: "bg-red-600",    label: "En riesgo" };
    default:
      return { bg: "bg-gray-100",   text: "text-gray-500",   badge: "bg-gray-400",   label: "Sin datos" };
  }
}

/** Mantener compatibilidad con nivel_riesgo (Alto/Medio/Bajo) del ETL */
function getRiesgoStyle(nivel) {
  if (nivel === "Alto")  return { bg: "bg-red-100",    text: "text-red-700",    label: "En riesgo" };
  if (nivel === "Medio") return { bg: "bg-yellow-100", text: "text-yellow-700", label: "Riesgo moderado" };
  if (nivel === "Bajo")  return { bg: "bg-green-100",  text: "text-green-700",  label: "Sin riesgo" };
  return                        { bg: "bg-gray-100",   text: "text-gray-500",   label: "Sin evaluar" };
}

function getCompromisoLabel(val) {
  if (val == null) return "—";
  if (val < 0.3) return "Bajo";
  if (val < 0.6) return "Medio";
  return "Alto";
}

/** Compactar texto de acceso AVAC: "3 días 15 horas 20 minutos" → "3d 15h 20m" */
function compactarAcceso(texto) {
  if (!texto) return null;
  return texto
    .replace(/(\d+)\s*días?/i,    "$1d")
    .replace(/(\d+)\s*horas?/i,   " $1h")
    .replace(/(\d+)\s*minutos?/i, " $1m")
    .replace(/(\d+)\s*segundos?/i,"")
    .replace(/,\s*/g, " ")
    .trim();
}

// ── Fila de dato personal ─────────────────────────────────────────────────────
function PersonalRow({ label, value, href, warning }) {
  if (!value || value === "—") {
    return (
      <tr>
        <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#F2F2F2] whitespace-nowrap w-28">{label}</td>
        <td className="text-[10px] px-2 py-0.5 border border-gray-200 text-gray-300 italic">—</td>
      </tr>
    );
  }
  return (
    <tr className={warning ? "bg-red-50" : ""}>
      <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#F2F2F2] whitespace-nowrap w-28">{label}</td>
      <td className="text-[10px] px-2 py-0.5 border border-gray-200">
        {href
          ? <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline break-all">{value}</a>
          : <span className={warning ? "text-red-600 font-semibold" : "text-gray-800"}>{value}</span>
        }
      </td>
    </tr>
  );
}

// ── Celda de actividad/tarea ───────────────────────────────────────────────────
function TaskCell({ entregada, retrasada, title }) {
  let cls = "inline-flex items-center justify-center w-[14px] h-[14px] rounded-sm text-white text-[8px] font-bold";
  if (entregada && !retrasada) return <span className={`${cls} bg-green-500`} title={title}>✓</span>;
  if (retrasada)               return <span className={`${cls} bg-red-500`}   title={title}>✗</span>;
  return                              <span className={`${cls} bg-gray-300`}  title={title}>·</span>;
}

// ── Chip de calificación histórica ────────────────────────────────────────────
function GradeChip({ asignatura, nota_final, docente }) {
  const s = getNoteStyle(nota_final);
  return (
    <div className={`border ${s.border || "border-gray-200"} ${s.bg} rounded p-1.5 text-center`}
         style={{ minWidth: "72px", maxWidth: "90px" }}
         title={docente || asignatura}>
      <div className="text-[9px] text-gray-500 leading-tight mb-1 overflow-hidden"
           style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
        {asignatura}
      </div>
      <div className={`text-xs font-bold ${s.text}`}>{nota_final ?? "—"}</div>
    </div>
  );
}

// ── Sección header ────────────────────────────────────────────────────────────
function SectionHeader({ children, className = "" }) {
  return (
    <div className={`bg-[#D6E4F0] border-y border-gray-300 px-3 py-0.5 text-[10px] font-bold text-[#1B3A6B] uppercase tracking-wide ${className}`}>
      {children}
    </div>
  );
}

// ── Componente principal ───────────────────────────────────────────────────────
export default function FichaEstudiante() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [ficha, setFicha] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const searchTimeout = useRef(null);

  useEffect(() => {
    if (studentId) loadFicha(studentId);
  }, [studentId]);

  const handleSearch = (value) => {
    setQuery(value);
    clearTimeout(searchTimeout.current);
    if (value.length < 2) { setSearchResults([]); return; }
    searchTimeout.current = setTimeout(async () => {
      try {
        const results = await api.searchStudents(value);
        setSearchResults(results);
      } catch (e) { console.error(e); }
    }, 300);
  };

  const loadFicha = async (id) => {
    setLoading(true);
    setSearchResults([]);
    try {
      const data = await api.getFicha(id);
      setFicha(data);
      setQuery(data.nombre || "");
      navigate(`/ficha/${id}`, { replace: true });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleExportPDF = async () => {
    if (!ficha) return;
    const blob = await api.exportFichaPDF(ficha.id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ficha_${(ficha.nombre || ficha.id).toString().replace(/\s+/g, "_")}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Construir mapa de cursos AVAC
  const cursos = {};
  if (ficha) {
    (ficha.accesos_avac || []).forEach(a => {
      if (!cursos[a.codigo_curso]) cursos[a.codigo_curso] = { acceso: null, tareas: [] };
      cursos[a.codigo_curso].acceso = a;
    });
    (ficha.tareas || []).forEach(t => {
      if (!cursos[t.codigo_curso]) cursos[t.codigo_curso] = { acceso: null, tareas: [] };
      cursos[t.codigo_curso].tareas.push(t);
    });
  }

  // Intentar hacer match entre cursos AVAC y calificaciones institucionales
  const matchNota = (courseName, calificaciones) => {
    if (!courseName || !calificaciones?.length) return null;
    const norm = s => (s || "").toLowerCase().replace(/[^a-záéíóúñ0-9]/gi, "").slice(0, 12);
    const cn = norm(courseName);
    return calificaciones.find(c => {
      const an = norm(c.asignatura);
      return an && cn && (an.startsWith(cn.slice(0, 8)) || cn.startsWith(an.slice(0, 8)));
    }) || null;
  };

  // Diagnóstico computado (Framework §3.5) — tiene prioridad sobre nivel_riesgo
  const diagStyle = ficha ? getDiagnosticoStyle(ficha.diagnostico_riesgo) : getDiagnosticoStyle(null);
  const riesgoStyle = ficha ? getRiesgoStyle(ficha.nivel_riesgo) : {};

  // Sede: usar la detectada por grupo si existe, si no la almacenada en BD
  const sedeDisplay = ficha?.sede_detectada || ficha?.sede || "—";

  const compromisoLabel = ficha ? getCompromisoLabel(ficha.indice_compromiso) : "—";
  const compromisoStr = ficha?.indice_compromiso != null
    ? `${(ficha.indice_compromiso * 100).toFixed(0)}%` : "";
  const compromisoColor = ficha?.indice_compromiso == null ? "text-gray-400"
    : ficha.indice_compromiso < 0.3 ? "text-red-600"
    : ficha.indice_compromiso < 0.6 ? "text-yellow-600"
    : "text-green-700";

  const today = new Date().toLocaleDateString("es-EC", {
    weekday: "long", day: "numeric", month: "long", year: "numeric"
  });

  const updatedText = new Date().toLocaleDateString("es-EC", { day: "2-digit", month: "short" });

  return (
    <div>
      {/* ── Título + buscador ─────────────────────────────────────────── */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Ficha del Estudiante</h1>
        <p className="text-gray-400 text-sm">Carrera EIB — Monitoreo académico individual</p>
      </div>

      <div className="relative mb-5">
        <input
          type="text"
          value={query}
          onChange={e => handleSearch(e.target.value)}
          placeholder="🔍 Buscar por nombre, correo o cédula..."
          className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 pr-10 bg-white shadow-sm"
        />
        {loading && <span className="absolute right-3 top-3.5 text-gray-400 text-sm">⏳</span>}
        {searchResults.length > 0 && (
          <div className="absolute z-10 w-full bg-white border border-gray-200 rounded-xl shadow-lg mt-1 max-h-64 overflow-y-auto">
            {searchResults.map(s => (
              <button key={s.id} onClick={() => loadFicha(s.id)}
                className="w-full text-left px-4 py-3 hover:bg-blue-50 flex items-center justify-between border-b border-gray-100 last:border-0">
                <div>
                  <div className="font-medium text-gray-900 text-sm">{s.nombre || "Sin nombre"}</div>
                  <div className="text-xs text-gray-400">{s.correo_institucional} · {s.carrera || "EIB"}</div>
                </div>
                <RiskBadge nivel={s.nivel_riesgo} />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── FICHA COMPLETA ─────────────────────────────────────────────── */}
      {ficha && (
        <div className="border border-gray-400 rounded-md overflow-hidden shadow text-xs" style={{ fontFamily: "Calibri, Arial, sans-serif" }}>

          {/* ═══ FILA 1: ENCABEZADO PRINCIPAL ═══ */}
          <div className="bg-[#1B3A6B] text-white flex items-center justify-between px-4 py-2">
            <div className="flex items-center gap-3">
              <span className="text-sm font-bold tracking-tight">Educación Intercultural Bilingüe</span>
              <span className="opacity-40">|</span>
              <span className="text-xs opacity-60 italic">CARRERA: Educación Intercultural Bilingüe</span>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button onClick={handleExportPDF}
                className="bg-white/10 hover:bg-white/20 text-white px-3 py-1 rounded text-xs font-medium transition">
                📄 PDF
              </button>
              <button onClick={() => setShowForm(true)}
                className="bg-white text-[#1B3A6B] hover:bg-blue-50 px-3 py-1 rounded text-xs font-bold transition">
                + Intervención
              </button>
            </div>
          </div>

          {/* ═══ FILA 2: BANDA DE IDENTIDAD (amarillo) ═══ */}
          <div className="bg-[#FFF2CC] border-b border-[#BF8F00]">
            <div className="flex divide-x divide-[#BF8F00]">
              <div className="px-3 py-1.5 text-center w-36 flex-shrink-0">
                <div className="text-[9px] text-gray-500 font-bold uppercase tracking-wider">Cédula</div>
                <div className="font-bold text-gray-800 text-sm mt-0.5">{ficha.cedula || "—"}</div>
              </div>
              <div className="px-3 py-1.5 text-center w-36 flex-shrink-0">
                <div className="text-[9px] text-gray-500 font-bold uppercase tracking-wider">Teléfono</div>
                <div className="font-bold text-gray-800 text-sm mt-0.5">{ficha.telefono || "—"}</div>
              </div>
              <div className="px-4 py-1.5 text-center flex-1">
                <div className="text-[9px] text-gray-500 font-bold uppercase tracking-wider">Nombres y apellidos</div>
                <div className="font-bold text-[#1B3A6B] text-base mt-0.5 uppercase">{ficha.nombre || "—"}</div>
              </div>
              <div className="px-3 py-1.5 text-center w-28 flex-shrink-0">
                <div className="text-[9px] text-gray-500 font-bold uppercase tracking-wider">Actualizado</div>
                <div className="font-semibold text-gray-700 text-sm mt-0.5">{updatedText}</div>
              </div>
              <div className="px-3 py-1.5 text-center w-36 flex-shrink-0">
                <div className="text-[9px] text-gray-500 font-bold uppercase tracking-wider">Compromiso</div>
                <div className={`font-bold text-sm mt-0.5 ${compromisoColor}`}>
                  {compromisoLabel} {compromisoStr}
                </div>
              </div>
              <div className={`px-3 py-1.5 text-center w-40 flex-shrink-0 ${diagStyle.bg} border-l border-[#BF8F00]`}>
                <div className="text-[9px] text-gray-500 font-bold uppercase tracking-wider">Diagnóstico</div>
                <div className={`font-bold text-xs mt-0.5 ${diagStyle.text}`}>{diagStyle.label}</div>
              </div>
            </div>
          </div>

          {/* ═══ CUERPO PRINCIPAL: 2 columnas ═══ */}
          <div className="flex divide-x divide-gray-300 bg-white">

            {/* ─── COLUMNA IZQUIERDA ─── */}
            <div className="flex-shrink-0 bg-white" style={{ width: "260px" }}>

              {/* Datos personales */}
              <SectionHeader>Datos personales</SectionHeader>
              <table className="w-full border-collapse">
                <tbody>
                  <PersonalRow
                    label="Whatsapp"
                    value={ficha.whatsapp || ficha.telefono}
                    href={
                      (ficha.whatsapp || ficha.telefono)
                        ? `https://wa.me/593${(ficha.whatsapp || ficha.telefono).replace(/\D/g, "").replace(/^0/, "")}`
                        : null
                    }
                  />
                  <PersonalRow label="Correo" value={ficha.correo} />
                  <PersonalRow label="Correo Ins." value={ficha.correo_institucional} />
                  <PersonalRow label="Discapacidad" value="—" />
                  <PersonalRow label="Fecha nac. y edad" value="—" />
                  <PersonalRow label="Autoidentificación" value="—" />
                  <PersonalRow label="Lengua materna" value="—" />
                </tbody>
              </table>

              {/* Lugar de residencia */}
              <SectionHeader>Lugar de residencia</SectionHeader>
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-[#F2F2F2]">
                    <th className="text-[10px] font-semibold text-gray-500 px-2 py-0.5 border border-gray-200 text-center">Provincia</th>
                    <th className="text-[10px] font-semibold text-gray-500 px-2 py-0.5 border border-gray-200 text-center">Cantón</th>
                    <th className="text-[10px] font-semibold text-gray-500 px-2 py-0.5 border border-gray-200 text-center">Parroquia</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="text-[10px] text-center px-1 py-0.5 border border-gray-200 text-gray-700 font-medium">
                      {ficha.provincia || <span className="text-gray-300 italic">—</span>}
                    </td>
                    <td className="text-[10px] text-center px-1 py-0.5 border border-gray-200 text-gray-700">
                      {ficha.ciudad || <span className="text-gray-300 italic">—</span>}
                    </td>
                    <td className="text-[10px] text-center px-1 py-0.5 border border-gray-200 text-gray-700">
                      {ficha.parroquia || <span className="text-gray-300 italic">—</span>}
                    </td>
                  </tr>
                </tbody>
              </table>

              {/* Mapa */}
              <div className="bg-gray-50 border border-gray-200 mx-2 my-2 rounded flex flex-col items-center justify-center text-center"
                   style={{ height: "130px" }}>
                <svg viewBox="0 0 80 90" className="w-16 h-16 opacity-30" fill="#1B3A6B">
                  {/* Ecuador simplified shape */}
                  <path d="M38 5 L50 8 L60 15 L65 25 L62 38 L70 45 L72 55 L65 65 L55 72 L42 78 L30 75 L20 68 L15 55 L18 42 L12 32 L18 20 L28 12 Z" />
                  <circle cx="38" cy="40" r="5" fill="#F0B000" opacity="1"/>
                </svg>
                <div className="text-[10px] text-gray-400 -mt-1">Datos geográficos</div>
                <div className="text-[9px] text-gray-300">no disponibles</div>
              </div>

              <table className="w-full border-collapse">
                <tbody>
                  <PersonalRow label="Barrio o comunidad" value={ficha.barrio} />
                </tbody>
              </table>

              {/* Datos socioeconómicos */}
              <SectionHeader>Datos socioeconómicos</SectionHeader>
              <table className="w-full border-collapse">
                <tbody>
                  <PersonalRow label="Nivel de beca" value="—" />
                  <tr className={ficha.estado_matricula === "Matriculado" ? "bg-green-50" : "bg-red-50"}>
                    <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#F2F2F2] whitespace-nowrap w-28">Pago matrícula</td>
                    <td className={`text-[10px] px-2 py-0.5 border border-gray-200 font-semibold ${ficha.estado_matricula === "Matriculado" ? "text-green-700" : "text-red-600"}`}>
                      {ficha.estado_matricula || "—"}
                    </td>
                  </tr>
                  <PersonalRow label="Empleabilidad" value="—" />
                  <PersonalRow label="Madre o padre" value="—" />
                </tbody>
              </table>
            </div>

            {/* ─── SECCIÓN DERECHA ─── */}
            <div className="flex-1 overflow-hidden flex flex-col">

              {/* Barra de info: sede / nivel / compromiso / diagnóstico */}
              <div className="grid grid-cols-4 divide-x divide-white/20 bg-[#1B3A6B] text-white">
                <div className="px-3 py-1.5 text-center">
                  <div className="text-[9px] opacity-50 uppercase tracking-wider">Centro de Apoyo</div>
                  <div className="text-xs font-semibold mt-0.5">{sedeDisplay}</div>
                </div>
                <div className="px-3 py-1.5 text-center">
                  <div className="text-[9px] opacity-50 uppercase tracking-wider">Semestre activo</div>
                  <div className="text-xs font-semibold mt-0.5">
                    {ficha.nivel_academico
                      ? `${ficha.nivel_academico}° Nivel`
                      : ficha.nivel_detectado
                        ? ficha.nivel_detectado
                        : Object.keys(cursos).length > 0
                          ? `${Object.keys(cursos).length} cursos`
                          : "Sin cursos"}
                  </div>
                </div>
                <div className="px-3 py-1.5 text-center">
                  <div className="text-[9px] opacity-50 uppercase tracking-wider">Compromiso</div>
                  <div className={`text-xs font-bold mt-0.5 ${
                    ficha.indice_compromiso == null ? "text-gray-300"
                    : ficha.indice_compromiso < 0.3 ? "text-red-300"
                    : ficha.indice_compromiso < 0.6 ? "text-yellow-300"
                    : "text-green-300"
                  }`}>
                    {compromisoLabel} {compromisoStr}
                  </div>
                </div>
                {/* Diagnóstico con color de fondo según estado (Framework §3.5) */}
                <div className={`px-3 py-1.5 text-center ${diagStyle.bg}`}>
                  <div className="text-[9px] opacity-70 uppercase tracking-wider text-gray-700">Diagnóstico</div>
                  <div className={`text-xs font-bold mt-0.5 ${diagStyle.text}`}>{diagStyle.label}</div>
                </div>
              </div>

              {/* Tabla de cursos AVAC activos */}
              {Object.keys(cursos).length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-xs">
                    <thead>
                      <tr className="bg-[#BDD7EE]">
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 whitespace-nowrap text-[10px]">Nivel y grupo</th>
                        <th className="text-left px-2 py-1 border border-gray-300 font-semibold text-gray-700 text-[10px]" style={{ minWidth: "180px" }}>Asignaturas matriculadas</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-14 text-[10px]">Nota</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-10 text-[10px]">Mat</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-16 text-[10px]">AVAC</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-28 text-[10px]">Actividades</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-14 text-[10px]">Link</th>
                        <th className="text-left px-2 py-1 border border-gray-300 font-semibold text-gray-700 text-[10px]">Docente</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(cursos).map(([codigo, { acceso, tareas: ts }], idx) => {
                        const courseName = acceso?.nombre_curso || ts[0]?.nombre_curso || codigo;
                        const matchedCal = matchNota(courseName, ficha.calificaciones);
                        const nota = matchedCal?.nota_final ?? null;
                        const noteStyle = getNoteStyle(nota);
                        const sortedTasks = [...ts].sort((a, b) =>
                          String(a.unidad).localeCompare(String(b.unidad), undefined, { numeric: true })
                        );
                        const diasInt = acceso?.dias_sin_acceso != null ? Math.round(acceso.dias_sin_acceso) : null;
                        const diasColor = diasInt == null ? "text-gray-300"
                          : diasInt > 14 ? "text-red-600 font-bold"
                          : diasInt > 7 ? "text-orange-500"
                          : "text-green-600";

                        return (
                          <tr key={codigo} className={idx % 2 === 0 ? "bg-white" : "bg-[#F9F9F9]"}>
                            {/* Nivel y grupo */}
                            <td className="px-2 py-1 border border-gray-200 text-center text-[10px] text-gray-500 whitespace-nowrap">
                              {(() => {
                                const niv = acceso?.nivel ?? null;
                                const grp = acceso?.grupo || ts[0]?.grupo || null;
                                if (!niv && !grp) return <span className="text-gray-300">—</span>;
                                return (
                                  <span className="font-mono">
                                    {niv ? `N${niv}` : ""}
                                    {niv && grp ? " · " : ""}
                                    {grp ? `G${grp}` : ""}
                                  </span>
                                );
                              })()}
                            </td>
                            {/* Asignatura */}
                            <td className="px-2 py-1 border border-gray-200 font-medium text-gray-800">
                              {courseName}
                            </td>
                            {/* Nota */}
                            <td className={`px-2 py-1 border border-gray-200 text-center font-bold ${noteStyle.bg} ${noteStyle.text}`}>
                              {nota != null ? nota : <span className="text-gray-300">—</span>}
                            </td>
                            {/* Mat (estado matrícula AVAC) */}
                            <td className="px-2 py-1 border border-gray-200 text-center text-[10px] text-gray-500">
                              {acceso?.estado_avac
                                ? <span className="bg-blue-100 text-blue-700 px-1 rounded text-[9px]">
                                    {acceso.estado_avac.slice(0, 3)}
                                  </span>
                                : "—"}
                            </td>
                            {/* AVAC: días + texto compactado */}
                            <td className="px-2 py-1 border border-gray-200 text-center">
                              <span className={`font-mono text-[11px] ${diasColor}`}>
                                {diasInt != null ? `${diasInt}d` : "—"}
                              </span>
                              {acceso?.ultimo_acceso_texto && (
                                <div className="text-[9px] text-gray-400 leading-tight whitespace-nowrap">
                                  {compactarAcceso(acceso.ultimo_acceso_texto)}
                                </div>
                              )}
                            </td>
                            {/* Actividades: celdas de tareas */}
                            <td className="px-2 py-1 border border-gray-200">
                              <div className="flex gap-0.5 justify-center flex-wrap">
                                {sortedTasks.slice(0, 8).map((t, i) => (
                                  <TaskCell
                                    key={i}
                                    entregada={t.entregada}
                                    retrasada={t.retrasada}
                                    title={`Unidad ${t.unidad}: ${t.entregada ? "Entregada" : t.retrasada ? "Retrasada" : "Pendiente"}`}
                                  />
                                ))}
                                {sortedTasks.length > 8 && (
                                  <span className="text-[9px] text-gray-400 self-center">+{sortedTasks.length - 8}</span>
                                )}
                                {sortedTasks.length === 0 && (
                                  <span className="text-[9px] text-gray-300 italic">Sin tareas</span>
                                )}
                              </div>
                            </td>
                            {/* Link AVAC */}
                            <td className="px-2 py-1 border border-gray-200 text-center">
                              <a href={`https://avac.ups.edu.ec/course/view.php?id=${codigo}`}
                                 target="_blank" rel="noreferrer"
                                 className="text-blue-500 hover:text-blue-700 font-mono text-[10px]">
                                {codigo}
                              </a>
                            </td>
                            {/* Docente */}
                            <td className="px-2 py-1 border border-gray-200 text-gray-600 text-[10px]">
                              {acceso?.docente || ts[0]?.docente || matchedCal?.docente
                                || <span className="text-gray-300 italic">—</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Fila resumen de KPIs */}
              <div className="grid grid-cols-4 divide-x divide-gray-200 border-t border-gray-200 bg-[#F9F9F9]">
                <div className="py-2 px-3 text-center">
                  <div className="text-[9px] text-gray-400 uppercase tracking-wider">Días sin AVAC</div>
                  <div className={`font-bold text-sm mt-0.5 ${
                    ficha.dias_sin_acceso == null ? "text-gray-400"
                    : ficha.dias_sin_acceso > 14 ? "text-red-600"
                    : ficha.dias_sin_acceso > 7 ? "text-orange-500"
                    : "text-green-600"}`}>
                    {ficha.dias_sin_acceso != null ? `${Math.round(ficha.dias_sin_acceso)}d` : "—"}
                  </div>
                </div>
                <div className="py-2 px-3 text-center">
                  <div className="text-[9px] text-gray-400 uppercase tracking-wider">Tareas entregadas</div>
                  <div className={`font-bold text-sm mt-0.5 ${
                    ficha.porcentaje_tareas == null ? "text-gray-400"
                    : ficha.porcentaje_tareas < 50 ? "text-red-600"
                    : ficha.porcentaje_tareas < 75 ? "text-orange-500"
                    : "text-green-600"}`}>
                    {ficha.porcentaje_tareas != null ? `${Math.round(ficha.porcentaje_tareas)}%` : "—"}
                  </div>
                </div>
                <div className="py-2 px-3 text-center">
                  <div className="text-[9px] text-gray-400 uppercase tracking-wider">Compromiso AVAC</div>
                  <div className={`font-bold text-sm mt-0.5 ${compromisoColor}`}>
                    {compromisoLabel} {compromisoStr}
                  </div>
                </div>
                {/* Diagnóstico: 4 estados con color semafórico */}
                <div className={`py-2 px-3 text-center ${diagStyle.bg}`}>
                  <div className="text-[9px] text-gray-500 uppercase tracking-wider">Diagnóstico</div>
                  <div className={`font-bold text-xs mt-0.5 ${diagStyle.text}`}>
                    {ficha.diagnostico_riesgo || "—"}
                  </div>
                </div>
              </div>

              {/* Historial de calificaciones institucionales */}
              {ficha.calificaciones?.length > 0 && (
                <div className="border-t border-gray-200">
                  <SectionHeader>
                    Historial de calificaciones ({ficha.calificaciones.length} asignaturas)
                  </SectionHeader>
                  <div className="p-2 flex flex-wrap gap-1.5 bg-white">
                    {ficha.calificaciones.map((c, i) => (
                      <GradeChip key={i} asignatura={c.asignatura} nota_final={c.nota_final} docente={c.docente} />
                    ))}
                  </div>
                </div>
              )}

              {/* Si no hay cursos AVAC */}
              {Object.keys(cursos).length === 0 && (
                <div className="flex-1 flex items-center justify-center py-12 text-center text-gray-300">
                  <div>
                    <div className="text-3xl mb-2">📚</div>
                    <div className="text-sm">Sin actividad AVAC registrada</div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ═══ PRÁCTICAS PREPROFESIONALES ═══ */}
          <div className="border-t border-gray-300">
            <div className="bg-[#1B3A6B] text-white px-4 py-1 text-[10px] font-bold uppercase tracking-wider">
              Prácticas Preprofesionales
            </div>
            <div className="grid grid-cols-2 divide-x divide-gray-300 bg-white">
              <table className="border-collapse w-full">
                <tbody>
                  {[
                    ["Nombre práctica", "—"],
                    ["IE Práctica", "—"],
                    ["Ubicación IE", "—"],
                    ["Distrito AMIE", "—"],
                    ["Jurisdicción", "—"],
                    ["Nombre autoridad", "—"],
                    ["Cargo", "—"],
                    ["Celular", "—"],
                  ].map(([label, val]) => (
                    <tr key={label}>
                      <td className="bg-[#F2F2F2] border border-gray-200 text-right text-[10px] font-semibold text-gray-500 px-2 py-0.5 w-32 whitespace-nowrap">{label}</td>
                      <td className="border border-gray-200 text-[10px] px-2 py-0.5 text-gray-300 italic">{val}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="p-3">
                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  <div>
                    <div className="bg-[#F2F2F2] text-center py-0.5 font-bold text-gray-600 border border-gray-200 mb-1">Sin membrete</div>
                    <div className="text-center text-[#BF8F00] border border-gray-200 py-0.5 cursor-pointer hover:bg-yellow-50">Carta de solicitud</div>
                    <div className="text-center text-[#BF8F00] border border-gray-200 py-0.5 cursor-pointer hover:bg-yellow-50 mt-0.5">Carta de solicitud</div>
                  </div>
                  <div>
                    <div className="bg-[#F2F2F2] text-center py-0.5 font-bold text-gray-600 border border-gray-200 mb-1">Membretado</div>
                    <div className="text-center text-[#BF8F00] border border-gray-200 py-0.5 cursor-pointer hover:bg-yellow-50">Carta de solicitud</div>
                    <div className="text-center text-[#BF8F00] border border-gray-200 py-0.5 cursor-pointer hover:bg-yellow-50 mt-0.5">Carta de solicitud</div>
                  </div>
                  <div className="col-span-2 text-center text-[#BF8F00] border border-gray-200 py-0.5 cursor-pointer hover:bg-yellow-50">Carta compromiso</div>
                </div>
              </div>
            </div>
          </div>

          {/* ═══ SEGUIMIENTO E INTERVENCIONES ═══ */}
          <div className="border-t border-gray-300">
            <div className="bg-[#1B3A6B] text-white flex items-center justify-between px-4 py-1">
              <span className="text-[10px] font-bold uppercase tracking-wider">
                Seguimiento e Intervenciones ({ficha.total_intervenciones || 0})
              </span>
              <button onClick={() => setShowForm(true)}
                className="bg-white/10 hover:bg-white/20 text-white text-[10px] px-3 py-0.5 rounded font-medium">
                + Nueva intervención
              </button>
            </div>
            <div className="bg-white">
              {ficha.intervenciones?.length === 0 ? (
                <div className="py-5 text-center text-[10px] text-gray-300 italic">
                  Sin intervenciones registradas
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {ficha.intervenciones.map(inv => (
                    <div key={inv.id} className="px-4 py-2 flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-1 mb-0.5">
                          {inv.medio && (
                            <span className="bg-blue-100 text-blue-700 text-[9px] font-medium px-1.5 py-0.5 rounded-full">
                              {inv.medio}
                            </span>
                          )}
                          {inv.motivo && <span className="text-[10px] text-gray-500">{inv.motivo}</span>}
                        </div>
                        {inv.observacion && <p className="text-xs text-gray-700 leading-relaxed">{inv.observacion}</p>}
                        <div className="flex flex-wrap gap-2 mt-0.5 text-[9px] text-gray-400">
                          {inv.estado && <span>Estado: <strong className="text-gray-600">{inv.estado}</strong></span>}
                          {inv.asignatura && <span>· {inv.asignatura}</span>}
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="text-[9px] text-gray-400">
                          {inv.created_at ? new Date(inv.created_at).toLocaleDateString("es-EC") : ""}
                        </div>
                        {inv.monitor_nombre && (
                          <div className="text-[9px] text-gray-400 truncate max-w-[90px]">{inv.monitor_nombre}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ═══ PIE DE PÁGINA ═══ */}
          <div className="bg-[#1B3A6B] text-white text-center py-1.5 text-[9px] opacity-60 tracking-wide">
            Yachay Deep — Carlos Vásconez P. © &nbsp;|&nbsp; {today}
          </div>

        </div>
      )}

      {/* Modal intervención */}
      {showForm && ficha && (
        <InterventionForm
          student={ficha}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadFicha(ficha.id); }}
        />
      )}
    </div>
  );
}
