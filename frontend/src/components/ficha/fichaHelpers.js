/**
 * Funciones utilitarias compartidas para la FichaEstudiante.
 * Extraídas del monolito original (Épica 1.5).
 */

export function getNoteStyle(nota, max = 40) {
  if (nota == null) return { bg: "", text: "text-gray-400", border: "" };
  const pct = nota / max;
  if (pct >= 0.70) return { bg: "bg-green-100",  text: "text-green-800",  border: "border-green-300" };
  if (pct >= 0.50) return { bg: "bg-yellow-100", text: "text-yellow-800", border: "border-yellow-300" };
  return               { bg: "bg-red-100",    text: "text-red-700",   border: "border-red-300" };
}

export function getDiagnosticoStyle(diagnostico) {
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

export function getRiesgoStyle(nivel) {
  if (nivel === "Alto")  return { bg: "bg-red-100",    text: "text-red-700",    label: "En riesgo" };
  if (nivel === "Medio") return { bg: "bg-yellow-100", text: "text-yellow-700", label: "Riesgo moderado" };
  if (nivel === "Bajo")  return { bg: "bg-green-100",  text: "text-green-700",  label: "Sin riesgo" };
  return                        { bg: "bg-gray-100",   text: "text-gray-500",   label: "Sin evaluar" };
}

export function getCompromisoLabel(val) {
  if (val == null) return "—";
  if (val < 0.3) return "Bajo";
  if (val < 0.6) return "Medio";
  return "Alto";
}

export function parseLocalDate(isoDate) {
  if (!isoDate) return null;
  return new Date(isoDate + (isoDate.includes("T") ? "" : "T00:00:00"));
}

export function calcAge(isoDate) {
  if (!isoDate) return null;
  const birth = parseLocalDate(isoDate);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  return age;
}

export function ordinalNivel(n) {
  const map = { 1: "1er", 2: "2do", 3: "3er", 4: "4to", 5: "5to", 6: "6to", 7: "7mo", 8: "8vo" };
  return map[n] || `${n}°`;
}

export function compactarAcceso(texto) {
  if (!texto) return null;
  return texto
    .replace(/(\d+)\s*días?/i,    "$1d")
    .replace(/(\d+)\s*horas?/i,   " $1h")
    .replace(/(\d+)\s*minutos?/i, " $1m")
    .replace(/(\d+)\s*segundos?/i,"")
    .replace(/,\s*/g, " ")
    .trim();
}

export function toTitleCase(str) {
  if (!str) return str;
  const ROMAN = /^(I{1,3}|IV|V|VI{0,3}|IX|X{0,3})$/i;
  return str
    .toLowerCase()
    .split(/\s+/)
    .map(w => ROMAN.test(w) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function abbreviateGrupo(grupo) {
  if (!grupo) return null;
  const m = grupo.match(/GRUPO\s*-?\s*(\d+)/i);
  if (m) return `G${m[1]}`;
  const num = grupo.match(/\d+/);
  return num ? `G${num[0]}` : grupo.length > 8 ? grupo.slice(0, 8) + "…" : grupo;
}

export function formatNivel(nivelAcademico, calificaciones, calificacionesHistoricas) {
  if (nivelAcademico > 0) return `${ordinalNivel(nivelAcademico)} nivel`;
  const extractNivel = (arr) => {
    if (!arr?.length) return null;
    const niveles = arr.map(c => c.nivel).filter(Boolean);
    if (niveles.length === 0) return null;
    const freq = {};
    niveles.forEach(n => { freq[n] = (freq[n] || 0) + 1; });
    const max = Math.max(...Object.values(freq));
    const best = Object.entries(freq).find(([, v]) => v === max);
    if (best) {
      const n = parseInt(best[0], 10);
      if (!isNaN(n) && n >= 1 && n <= 12) return `${ordinalNivel(n)} nivel`;
    }
    return null;
  };
  return extractNivel(calificaciones) || extractNivel(calificacionesHistoricas) || null;
}

export function parseNivelNum(val) {
  if (val == null) return null;
  const n = typeof val === "number" ? val : parseInt(val, 10);
  return (!isNaN(n) && n >= 1 && n <= 12) ? n : null;
}

export function getNoteStyleHistorico(nota) {
  if (nota == null) return { bg: "", text: "text-gray-400" };
  if (nota >= 70) return { bg: "bg-green-50",  text: "text-green-700" };
  if (nota >= 60) return { bg: "bg-yellow-50", text: "text-yellow-700" };
  return                  { bg: "bg-red-50",   text: "text-red-600" };
}

export function getMallaEstado(estado) {
  switch (estado) {
    case "aprobada":   return { bg: "bg-green-100",  border: "border-green-300",  text: "text-green-800" };
    case "cursando":   return { bg: "bg-amber-100",  border: "border-amber-400",  text: "text-amber-800" };
    case "reprobada":  return { bg: "bg-red-100",    border: "border-red-300",    text: "text-red-700" };
    default:           return { bg: "bg-gray-100",   border: "border-gray-200",   text: "text-gray-400" };
  }
}

export function abreviarAsignatura(nombre, maxLen = 32) {
  if (!nombre) return "—";
  const s = nombre.toUpperCase();
  const ABREVIATURAS = {
    "METODOLOGÍA": "METOD.",
    "INVESTIGACIÓN": "INVEST.",
    "COMUNICACIÓN": "COMUN.",
    "TECNOLOGÍA": "TECNOL.",
    "EDUCACIÓN": "EDUC.",
    "DESARROLLO": "DESARR.",
    "ORGANIZACIÓN": "ORG.",
    "ADMINISTRACIÓN": "ADMIN.",
    "PLANIFICACIÓN": "PLANIF.",
    "EVALUACIÓN": "EVAL.",
    "PEDAGOGÍA": "PEDAG.",
    "PSICOLOGÍA": "PSICOL.",
    "DIDÁCTICA": "DIDÁCT.",
    "PROFESIONAL": "PROF.",
    "APRENDIZAJE": "APREND.",
    "INTERCULTURAL": "INTERC.",
    "BILINGÜE": "BILING.",
    "GENERAL": "GRAL.",
    "BÁSICA": "BÁS.",
    "APLICADA": "APLIC.",
    "SOCIOLOGÍA": "SOCIOL.",
    "FILOSÓFICA": "FILOS.",
  };
  let result = s;
  if (result.length > maxLen) {
    for (const [full, abbr] of Object.entries(ABREVIATURAS)) {
      result = result.replace(new RegExp(full, "gi"), abbr);
    }
  }
  if (result.length > maxLen) {
    const words = result.split(/\s+/);
    if (words.length > 2) {
      result = words.slice(0, 3).join(" ");
      if (result.length > maxLen) result = result.slice(0, maxLen - 1) + "…";
    }
  }
  return toTitleCase(result);
}
