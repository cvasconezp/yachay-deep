import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";
import EcuadorMap from "../components/EcuadorMap";
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

/**
 * Parsea una fecha ISO date-only ("2001-12-31") como fecha LOCAL, no UTC.
 * new Date("2001-12-31") → UTC midnight → en Ecuador (UTC-5) muestra día anterior.
 * Agregando T00:00:00 se interpreta como hora local.
 */
function parseLocalDate(isoDate) {
  if (!isoDate) return null;
  return new Date(isoDate + (isoDate.includes("T") ? "" : "T00:00:00"));
}

/** Calcula la edad a partir de una fecha de nacimiento ISO */
function calcAge(isoDate) {
  if (!isoDate) return null;
  const birth = parseLocalDate(isoDate);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  return age;
}

/** Convierte número de nivel a ordinal en español: 1→"1er", 2→"2do", etc. */
function ordinalNivel(n) {
  const map = { 1: "1er", 2: "2do", 3: "3er", 4: "4to", 5: "5to", 6: "6to", 7: "7mo", 8: "8vo" };
  return map[n] || `${n}°`;
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

/** Title Case: primera letra de cada palabra en mayúscula, excepto números romanos */
function toTitleCase(str) {
  if (!str) return str;
  const roman = /^(I{1,3}|IV|VI{0,3}|IX|X{0,3}|XI{0,3}|XII)$/;
  return str.toLowerCase().split(/\s+/).map(word => {
    if (roman.test(word.toUpperCase())) return word.toUpperCase();
    return word.charAt(0).toUpperCase() + word.slice(1);
  }).join(" ");
}

/** Abrevia el grupo: "3" → "G3", "Grupo - 3" → "G3", ya formateado "G6" → "G6" */
function abbreviateGrupo(grupo) {
  if (!grupo) return null;
  const s = String(grupo).trim();
  if (/^G\d+$/i.test(s)) return s.toUpperCase(); // ya abreviado
  const m = s.match(/(\d+)/);
  return m ? `G${m[1]}` : s;
}

/**
 * Formatea nivel para encabezados: "9° Nivel".
 * Prioriza nivel_academico (entero), luego el nivel más frecuente de calificaciones.
 * NO parsea nivel_detectado ("Semestre 67") porque es código de período, no nivel real.
 */
function formatNivel(nivelAcademico, calificaciones) {
  if (nivelAcademico != null && nivelAcademico > 0 && nivelAcademico <= 12)
    return `${nivelAcademico}° Nivel`;
  // Fallback: nivel más frecuente de calificaciones del semestre actual
  if (calificaciones?.length > 0) {
    const niveles = calificaciones.map(c => c.nivel).filter(n => n != null && n > 0 && n <= 12);
    if (niveles.length > 0) {
      const counts = {};
      niveles.forEach(n => { counts[n] = (counts[n] || 0) + 1; });
      const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
      return `${top}° Nivel`;
    }
  }
  return null;
}

/** Normaliza un valor de nivel individual (de calificaciones) a entero 1-12. */
function parseNivelNum(val) {
  if (val == null || val === "") return null;
  const n = parseInt(String(val), 10);
  return (!isNaN(n) && n >= 1 && n <= 12) ? n : null;
}

// ── Fila de dato personal ─────────────────────────────────────────────────────
function PersonalRow({ label, value, href, warning }) {
  if (!value || value === "—") {
    return (
      <tr>
        <td className="text-right text-[11px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#F2F2F2] whitespace-nowrap w-28">{label}</td>
        <td className="text-[11px] px-2 py-0.5 border border-gray-200 text-gray-300 italic">—</td>
      </tr>
    );
  }
  return (
    <tr className={warning ? "bg-red-50" : ""}>
      <td className="text-right text-[11px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#F2F2F2] whitespace-nowrap w-28">{label}</td>
      <td className="text-[11px] px-2 py-0.5 border border-gray-200">
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

// ── Estilo de nota para escala 0–100 (TableauHistorico)
// Umbral EIB: ≥70 aprobado, 60–69 en proceso, <60 reprobado
function getNoteStyleHistorico(nota) {
  if (nota == null) return { bg: "", text: "text-gray-400", border: "border-gray-200" };
  if (nota >= 70) return { bg: "bg-green-100",  text: "text-green-800",  border: "border-green-300" };
  if (nota >= 60) return { bg: "bg-yellow-100", text: "text-yellow-800", border: "border-yellow-300" };
  return               { bg: "bg-red-100",    text: "text-red-700",   border: "border-red-300" };
}

// ── Chip de calificación histórica ────────────────────────────────────────────
function GradeChip({ asignatura, nota_final, docente }) {
  const s = getNoteStyle(nota_final);
  return (
    <div className={`border ${s.border || "border-gray-200"} ${s.bg} rounded p-1.5 text-center`}
         style={{ minWidth: "72px", maxWidth: "90px" }}
         title={toTitleCase(docente) || toTitleCase(asignatura)}>
      <div className="text-[9px] text-gray-500 leading-tight mb-1 overflow-hidden"
           style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
        {toTitleCase(asignatura)}
      </div>
      <div className={`text-xs font-bold ${s.text}`}>{nota_final ?? "—"}</div>
    </div>
  );
}

// ── Chip de calificación en malla histórica ────────────────────────────────────
function MallaChip({ asignatura, nota_final, docente }) {
  const s = getNoteStyleHistorico(nota_final);
  const titleName = toTitleCase(asignatura) || "";
  // Abreviar nombre: máx 18 chars, eliminar palabras comunes
  const abrev = titleName
    .replace(/\b(de|la|las|los|el|y|en|del|para|con|por)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 18);
  return (
    <div className={`border ${s.border} ${s.bg} rounded px-1.5 py-1 text-center cursor-default`}
         style={{ minWidth: "70px", maxWidth: "88px" }}
         title={`${titleName}${docente ? " · " + toTitleCase(docente) : ""}${nota_final != null ? " · " + nota_final + "/100" : ""}`}>
      <div className="text-[8px] text-gray-500 leading-tight mb-0.5 overflow-hidden whitespace-nowrap"
           style={{ overflow: "hidden", textOverflow: "ellipsis", maxWidth: "84px" }}>
        {abrev}
      </div>
      <div className={`text-[11px] font-bold ${s.text}`}>{nota_final ?? "—"}</div>
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
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [carreras, setCarreras] = useState([]);
  const [selectedCarrera, setSelectedCarrera] = useState("");
  const [prediccion, setPrediccion] = useState(null);
  const [recomendaciones, setRecomendaciones] = useState([]);
  const [contrafactual, setContrafactual] = useState(null);
  const searchTimeout = useRef(null);
  const searchAbort = useRef(null);
  const searchContainerRef = useRef(null);

  // Cargar lista de carreras al montar
  useEffect(() => {
    api.getCarreras().then(setCarreras).catch(() => {});
  }, []);

  // Cerrar dropdown al hacer click fuera
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target)) {
        setSearchResults([]);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (studentId) loadFicha(studentId);
  }, [studentId]);

  useEffect(() => {
    if (!studentId) return;
    const loadPrediction = async () => {
      try {
        const data = await api.getPrediction(studentId);
        setPrediccion(data);
      } catch (err) {
        console.error('Error cargando predicción:', err);
      }
    };
    const loadRecomendaciones = async () => {
      try {
        const data = await api.getRecommendations(studentId);
        setRecomendaciones(Array.isArray(data) ? data : (data?.recomendaciones || []));
      } catch (err) {
        console.error('Error cargando recomendaciones:', err);
      }
    };
    loadPrediction();
    loadRecomendaciones();
    // Cargar contrafactuales
    api.getCounterfactual(studentId).then(setContrafactual).catch(() => {});
  }, [studentId]);

  // Re-buscar cuando cambia la carrera seleccionada
  const triggerSearch = (q, carrera) => {
    clearTimeout(searchTimeout.current);
    if (searchAbort.current) searchAbort.current.abort();
    // Si hay carrera seleccionada, buscar incluso sin query (lista de carrera)
    if (!carrera && q.length < 2) { setSearchResults([]); return; }
    searchTimeout.current = setTimeout(async () => {
      const controller = new AbortController();
      searchAbort.current = controller;
      try {
        const results = await api.searchStudents(q, carrera, { signal: controller.signal });
        // PERF-01 fix: endpoint ahora devuelve {items, total, ...} en vez de array plano
        setSearchResults(Array.isArray(results) ? results : (results?.items || []));
      } catch (e) {
        if (e.name !== "AbortError") console.error(e);
      }
    }, 300);
  };

  const handleSearch = (value) => {
    setQuery(value);
    triggerSearch(value, selectedCarrera);
  };

  const handleCarreraChange = (carrera) => {
    setSelectedCarrera(carrera);
    triggerSearch(query, carrera);
  };

  const loadFicha = async (id) => {
    setLoading(true);
    setError(null);
    setSearchResults([]);
    try {
      const data = await api.getFicha(id);
      setFicha(data);
      setQuery(data.nombre || "");
      navigate(`/ficha/${id}`, { replace: true });
    } catch (e) {
      console.error(e);
      setError(e.message || "Error al cargar la ficha del estudiante");
    } finally {
      setLoading(false);
    }
  };

  const handleExportPDF = async () => {
    if (!ficha) return;
    try {
      const blob = await api.exportFichaPDF(ficha.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ficha_${(ficha.nombre || ficha.id).toString().replace(/\s+/g, "_")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError("Error al exportar PDF: " + (e.message || "intenta de nuevo"));
    }
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

  // Carrera EIB: sedes, centro de apoyo y SEDE_MAPPING solo aplican para EIB
  const isEIB = Boolean(ficha?.carrera?.toUpperCase().includes("INTERCULTURAL"));

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
        <p className="text-gray-400 text-sm">Monitoreo académico individual</p>
      </div>

      {/* ── Filtro de carrera + buscador ────────────────────────────── */}
      <div className="flex gap-2 mb-5">
        {/* Dropdown de carreras */}
        <select
          value={selectedCarrera}
          onChange={e => handleCarreraChange(e.target.value)}
          className="border border-gray-300 rounded-xl px-3 py-3 text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[180px] text-gray-600"
        >
          <option value="">Todas las carreras</option>
          {carreras.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        {/* Buscador */}
        <div className="relative flex-1" ref={searchContainerRef}>
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
      </div>

      {/* ── ERROR ─────────────────────────────────────────────────────── */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-4 flex items-center justify-between">
          <span className="text-red-700 text-sm">{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 text-xs ml-4">Cerrar</button>
        </div>
      )}

      {/* ── FICHA COMPLETA ─────────────────────────────────────────────── */}
      {ficha && (
        <div className="border border-gray-400 rounded-md overflow-hidden shadow text-xs" style={{ fontFamily: "Calibri, Arial, sans-serif" }}>

          {/* ═══ ENCABEZADO INSTITUCIONAL ═══ */}
          <div className="bg-gradient-to-r from-[#0F2444] to-[#1B3A6B] text-white">
            {/* Barra superior: carrera + acciones */}
            <div className="flex items-center justify-between px-6 py-2 border-b border-white/10">
              <div className="flex items-center gap-3">
                <span className="text-xs font-bold tracking-widest uppercase text-white/60">{ficha.carrera || "Monitoreo Estudiantil"}</span>
                {isEIB && sedeDisplay !== "—" && (
                  <span className="bg-white/10 text-white/80 text-[10px] px-2 py-0.5 rounded-full font-medium">{sedeDisplay}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={handleExportPDF}
                  className="bg-white/10 hover:bg-white/20 text-white px-4 py-1.5 rounded-lg text-xs font-medium transition border border-white/10">
                  PDF
                </button>
                <button onClick={() => setShowForm(true)}
                  className="bg-[#E8A838] hover:bg-[#F0B000] text-[#0F2444] px-4 py-1.5 rounded-lg text-xs font-bold transition shadow-sm">
                  + Intervención
                </button>
              </div>
            </div>
            {/* Nombre del estudiante + datos de identidad */}
            <div className="px-6 py-4">
              <h2 className="text-xl font-bold tracking-wide uppercase leading-tight">{ficha.nombre || "—"}</h2>
              <div className="flex flex-wrap items-center gap-x-5 gap-y-1 mt-2 text-sm text-white/60">
                <span>CI: <strong className="text-white/90 font-semibold">{ficha.cedula || "—"}</strong></span>
                <span className="hidden sm:inline w-px h-3 bg-white/20" />
                <span>Tel: <strong className="text-white/90 font-semibold">{ficha.telefono || "—"}</strong></span>
                <span className="hidden sm:inline w-px h-3 bg-white/20" />
                <span>Actualizado: <strong className="text-white/90 font-semibold">{updatedText}</strong></span>
                {formatNivel(ficha.nivel_academico, ficha.calificaciones) && (
                  <>
                    <span className="hidden sm:inline w-px h-3 bg-white/20" />
                    <span className="bg-white/15 text-white px-2.5 py-0.5 rounded-full text-xs font-semibold">
                      {formatNivel(ficha.nivel_academico, ficha.calificaciones)}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* ═══ INDICADORES — GRID EJECUTIVO ═══ */}
          <div className="bg-white border-b border-gray-200">
            <div className="flex items-center justify-between px-6 py-1.5 bg-gray-50/80 border-b border-gray-100">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Indicadores · Predicción IA</span>
              <span className="text-[9px] text-gray-400">
                Modelo ML · P60-P67
                {ficha.prediccion_updated_at && (
                  <> · {new Date(ficha.prediccion_updated_at).toLocaleDateString("es-EC")}</>
                )}
              </span>
            </div>
            <div className="grid grid-cols-3 divide-x divide-gray-100">
              {/* Compromiso */}
              <div className="px-5 py-2 cursor-help" title="Indice de compromiso: acceso AVAC (30%), tareas (30%), rendimiento (25%), matrícula (15%)">
                <div className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider mb-1">Compromiso</div>
                <div className="flex items-end gap-2">
                  <span className={`text-2xl font-bold leading-none ${compromisoColor}`}>{compromisoStr || "—"}</span>
                  <span className={`text-xs font-semibold ${compromisoColor} mb-0.5`}>{compromisoLabel}</span>
                </div>
                {ficha.indice_compromiso != null && (
                  <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-500 ${
                      ficha.indice_compromiso >= 0.7 ? "bg-green-500" : ficha.indice_compromiso >= 0.4 ? "bg-yellow-400" : "bg-red-500"
                    }`} style={{ width: `${Math.round(ficha.indice_compromiso * 100)}%` }} />
                  </div>
                )}
              </div>
              {/* Predicción Deserción */}
              {(() => {
                const pctDes = ficha.prob_desercion != null ? Math.round(ficha.prob_desercion * 100) : null;
                const colorDes = pctDes == null ? "text-gray-300" : pctDes >= 70 ? "text-red-600" : pctDes >= 40 ? "text-orange-600" : "text-green-600";
                const barDes = pctDes >= 70 ? "bg-red-500" : pctDes >= 40 ? "bg-orange-400" : "bg-green-500";
                const labelDes = pctDes == null ? "—" : pctDes >= 70 ? "Alto" : pctDes >= 40 ? "Moderado" : "Bajo";
                return (
                  <div className="px-5 py-2 cursor-help" title="Probabilidad de deserción predicha por modelo ML">
                    <div className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider mb-1">Predicción Deserción</div>
                    <div className="flex items-end gap-2">
                      <span className={`text-2xl font-bold leading-none ${colorDes}`}>{pctDes != null ? `${pctDes}%` : "—"}</span>
                      <span className={`text-xs font-semibold ${colorDes} mb-0.5`}>{labelDes}</span>
                    </div>
                    {pctDes != null && (
                      <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all duration-500 ${barDes}`} style={{ width: `${pctDes}%` }} />
                      </div>
                    )}
                  </div>
                );
              })()}
              {/* Predicción Reprobación */}
              {(() => {
                const pctRep = ficha.prob_reprobacion != null ? Math.round(ficha.prob_reprobacion * 100) : null;
                const colorRep = pctRep == null ? "text-gray-300" : pctRep >= 70 ? "text-red-600" : pctRep >= 40 ? "text-orange-600" : "text-green-600";
                const barRep = pctRep >= 70 ? "bg-red-500" : pctRep >= 40 ? "bg-orange-400" : "bg-green-500";
                const labelRep = pctRep == null ? "—" : pctRep >= 70 ? "Alto" : pctRep >= 40 ? "Moderado" : "Bajo";
                return (
                  <div className="px-5 py-2 cursor-help" title="Probabilidad de reprobar al menos una materia">
                    <div className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider mb-1">Predicción Reprobación</div>
                    <div className="flex items-end gap-2">
                      <span className={`text-2xl font-bold leading-none ${colorRep}`}>{pctRep != null ? `${pctRep}%` : "—"}</span>
                      <span className={`text-xs font-semibold ${colorRep} mb-0.5`}>{labelRep}</span>
                    </div>
                    {pctRep != null && (
                      <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all duration-500 ${barRep}`} style={{ width: `${pctRep}%` }} />
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          </div>

          {/* ===== Explicación del Riesgo (XAI) ===== */}
          {prediccion?.xai && (
          <div className="mt-4 space-y-3">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide flex items-center gap-2">
              <span>🔍</span> Explicación del Riesgo
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {prediccion.xai.desercion?.length > 0 && (
              <div className="bg-white rounded-xl border border-red-100 shadow-sm p-4">
                <p className="text-xs font-bold text-red-700 mb-3 uppercase">Factores · Deserción</p>
                <div className="space-y-3">
                  {prediccion.xai.desercion.slice(0,3).map((f,i) => {
                    const nm = {promedio_notas:'Promedio Calificaciones',num_reprobadas:'Materias Reprobadas',pct_reprobadas:'% Reprobadas',nota_min:'Nota Mínima',std_notas:'Dispersión Notas',num_zeros:'Materias con Cero'};
                    const sube = f.direccion==='aumenta';
                    const pct = Math.min(100, Math.round(Math.abs(f.impacto||0)*100));
                    return (
                    <div key={i}>
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="font-medium text-gray-700">{nm[f.feature]||f.feature}</span>
                        <span className={sube?'text-red-500':'text-emerald-500'}>{sube?'↑ riesgo':'↓ riesgo'}</span>
                      </div>
                      <p className="text-xs text-gray-400 mb-1">Valor: {typeof f.valor==='number'?f.valor.toFixed(2):f.valor} · Media: {typeof f.media_carrera==='number'?f.media_carrera.toFixed(2):f.media_carrera}</p>
                      <div className="h-1.5 bg-gray-100 rounded-full">
                        <div className={'h-1.5 rounded-full ' + (sube?'bg-red-400':'bg-emerald-400')} style={{width: pct + '%'}}/>
                      </div>
                    </div>
                    );
                  })}
                </div>
              </div>
              )}
              {prediccion.xai.reprobacion?.length > 0 && (
              <div className="bg-white rounded-xl border border-orange-100 shadow-sm p-4">
                <p className="text-xs font-bold text-orange-700 mb-3 uppercase">Factores · Reprobación</p>
                <div className="space-y-3">
                  {prediccion.xai.reprobacion.slice(0,3).map((f,i) => {
                    const nm = {promedio_notas:'Promedio Calificaciones',num_reprobadas:'Materias Reprobadas',pct_reprobadas:'% Reprobadas',nota_min:'Nota Mínima',std_notas:'Dispersión Notas',num_zeros:'Materias con Cero'};
                    const sube = f.direccion==='aumenta';
                    const pct = Math.min(100, Math.round(Math.abs(f.impacto||0)*100));
                    return (
                    <div key={i}>
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="font-medium text-gray-700">{nm[f.feature]||f.feature}</span>
                        <span className={sube?'text-orange-500':'text-emerald-500'}>{sube?'↑ riesgo':'↓ riesgo'}</span>
                      </div>
                      <p className="text-xs text-gray-400 mb-1">Valor: {typeof f.valor==='number'?f.valor.toFixed(2):f.valor} · Media: {typeof f.media_carrera==='number'?f.media_carrera.toFixed(2):f.media_carrera}</p>
                      <div className="h-1.5 bg-gray-100 rounded-full">
                        <div className={'h-1.5 rounded-full ' + (sube?'bg-orange-400':'bg-emerald-400')} style={{width: pct + '%'}}/>
                      </div>
                    </div>
                    );
                  })}
                </div>
              </div>
              )}
            </div>
          </div>
          )}

          {/* ===== PANEL IA: Acordeones desplegables ===== */}
          {(prediccion?.contexto_conductual?.length > 0 || contrafactual?.contrafactual_desercion?.cambios?.length > 0 || recomendaciones.length > 0) && (
          <div className="border-t border-gray-200 bg-[#FAFBFF]">
            <div className="divide-y divide-gray-200">

              {/* ── Alertas Conductuales (acordeón) ── */}
              {prediccion?.contexto_conductual?.length > 0 && (
              <details open className="group">
                <summary className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-blue-50/50 transition select-none">
                  <span className="text-[11px] font-bold text-gray-600 uppercase tracking-wide flex items-center gap-1.5">
                    <span>⚡</span> Alertas Conductuales
                    <span className="bg-red-100 text-red-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full ml-1">
                      {prediccion.contexto_conductual.length}
                    </span>
                  </span>
                  <span className="text-gray-400 text-xs group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div className="px-4 pb-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {prediccion.contexto_conductual.map((ctx, i) => {
                    const sev = ctx.severidad === "critica"
                      ? "border-red-300 bg-red-50 text-red-800"
                      : "border-amber-300 bg-amber-50 text-amber-800";
                    const icon = ctx.severidad === "critica" ? "🔴" : "🟡";
                    return (
                    <div key={i} className={`rounded-lg border p-2.5 ${sev}`}>
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-sm">{icon}</span>
                        <span className="text-[10px] font-bold uppercase">{ctx.factor}</span>
                      </div>
                      <p className="text-xs">{ctx.descripcion}</p>
                    </div>
                    );
                  })}
                </div>
              </details>
              )}

              {/* ── Escenarios Contrafactuales v2 (reactivado con factibilidad) ── */}
              {contrafactual?.contrafactual_desercion?.cambios?.length > 0 && (
              <details className="group">
                <summary className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-blue-50/50 transition select-none">
                  <span className="text-[11px] font-bold text-gray-600 uppercase tracking-wide flex items-center gap-1.5">
                    <span>🔄</span> Escenarios Contrafactuales
                    <span className="text-[10px] font-normal text-gray-400 normal-case ml-1">¿Qué cambiar para reducir el riesgo?</span>
                  </span>
                  <span className="text-gray-400 text-xs group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div className="px-4 pb-3 space-y-2">
                  {[
                    { data: contrafactual.contrafactual_desercion, label: "Deserción", border: "border-red-200", title: "text-red-700" },
                    { data: contrafactual.contrafactual_reprobacion, label: "Reprobación", border: "border-orange-200", title: "text-orange-700" },
                  ].filter(s => s.data?.cambios?.length > 0).map((sc, si) => (
                  <div key={si} className={`bg-white rounded-lg border ${sc.border} p-3`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-[10px] font-bold ${sc.title} uppercase`}>Escenario · {sc.label}</span>
                      <div className="flex items-center gap-1.5 text-xs">
                        <span className="text-gray-500">{Math.round((sc.data.prob_original||0)*100)}%</span>
                        <span className="text-gray-300">→</span>
                        <span className={`font-bold ${sc.data.factible ? 'text-green-600' : 'text-amber-600'}`}>
                          {Math.round((sc.data.prob_contrafactual||0)*100)}%
                        </span>
                        {sc.data.factible && <span className="text-green-500 text-[10px]">✓</span>}
                      </div>
                    </div>
                    {sc.data.cambios.map((c, ci) => {
                      const factColors = {alta:'bg-green-100 text-green-700',media:'bg-amber-100 text-amber-700',baja:'bg-gray-100 text-gray-500'};
                      return (
                      <div key={ci} className="flex items-start gap-1.5 text-xs mb-1.5">
                        <span className="text-blue-500 mt-0.5">▸</span>
                        <div className="flex-1">
                          <span className="font-medium text-gray-800">{c.accion}</span>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <span className="text-gray-400">-{Math.round((c.impacto_individual||0)*100)}% riesgo</span>
                            {c.factibilidad && (
                              <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${factColors[c.factibilidad]||'bg-gray-100 text-gray-500'}`}>
                                {c.factibilidad}
                              </span>
                            )}
                            {c.plazo && <span className="text-[9px] text-gray-400">{c.plazo}</span>}
                          </div>
                        </div>
                      </div>
                      );
                    })}
                    {sc.data.factible && (
                    <p className="text-[10px] text-green-600 mt-1.5 font-medium">
                      ✓ Riesgo: {Math.round((sc.data.prob_original||0)*100)}% → {Math.round((sc.data.prob_contrafactual||0)*100)}%
                      (−{Math.round((sc.data.reduccion_total||0)*100)} puntos)
                    </p>
                    )}
                  </div>
                  ))}
                </div>
              </details>
              )}

              {/* ── Contrafactuales Conductuales (siempre visible si hay datos) ── */}
              {contrafactual?.contrafactual_conductual?.escenarios?.length > 0 && (
              <details open className="group">
                <summary className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-blue-50/50 transition select-none">
                  <span className="text-[11px] font-bold text-gray-600 uppercase tracking-wide flex items-center gap-1.5">
                    <span>🎯</span> ¿Qué puede hacer el estudiante?
                    <span className="bg-blue-100 text-blue-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full ml-1">
                      {contrafactual.contrafactual_conductual.escenarios.length}
                    </span>
                  </span>
                  <span className="text-gray-400 text-xs group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div className="px-4 pb-3 space-y-2">
                  {contrafactual.contrafactual_conductual.escenarios.map((esc, i) => {
                    const factColors = {alta:'border-green-200 bg-green-50',media:'border-amber-200 bg-amber-50',baja:'border-gray-200 bg-gray-50'};
                    const badgeColors = {alta:'bg-green-100 text-green-700',media:'bg-amber-100 text-amber-700',baja:'bg-gray-100 text-gray-500'};
                    return (
                    <div key={i} className={`rounded-lg border p-3 ${factColors[esc.factibilidad] || 'border-gray-200 bg-gray-50'}`}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1">
                          <p className="text-xs font-medium text-gray-800">{esc.accion}</p>
                          <div className="flex items-center gap-2 mt-1.5">
                            <span className="text-[10px] text-gray-500">Compromiso:</span>
                            <span className="text-[11px] font-bold text-gray-600">{esc.compromiso_actual}%</span>
                            <span className="text-gray-300">→</span>
                            <span className="text-[11px] font-bold text-green-600">{esc.compromiso_nuevo}%</span>
                            <span className="text-[10px] text-green-600 font-medium">(+{esc.ganancia}pp)</span>
                          </div>
                          <div className="flex items-center gap-1.5 mt-1">
                            <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${badgeColors[esc.factibilidad] || ''}`}>
                              {esc.factibilidad}
                            </span>
                            <span className="text-[9px] text-gray-400">{esc.plazo}</span>
                            <span className="text-[9px] text-gray-400">→ Riesgo: {esc.nivel_riesgo_nuevo}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                    );
                  })}
                </div>
              </details>
              )}

              {/* ── Recomendaciones Automáticas (acordeón) ── */}
              {recomendaciones.length > 0 && (
              <details className="group">
                <summary className="flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-blue-50/50 transition select-none">
                  <span className="text-[11px] font-bold text-gray-600 uppercase tracking-wide flex items-center gap-1.5">
                    <span>💡</span> Recomendaciones
                    <span className="bg-amber-100 text-amber-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full ml-1">
                      {recomendaciones.length}
                    </span>
                    {recomendaciones.some(r => (r.prioridad||r.priority) === 'urgente') && (
                      <span className="bg-red-100 text-red-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                        {recomendaciones.filter(r => (r.prioridad||r.priority) === 'urgente').length} urgentes
                      </span>
                    )}
                  </span>
                  <span className="text-gray-400 text-xs group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div className="px-4 pb-3 space-y-1.5">
                  {recomendaciones.map((rec, i) => {
                    const clrs = {urgente:'border-red-200 bg-red-50',importante:'border-amber-200 bg-amber-50',sugerida:'border-blue-200 bg-blue-50'};
                    const bdgs = {urgente:'bg-red-100 text-red-700',importante:'bg-amber-100 text-amber-700',sugerida:'bg-blue-100 text-blue-700'};
                    const prio = rec.priority||rec.prioridad||'sugerida';
                    return (
                    <div key={i} className={'rounded-lg border p-2.5 ' + (clrs[prio]||'border-gray-200 bg-gray-50')}>
                      <div className="flex flex-wrap items-center gap-1 mb-0.5">
                        <span className={'text-[10px] font-semibold px-1.5 py-0.5 rounded-full ' + (bdgs[prio]||'bg-gray-100 text-gray-600')}>{prio}</span>
                        <span className="text-[10px] text-gray-500">{rec.medio}</span>
                        {rec.destinatario && <span className="text-[10px] text-gray-400">→ {rec.destinatario}</span>}
                      </div>
                      <p className="text-xs font-medium text-gray-800">{rec.accion}</p>
                      {rec.motivo && <p className="text-[10px] text-gray-500 mt-0.5">{rec.motivo}</p>}
                    </div>
                    );
                  })}
                </div>
              </details>
              )}

            </div>
          </div>
          )}

          {/* ═══ CUERPO PRINCIPAL: 2 columnas ═══ */}
          <div className="flex divide-x divide-gray-200 bg-white">

            {/* ─── COLUMNA IZQUIERDA ─── */}
            <div className="flex-shrink-0 bg-white" style={{ width: "300px" }}>

              {/* Datos personales */}
              <SectionHeader>Datos personales</SectionHeader>
              <table className="w-full border-collapse">
                <tbody>
                  {(() => {
                    // Filtrar valores "nan" que vienen del ETL cuando no hay dato
                    const wa = (ficha.whatsapp && ficha.whatsapp !== "nan") ? ficha.whatsapp : null;
                    const tel = (ficha.telefono && ficha.telefono !== "nan") ? ficha.telefono : null;
                    const num = wa || tel;
                    return (
                      <PersonalRow
                        label="Whatsapp"
                        value={num}
                        href={num
                          ? `https://wa.me/593${num.replace(/\D/g, "").replace(/^0/, "")}`
                          : null}
                      />
                    );
                  })()}
                  <PersonalRow label="Correo" value={ficha.correo} />
                  <PersonalRow label="Correo Ins." value={ficha.correo_institucional} />
                  <PersonalRow label="Fecha nac. y edad" value={
                    ficha?.fecha_nacimiento
                      ? `${parseLocalDate(ficha.fecha_nacimiento).toLocaleDateString("es-EC")} (${calcAge(ficha.fecha_nacimiento)} años)`
                      : "—"
                  } />
                  <PersonalRow label="Autoidentificación" value={ficha?.autoidentificacion_etnica || "—"} />
                  <PersonalRow label="Género" value={ficha?.genero || "—"} />
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
                    <td className="text-[11px] text-center px-1 py-0.5 border border-gray-200 text-gray-700 font-medium">
                      {ficha.provincia || <span className="text-gray-300 italic">—</span>}
                    </td>
                    <td className="text-[11px] text-center px-1 py-0.5 border border-gray-200 text-gray-700">
                      {ficha.ciudad || <span className="text-gray-300 italic">—</span>}
                    </td>
                    <td className="text-[11px] text-center px-1 py-0.5 border border-gray-200 text-gray-700">
                      {ficha.parroquia || <span className="text-gray-300 italic">—</span>}
                    </td>
                  </tr>
                </tbody>
              </table>

              {/* Mapa coroplético de Ecuador — ancho completo, alto proporcional */}
              {(ficha.provincia || ficha.ciudad || ficha.parroquia) ? (
                <div className="border-y border-gray-200 bg-[#F4F7FA]" style={{ aspectRatio: "4/3" }}>
                  <EcuadorMap
                    provincia={ficha.provincia}
                    ciudad={ficha.ciudad}
                    parroquia={ficha.parroquia}
                    height="100%"
                  />
                </div>
              ) : (
                <div className="bg-gray-50 border-y border-gray-200 flex flex-col items-center justify-center text-center"
                     style={{ aspectRatio: "4/3" }}>
                  <svg viewBox="0 0 80 90" className="w-16 h-16 opacity-30" fill="#1B3A6B">
                    <path d="M38 5 L50 8 L60 15 L65 25 L62 38 L70 45 L72 55 L65 65 L55 72 L42 78 L30 75 L20 68 L15 55 L18 42 L12 32 L18 20 L28 12 Z" />
                    <circle cx="38" cy="40" r="5" fill="#F0B000" opacity="1"/>
                  </svg>
                  <div className="text-[11px] text-gray-400 -mt-1">Sin datos geográficos</div>
                </div>
              )}

              <table className="w-full border-collapse">
                <tbody>
                  <PersonalRow label="Barrio o comunidad" value={ficha.barrio} />
                </tbody>
              </table>

              {/* Datos socioeconómicos */}
              <SectionHeader>Estado académico</SectionHeader>
              <table className="w-full border-collapse">
                <tbody>
                  <tr className={ficha.estado_matricula === "Matriculado" ? "bg-green-50" : "bg-red-50"}>
                    <td className="text-right text-[11px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#F2F2F2] whitespace-nowrap w-28">Pago matrícula</td>
                    <td className={`text-[11px] px-2 py-0.5 border border-gray-200 font-semibold ${ficha.estado_matricula === "Matriculado" ? "text-green-700" : "text-red-600"}`}>
                      {ficha.estado_matricula || "—"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* ─── SECCIÓN DERECHA ─── */}
            <div className="flex-1 overflow-hidden flex flex-col">

              {/* Barra de info: sede (solo EIB) / nivel / carrera */}
              <div className="flex divide-x divide-white/20 bg-[#1B3A6B] text-white">
                {isEIB && (
                  <div className="px-3 py-1.5 text-center flex-1">
                    <div className="text-[9px] opacity-50 uppercase tracking-wider">Centro de Apoyo</div>
                    <div className="text-xs font-semibold mt-0.5">{sedeDisplay}</div>
                  </div>
                )}
                <div className="px-3 py-1.5 text-center flex-1">
                  <div className="text-[9px] opacity-50 uppercase tracking-wider">Nivel</div>
                  <div className="text-xs font-semibold mt-0.5">
                    {formatNivel(ficha.nivel_academico, ficha.calificaciones) || "—"}
                  </div>
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
                        const matchedCal = matchNota(courseName, ficha.calificaciones)
                          || matchNota(courseName, ficha.calificaciones_historicas);
                        const notaTableau = matchedCal?.nota_final ?? null;
                        // Fallback: nota total del curso desde TaskSubmission (total_curso, escala 0-100)
                        const totalCurso = ts.find(t => t.total_curso != null)?.total_curso ?? null;
                        const nota = notaTableau ?? totalCurso;
                        // Escala: calificaciones Tableau (institucionales) = 0-100
                        const noteStyle = getNoteStyleHistorico(nota);
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
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500 whitespace-nowrap">
                              {(() => {
                                const nivNum = parseNivelNum(matchedCal?.nivel);
                                const grp = abbreviateGrupo(matchedCal?.grupo || acceso?.grupo || ts[0]?.grupo);
                                if (nivNum && grp) return <>{nivNum}° nivel | {grp}</>;
                                if (nivNum) return <>{nivNum}° nivel</>;
                                if (grp) return grp;
                                return <span className="text-gray-300">—</span>;
                              })()}
                            </td>
                            {/* Asignatura */}
                            <td className="px-2 py-1 border border-gray-200 font-medium text-gray-800">
                              {toTitleCase(courseName)}
                            </td>
                            {/* Nota */}
                            <td className={`px-2 py-1 border border-gray-200 text-center font-bold ${noteStyle.bg} ${noteStyle.text}`}>
                              {nota != null ? nota : <span className="text-gray-300">—</span>}
                            </td>
                            {/* Mat (número de repitencias) */}
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500">
                              {matchedCal?.numero_repitencias != null
                                ? <span className={`px-1 rounded text-[10px] font-semibold ${matchedCal.numero_repitencias > 1 ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-700"}`}>
                                    {matchedCal.numero_repitencias}
                                  </span>
                                : "—"}
                            </td>
                            {/* AVAC: días + texto compactado */}
                            <td className="px-2 py-1 border border-gray-200 text-center">
                              <span className={`font-mono text-[11px] ${diasColor}`}>
                                {diasInt != null ? `${diasInt}d` : "—"}
                              </span>
                              {acceso?.ultimo_acceso_texto && (
                                <div className="text-[10px] text-gray-400 leading-tight whitespace-nowrap">
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
                                  <span className="text-[10px] text-gray-400 self-center">+{sortedTasks.length - 8}</span>
                                )}
                                {sortedTasks.length === 0 && (
                                  <span className="text-[10px] text-gray-300 italic">Sin tareas</span>
                                )}
                              </div>
                            </td>
                            {/* Link AVAC */}
                            <td className="px-2 py-1 border border-gray-200 text-center">
                              <a href={`https://avac.ups.edu.ec/grado67/course/search.php?search=${codigo}`}
                                 target="_blank" rel="noreferrer"
                                 className="text-blue-500 hover:text-blue-700 font-mono text-[11px]">
                                {codigo}
                              </a>
                            </td>
                            {/* Docente */}
                            <td className="px-2 py-1 border border-gray-200 text-gray-600 text-[11px]">
                              {toTitleCase(acceso?.docente || ts[0]?.docente || matchedCal?.docente)
                                || <span className="text-gray-300 italic">—</span>}
                            </td>
                          </tr>
                        );
                      })}
                      {/* Materias con calificación pero sin actividad AVAC */}
                      {ficha.calificaciones?.filter(cal => {
                        // Excluir las que ya tienen match con algún curso AVAC
                        return !Object.entries(cursos).some(([, { acceso, tareas: ts }]) => {
                          const cn = acceso?.nombre_curso || ts[0]?.nombre_curso || "";
                          return matchNota(cn, [cal]);
                        });
                      }).map((cal, idx) => {
                        const noteStyle = getNoteStyleHistorico(cal.nota_final);
                        const rowIdx = Object.keys(cursos).length + idx;
                        return (
                          <tr key={`cal-${idx}`} className={rowIdx % 2 === 0 ? "bg-white" : "bg-[#F9F9F9]"}>
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500 whitespace-nowrap">
                              {(() => {
                                const nivNum = parseNivelNum(cal.nivel);
                                const grp = abbreviateGrupo(cal.grupo);
                                if (nivNum && grp) return <>{nivNum}° nivel | {grp}</>;
                                if (nivNum) return <>{nivNum}° nivel</>;
                                if (grp) return grp;
                                return <span className="text-gray-300">—</span>;
                              })()}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 font-medium text-gray-800">
                              {toTitleCase(cal.asignatura)}
                            </td>
                            <td className={`px-2 py-1 border border-gray-200 text-center font-bold ${noteStyle.bg} ${noteStyle.text}`}>
                              {cal.nota_final != null ? cal.nota_final : <span className="text-gray-300">—</span>}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500">
                              {cal.numero_repitencias != null
                                ? <span className={`px-1 rounded text-[10px] font-semibold ${cal.numero_repitencias > 1 ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-700"}`}>
                                    {cal.numero_repitencias}
                                  </span>
                                : "—"}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-center">
                              <span className="text-[10px] text-gray-300 italic">Sin AVAC</span>
                            </td>
                            <td className="px-2 py-1 border border-gray-200">
                              <span className="text-[10px] text-gray-300 italic">—</span>
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-center">
                              <span className="text-gray-300">—</span>
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-gray-600 text-[11px]">
                              {toTitleCase(cal.docente) || <span className="text-gray-300 italic">—</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Mostrar materias sin AVAC cuando no hay cursos AVAC pero sí calificaciones */}
              {Object.keys(cursos).length === 0 && ficha.calificaciones?.length > 0 && (
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
                      {ficha.calificaciones.map((cal, idx) => {
                        const noteStyle = getNoteStyleHistorico(cal.nota_final);
                        return (
                          <tr key={idx} className={idx % 2 === 0 ? "bg-white" : "bg-[#F9F9F9]"}>
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500">
                              {(() => {
                                const nivNum = parseNivelNum(cal.nivel);
                                const grp = abbreviateGrupo(cal.grupo);
                                if (nivNum && grp) return <>{nivNum}° nivel | {grp}</>;
                                if (nivNum) return <>{nivNum}° nivel</>;
                                if (grp) return grp;
                                return "—";
                              })()}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 font-medium text-gray-800">{toTitleCase(cal.asignatura)}</td>
                            <td className={`px-2 py-1 border border-gray-200 text-center font-bold ${noteStyle.bg} ${noteStyle.text}`}>{cal.nota_final ?? "—"}</td>
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500">
                              {cal.numero_repitencias != null ? cal.numero_repitencias : "—"}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-center"><span className="text-[10px] text-gray-300 italic">Sin AVAC</span></td>
                            <td className="px-2 py-1 border border-gray-200"><span className="text-[10px] text-gray-300 italic">—</span></td>
                            <td className="px-2 py-1 border border-gray-200 text-center"><span className="text-gray-300">—</span></td>
                            <td className="px-2 py-1 border border-gray-200 text-gray-600 text-[11px]">{toTitleCase(cal.docente) || "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Fila resumen de KPIs */}
              <div className="grid grid-cols-2 divide-x divide-gray-200 border-t border-gray-200 bg-gradient-to-r from-gray-50 to-white">
                <div className="py-3 px-4 text-center">
                  <div className="text-[9px] text-gray-400 uppercase tracking-widest font-semibold">Días sin AVAC</div>
                  <div className={`font-bold text-lg mt-0.5 ${
                    ficha.dias_sin_acceso == null ? "text-gray-300"
                    : ficha.dias_sin_acceso > 14 ? "text-red-600"
                    : ficha.dias_sin_acceso > 7 ? "text-orange-500"
                    : "text-green-600"}`}>
                    {ficha.dias_sin_acceso != null ? `${Math.round(ficha.dias_sin_acceso)}d` : "—"}
                  </div>
                </div>
                <div className="py-3 px-4 text-center">
                  <div className="text-[9px] text-gray-400 uppercase tracking-widest font-semibold">Tareas entregadas</div>
                  <div className={`font-bold text-lg mt-0.5 ${
                    ficha.porcentaje_tareas == null ? "text-gray-300"
                    : ficha.porcentaje_tareas < 50 ? "text-red-600"
                    : ficha.porcentaje_tareas < 75 ? "text-orange-500"
                    : "text-green-600"}`}>
                    {ficha.porcentaje_tareas != null ? `${Math.round(ficha.porcentaje_tareas)}%` : "—"}
                  </div>
                </div>
              </div>

              {/* ══ MALLA CURRICULAR HISTÓRICA (TableauHistorico P60–P67+) ══ */}
              {ficha.calificaciones_historicas?.length > 0 && (() => {
                // Agrupar por período
                const porPeriodo = {};
                ficha.calificaciones_historicas.forEach(c => {
                  const p = c.periodo || "Sin período";
                  if (!porPeriodo[p]) porPeriodo[p] = [];
                  porPeriodo[p].push(c);
                });
                const periodos = Object.keys(porPeriodo).sort();

                return (
                  <div className="border-t border-gray-200">
                    <SectionHeader>
                      Malla curricular — {periodos.length} semestres · {ficha.calificaciones_historicas.length} asignaturas
                      <span className="text-gray-400 font-normal ml-2 text-[9px] normal-case tracking-normal">
                        escala 0–100 · ≥70 aprobado
                      </span>
                    </SectionHeader>
                    <div className="overflow-x-auto bg-[#FAFAFA] px-2 py-2">
                      <div className="flex gap-2" style={{ minWidth: "max-content" }}>
                        {periodos.map(periodo => {
                          const asigs = porPeriodo[periodo];
                          const promedio = asigs.reduce((s, c) => s + (c.nota_final ?? 0), 0) / asigs.length;
                          const promedioStyle = getNoteStyleHistorico(Math.round(promedio));
                          return (
                            <div key={periodo} className="flex-shrink-0 flex flex-col" style={{ minWidth: "80px" }}>
                              {/* Encabezado de período */}
                              <div className="bg-[#1B3A6B] text-white text-center rounded-t px-1 py-0.5 text-[9px] font-bold uppercase tracking-wider">
                                {periodo}
                              </div>
                              {/* Chips de asignaturas */}
                              <div className="border border-t-0 border-gray-200 rounded-b bg-white px-1 pt-1 pb-0.5 flex flex-col gap-0.5">
                                {asigs.map((c, i) => (
                                  <MallaChip
                                    key={i}
                                    asignatura={c.asignatura}
                                    nota_final={c.nota_final}
                                    docente={c.docente}
                                  />
                                ))}
                                {/* Promedio del período */}
                                <div className={`mt-0.5 text-center text-[9px] font-bold border-t border-gray-100 pt-0.5 ${promedioStyle.text}`}>
                                  x̄ {isNaN(promedio) ? "—" : promedio.toFixed(1)}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                        {/* ── Columna del semestre actual ── */}
                        {ficha.calificaciones?.length > 0 && (() => {
                          const promActual = ficha.calificaciones.reduce((s, c) => s + (c.nota_final ?? 0), 0) / ficha.calificaciones.length;
                          const promActualStyle = getNoteStyleHistorico(Math.round(promActual));
                          return (
                            <div className="flex-shrink-0 flex flex-col" style={{ minWidth: "80px" }}>
                              <div className="bg-[#F0B000] text-white text-center rounded-t px-1 py-0.5 text-[9px] font-bold uppercase tracking-wider">
                                {formatNivel(ficha.nivel_academico, ficha.calificaciones) || "Sem. actual"}
                              </div>
                              <div className="border border-t-0 border-[#F0B000] rounded-b bg-[#FFFDF5] px-1 pt-1 pb-0.5 flex flex-col gap-0.5">
                                {ficha.calificaciones.map((c, i) => (
                                  <MallaChip
                                    key={i}
                                    asignatura={c.asignatura}
                                    nota_final={c.nota_final}
                                    docente={c.docente}
                                  />
                                ))}
                                <div className={`mt-0.5 text-center text-[9px] font-bold border-t border-gray-100 pt-0.5 ${promActualStyle.text}`}>
                                  x̄ {isNaN(promActual) ? "—" : promActual.toFixed(1)}
                                </div>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    </div>
                    {/* Leyenda */}
                    <div className="flex gap-3 px-2 pb-1 bg-[#FAFAFA] border-t border-gray-100">
                      <span className="flex items-center gap-1 text-[9px] text-gray-400">
                        <span className="inline-block w-2 h-2 rounded-sm bg-green-200 border border-green-300"></span>≥70 Aprobado
                      </span>
                      <span className="flex items-center gap-1 text-[9px] text-gray-400">
                        <span className="inline-block w-2 h-2 rounded-sm bg-yellow-200 border border-yellow-300"></span>60–69 En proceso
                      </span>
                      <span className="flex items-center gap-1 text-[9px] text-gray-400">
                        <span className="inline-block w-2 h-2 rounded-sm bg-red-200 border border-red-300"></span>&lt;60 Reprobado
                      </span>
                    </div>
                  </div>
                );
              })()}

              {/* Calificaciones semestre actual: si no hay malla histórica pero sí calificaciones, mostrar como columna única */}
              {(!ficha.calificaciones_historicas || ficha.calificaciones_historicas.length === 0) && ficha.calificaciones?.length > 0 && (() => {
                const promActual = ficha.calificaciones.reduce((s, c) => s + (c.nota_final ?? 0), 0) / ficha.calificaciones.length;
                const promActualStyle = getNoteStyleHistorico(Math.round(promActual));
                return (
                  <div className="border-t border-gray-200">
                    <SectionHeader>
                      Malla curricular — semestre actual · {ficha.calificaciones.length} asignaturas
                      <span className="text-gray-400 font-normal ml-2 text-[9px] normal-case tracking-normal">
                        escala 0–100 · ≥70 aprobado
                      </span>
                    </SectionHeader>
                    <div className="overflow-x-auto bg-[#FAFAFA] px-2 py-2">
                      <div className="flex gap-2" style={{ minWidth: "max-content" }}>
                        <div className="flex-shrink-0 flex flex-col" style={{ minWidth: "80px" }}>
                          <div className="bg-[#F0B000] text-white text-center rounded-t px-1 py-0.5 text-[9px] font-bold uppercase tracking-wider">
                            {formatNivel(ficha.nivel_academico, ficha.calificaciones) || "Sem. actual"}
                          </div>
                          <div className="border border-t-0 border-[#F0B000] rounded-b bg-[#FFFDF5] px-1 pt-1 pb-0.5 flex flex-col gap-0.5">
                            {ficha.calificaciones.map((c, i) => (
                              <MallaChip key={i} asignatura={c.asignatura} nota_final={c.nota_final} docente={c.docente} />
                            ))}
                            <div className={`mt-0.5 text-center text-[9px] font-bold border-t border-gray-100 pt-0.5 ${promActualStyle.text}`}>
                              x̄ {isNaN(promActual) ? "—" : promActual.toFixed(1)}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })()}

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

          {/* ═══ PRÁCTICAS PREPROFESIONALES (próximamente) ═══ */}
          <div className="border-t border-gray-300">
            <div className="bg-[#1B3A6B] text-white px-4 py-1 text-[10px] font-bold uppercase tracking-wider">
              Prácticas Preprofesionales
            </div>
            <div className="bg-white py-4 text-center text-[11px] text-gray-400 italic">
              Módulo en desarrollo — próximamente
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
                <div className="py-5 text-center text-[11px] text-gray-300 italic">
                  Sin intervenciones registradas
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {ficha.intervenciones.map(inv => (
                    <div key={inv.id} className="px-4 py-2 flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-1 mb-0.5">
                          {inv.medio && (
                            <span className="bg-blue-100 text-blue-700 text-[10px] font-medium px-1.5 py-0.5 rounded-full">
                              {inv.medio}
                            </span>
                          )}
                          {inv.motivo && <span className="text-[11px] text-gray-500">{inv.motivo}</span>}
                        </div>
                        {inv.observacion && <p className="text-xs text-gray-700 leading-relaxed">{inv.observacion}</p>}
                        <div className="flex flex-wrap gap-2 mt-0.5 text-[10px] text-gray-400">
                          {inv.estado && <span>Estado: <strong className="text-gray-600">{inv.estado}</strong></span>}
                          {inv.asignatura && <span>· {inv.asignatura}</span>}
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="text-[10px] text-gray-400">
                          {inv.created_at ? new Date(inv.created_at).toLocaleDateString("es-EC") : ""}
                        </div>
                        {inv.monitor_nombre && (
                          <div className="text-[10px] text-gray-400 truncate max-w-[90px]">{inv.monitor_nombre}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ═══ PIE DE PÁGINA ═══ */}
          <div className="bg-gradient-to-r from-[#0F2444] to-[#1B3A6B] text-white/50 text-center py-2 text-[9px] tracking-widest uppercase">
            Yachay Deep — Pacha Tech © &nbsp;·&nbsp; {today}
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
