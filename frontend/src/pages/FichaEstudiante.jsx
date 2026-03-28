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

/** Trend chart component: BI-style sparkline + KPIs — full-width, compact height */
function TrendChart({ calificacionesHistoricas, calificaciones }) {
  const chartRef = useRef(null);
  const [chartW, setChartW] = useState(600);
  const [hoveredIdx, setHoveredIdx] = useState(null);

  if (!calificacionesHistoricas?.length) return null;

  // Group by periodo and calculate average + count
  const periodos = {};
  calificacionesHistoricas.forEach(c => {
    if (!periodos[c.periodo]) periodos[c.periodo] = [];
    if (c.nota_final != null) periodos[c.periodo].push(c.nota_final);
  });
  if (calificaciones?.length > 0) {
    const notas = calificaciones.filter(c => c.nota_final != null).map(c => c.nota_final);
    if (notas.length > 0) periodos["Actual"] = notas;
  }

  // Ordenar períodos cronológicamente, "Actual" siempre al final
  const periodoKeys = Object.keys(periodos)
    .filter(k => k !== "Actual")
    .sort()
    .concat(periodos["Actual"] ? ["Actual"] : []);
  if (periodoKeys.length < 2) return null;

  const averages = periodoKeys.map(p => {
    const v = periodos[p];
    return v.length > 0 ? v.reduce((a, b) => a + b, 0) / v.length : 0;
  });
  const counts = periodoKeys.map(p => periodos[p].length);

  const firstAvg = averages[0];
  const lastAvg = averages[averages.length - 1];
  const cambio = lastAvg - firstAvg;
  const trendUp = cambio > 0;
  const trendFlat = Math.abs(cambio) < 0.5;
  const maxAvg = Math.max(...averages);
  const minAvg = Math.min(...averages);
  const bestIdx = averages.indexOf(maxAvg);
  const worstIdx = averages.indexOf(minAvg);

  // Responsive width
  useEffect(() => {
    if (!chartRef.current) return;
    const ro = new ResizeObserver(entries => {
      for (const e of entries) setChartW(e.contentRect.width);
    });
    ro.observe(chartRef.current);
    return () => ro.disconnect();
  }, []);

  // SVG dimensions — compact
  const svgH = 80;
  const pad = { top: 8, right: 12, bottom: 18, left: 32 };
  const cw = chartW - pad.left - pad.right;
  const ch = svgH - pad.top - pad.bottom;

  // Scale
  const yMin = Math.max(0, minAvg - 8);
  const yMax = Math.min(100, maxAvg + 8);
  const yRange = yMax - yMin || 1;
  const scaleX = (i) => pad.left + (i / (averages.length - 1)) * cw;
  const scaleY = (v) => pad.top + ch - ((v - yMin) / yRange) * ch;

  const points = averages.map((avg, i) => ({ x: scaleX(i), y: scaleY(avg), value: avg }));

  // Curva suavizada — Catmull-Rom (tensión 0.5 para curvas más visibles)
  const buildPath = (pts) => {
    if (pts.length < 2) return "";
    if (pts.length === 2) {
      // Con 2 puntos: curva ligera usando un punto de control central elevado
      const mx = (pts[0].x + pts[1].x) / 2;
      const my = (pts[0].y + pts[1].y) / 2 - Math.abs(pts[1].y - pts[0].y) * 0.15;
      return `M${pts[0].x},${pts[0].y}Q${mx},${my},${pts[1].x},${pts[1].y}`;
    }
    const tension = 0.35;
    let d = `M${pts[0].x},${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[Math.max(0, i - 1)];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[Math.min(pts.length - 1, i + 2)];
      const cp1x = p1.x + (p2.x - p0.x) * tension;
      const cp1y = p1.y + (p2.y - p0.y) * tension;
      const cp2x = p2.x - (p3.x - p1.x) * tension;
      const cp2y = p2.y - (p3.y - p1.y) * tension;
      d += `C${cp1x},${cp1y},${cp2x},${cp2y},${p2.x},${p2.y}`;
    }
    return d;
  };
  const linePath = buildPath(points);
  const areaPath = `${linePath}L${points[points.length - 1].x},${pad.top + ch}L${points[0].x},${pad.top + ch}Z`;

  // Línea de tendencia (regresión lineal) — solo con ≥4 períodos
  const showTrendLine = averages.length >= 4;
  let trendLinePath = "";
  if (showTrendLine) {
    const n = averages.length;
    const meanX = (n - 1) / 2;
    const meanY = averages.reduce((a, b) => a + b, 0) / n;
    let num = 0, den = 0;
    for (let i = 0; i < n; i++) {
      num += (i - meanX) * (averages[i] - meanY);
      den += (i - meanX) * (i - meanX);
    }
    const slope = den !== 0 ? num / den : 0;
    const intercept = meanY - slope * meanX;
    const y0 = intercept;
    const yN = slope * (n - 1) + intercept;
    trendLinePath = `M${scaleX(0)},${scaleY(y0)}L${scaleX(n - 1)},${scaleY(yN)}`;
  }

  // 70-pt reference line
  const y70 = (70 >= yMin && 70 <= yMax) ? scaleY(70) : null;

  // Colors
  const lineColor = trendFlat ? "#6366f1" : trendUp ? "#059669" : "#dc2626";
  const areaColor = trendFlat ? "#eef2ff" : trendUp ? "#ecfdf5" : "#fef2f2";
  const dotColor = trendFlat ? "#818cf8" : trendUp ? "#34d399" : "#f87171";
  const kpiColor = trendFlat ? "text-indigo-600" : trendUp ? "text-emerald-600" : "text-red-600";
  const kpiBg = trendFlat ? "bg-indigo-50" : trendUp ? "bg-emerald-50" : "bg-red-50";
  const trendIcon = trendFlat ? "→" : trendUp ? "↑" : "↓";
  const trendLabel = trendFlat ? "Estable" : trendUp ? "Mejorando" : "Descendiendo";

  // Y ticks (3 ticks)
  const yTicks = [yMin, (yMin + yMax) / 2, yMax].map(v => Math.round(v));

  return (
    <div className="border-t border-gray-200">
      <SectionHeader>Tendencia Académica</SectionHeader>
      <div className="bg-white" style={{ padding: "8px 12px 10px" }}>
        {/* KPI row — flush horizontal */}
        <div className="flex items-center gap-2 mb-1" style={{ fontSize: "11px" }}>
          {/* Trend badge */}
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-semibold ${kpiBg} ${kpiColor}`}
                style={{ fontSize: "10px" }}>
            {trendIcon} {trendLabel}
          </span>
          {/* KPIs inline */}
          <div className="flex items-center gap-3 ml-auto text-gray-500" style={{ fontSize: "10px" }}>
            <span>Inicio <strong className="text-gray-800 ml-0.5">{firstAvg.toFixed(1)}</strong></span>
            <span className="text-gray-300">|</span>
            <span>Actual <strong className="text-gray-800 ml-0.5">{lastAvg.toFixed(1)}</strong></span>
            <span className="text-gray-300">|</span>
            <span>
              Cambio{" "}
              <strong className={`ml-0.5 ${kpiColor}`}>
                {cambio > 0 ? "+" : ""}{cambio.toFixed(1)}
              </strong>
            </span>
            <span className="text-gray-300">|</span>
            <span>
              Máx <strong className="text-gray-800 ml-0.5">{maxAvg.toFixed(1)}</strong>
              <span className="text-gray-400 ml-0.5">({periodoKeys[bestIdx]})</span>
            </span>
          </div>
        </div>

        {/* Chart — full-width responsive SVG */}
        <div ref={chartRef} className="w-full" style={{ minWidth: 0 }}>
          <svg width={chartW} height={svgH} style={{ display: "block" }}
               onMouseLeave={() => setHoveredIdx(null)}>
            <defs>
              <linearGradient id="trend-area-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={areaColor} stopOpacity="0.7" />
                <stop offset="100%" stopColor={areaColor} stopOpacity="0.05" />
              </linearGradient>
            </defs>

            {/* Y ticks */}
            {yTicks.map((v, i) => {
              const y = scaleY(v);
              return (
                <g key={`yt-${i}`}>
                  <line x1={pad.left} y1={y} x2={chartW - pad.right} y2={y}
                        stroke="#f3f4f6" strokeWidth="1" />
                  <text x={pad.left - 5} y={y + 3} fontSize="9" fill="#b0b0b0" textAnchor="end">{v}</text>
                </g>
              );
            })}

            {/* 70-pt reference line */}
            {y70 != null && (
              <g>
                <line x1={pad.left} y1={y70} x2={chartW - pad.right} y2={y70}
                      stroke="#f59e0b" strokeWidth="1" strokeDasharray="3,3" opacity="0.5" />
                <text x={chartW - pad.right + 2} y={y70 + 3} fontSize="8" fill="#f59e0b">70</text>
              </g>
            )}

            {/* Area fill */}
            <path d={areaPath} fill="url(#trend-area-grad)" />

            {/* Trend line — regresión lineal (solo ≥4 períodos) */}
            {showTrendLine && (
              <path d={trendLinePath} fill="none" stroke={lineColor} strokeWidth="1.5"
                    strokeDasharray="6,4" opacity="0.35" />
            )}

            {/* Line — curva suavizada */}
            <path d={linePath} fill="none" stroke={lineColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

            {/* Data points + value labels */}
            {points.map((p, i) => {
              const isHovered = hoveredIdx === i;
              const isBest = i === bestIdx;
              const isWorst = i === worstIdx;
              const isEnd = i === 0 || i === points.length - 1;
              const showLabel = isHovered || isBest || isWorst || isEnd || points.length <= 5;
              const below70 = p.value < 70;
              const dotFill = below70 ? "#f59e0b" : dotColor;
              return (
                <g key={i}>
                  {/* Hover hit area */}
                  <rect x={p.x - cw / (averages.length * 2)} y={pad.top} width={cw / averages.length} height={ch}
                        fill="transparent" onMouseEnter={() => setHoveredIdx(i)} />
                  {/* Vertical indicator on hover */}
                  {isHovered && (
                    <line x1={p.x} y1={pad.top} x2={p.x} y2={pad.top + ch} stroke={lineColor} strokeWidth="1" opacity="0.2" />
                  )}
                  <circle cx={p.x} cy={p.y} r={isHovered ? 5 : 3.5} fill={dotFill} stroke="white" strokeWidth="2"
                          style={{ transition: "r 0.15s" }} />
                  {showLabel && (
                    <text x={p.x} y={p.y - 7} fontSize="9" fontWeight={isHovered || isBest ? "700" : "600"}
                          fill={below70 ? "#d97706" : "#374151"} textAnchor="middle">
                      {p.value.toFixed(1)}
                    </text>
                  )}
                </g>
              );
            })}

            {/* X-axis labels */}
            {periodoKeys.map((periodo, i) => {
              const x = scaleX(i);
              const isLast = periodo === "Actual";
              return (
                <text key={`xl-${i}`} x={x} y={svgH - 3} fontSize="9"
                      fill={isLast ? lineColor : "#9ca3af"} fontWeight={isLast ? "700" : "400"}
                      textAnchor="middle">
                  {isLast ? "Actual" : periodo}
                </text>
              );
            })}
          </svg>
        </div>

        {/* Hover tooltip row */}
        {hoveredIdx != null && (
          <div className="flex items-center gap-3 text-gray-500 mt-0.5" style={{ fontSize: "9px", minHeight: "14px" }}>
            <span className="font-semibold text-gray-700">{periodoKeys[hoveredIdx]}</span>
            <span>Promedio: <strong className="text-gray-800">{averages[hoveredIdx].toFixed(1)}</strong></span>
            <span>Materias: <strong className="text-gray-800">{counts[hoveredIdx]}</strong></span>
            {hoveredIdx > 0 && (
              <span>
                vs anterior:{" "}
                <strong className={averages[hoveredIdx] >= averages[hoveredIdx - 1] ? "text-emerald-600" : "text-red-600"}>
                  {(averages[hoveredIdx] - averages[hoveredIdx - 1]) > 0 ? "+" : ""}
                  {(averages[hoveredIdx] - averages[hoveredIdx - 1]).toFixed(1)}
                </strong>
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
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
function formatNivel(nivelAcademico, calificaciones, calificacionesHistoricas) {
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
  // Fallback 2: nivel más alto del último período histórico
  if (calificacionesHistoricas?.length > 0) {
    const periodos = [...new Set(calificacionesHistoricas.map(c => c.periodo))].sort();
    const ultimoPeriodo = periodos[periodos.length - 1];
    const delUltimo = calificacionesHistoricas.filter(c => c.periodo === ultimoPeriodo);
    const niveles = delUltimo.map(c => c.nivel).filter(n => n != null && n > 0 && n <= 12);
    if (niveles.length > 0) {
      const maxNivel = Math.max(...niveles) + 1; // Next level after the last completed
      return maxNivel <= 12 ? `${maxNivel}° Nivel` : `${Math.max(...niveles)}° Nivel`;
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

// ── Chip de calificación en malla histórica (legacy — used in old grid) ──────
function MallaChip({ asignatura, nota_final, docente }) {
  const s = getNoteStyleHistorico(nota_final);
  const titleName = toTitleCase(asignatura) || "";
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

// ── Estilos para la malla fija ──────────────────────────────────────────────
function getMallaEstado(estado) {
  switch (estado) {
    case "aprobada":   return { bg: "bg-green-50",  border: "border-green-300", text: "text-green-800",  label: "Aprobada" };
    case "reprobada":  return { bg: "bg-red-50",    border: "border-red-300",   text: "text-red-700",    label: "Reprobada" };
    case "en_proceso": return { bg: "bg-yellow-50", border: "border-yellow-300",text: "text-yellow-800", label: "En proceso" };
    case "cursando":   return { bg: "bg-amber-50",  border: "border-amber-400", text: "text-amber-800",  label: "Cursando" };
    default:           return { bg: "bg-gray-50",   border: "border-gray-200",  text: "text-gray-400",   label: "No cursado" };
  }
}

// ── Abreviar nombres largos de asignaturas ──────────────────────────────────
function abreviarAsignatura(nombre, maxLen = 32) {
  // Siempre quitar conectores primero para compactar
  let short = nombre
    .replace(/\b(De La|De Los|De Las|Del|De|La|Las|Los|El|Y|En|Para|Con|Por|A)\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  if (short.length <= maxLen) return short;
  // Quitar subtítulos después de ":" para acortar más
  const colonIdx = short.indexOf(":");
  if (colonIdx > 0 && colonIdx <= maxLen - 1) {
    return short.slice(0, colonIdx).trim() + "…";
  }
  // Truncar con elipsis
  const words = short.split(" ");
  let result = "";
  for (const w of words) {
    if ((result + " " + w).trim().length > maxLen - 1) break;
    result = (result + " " + w).trim();
  }
  return result + "…";
}

// ── Celda compacta de la malla con soporte de repeticiones ──────────────────
function MallaCeldaFija({ asignatura }) {
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

      {/* Nombre abreviado + nota — overflow controlado */}
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

      {/* Tooltip: nombre completo (siempre) + historial de intentos (si repetición) */}
      {showTooltip && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-1 bg-gray-900 text-white rounded-lg shadow-xl px-3 py-2"
             style={{ minWidth: "200px", maxWidth: "300px", fontSize: "10px" }}>
          <div className="font-bold mb-0.5" style={{ fontSize: "11px", color: esRepeticion ? "#fdba74" : "#e5e7eb", whiteSpace: "normal" }}>
            {titleName}
          </div>
          {esRepeticion && asignatura.intentos.length > 0 && (
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
  const [activeTab, setActiveTab] = useState("indicadores");
  const [comparativa, setComparativa] = useState(null);
  const [loadingComparativa, setLoadingComparativa] = useState(false);
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
    setActiveTab("indicadores");
    try {
      const data = await api.getFicha(id);
      setFicha(data);
      setQuery(data.nombre || "");
      navigate(`/ficha/${id}`, { replace: true });
      // Cargar análisis comparativo
      setLoadingComparativa(true);
      api.getStudentComparativa(id).then(setComparativa).catch(() => setComparativa(null)).finally(() => setLoadingComparativa(false));
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
                {formatNivel(ficha.nivel_academico, ficha.calificaciones, ficha.calificaciones_historicas) && (
                  <>
                    <span className="hidden sm:inline w-px h-3 bg-white/20" />
                    <span className="bg-white/15 text-white px-2.5 py-0.5 rounded-full text-xs font-semibold">
                      {formatNivel(ficha.nivel_academico, ficha.calificaciones, ficha.calificaciones_historicas)}
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

          {/* ===== PANEL IA: Tabbed Navigation ===== */}
{(prediccion?.xai || prediccion?.contexto_conductual?.length > 0 || contrafactual?.contrafactual_desercion?.cambios?.length > 0 || contrafactual?.contrafactual_conductual?.escenarios?.length > 0 || recomendaciones.length > 0) && (
<div className="border-t border-gray-200 bg-[#FAFBFF]">
  {/* Tab headers */}
  <div className="flex border-b border-gray-200 bg-white">
    <button
      onClick={() => setActiveTab("indicadores")}
      className={`flex-1 px-4 py-2.5 text-[11px] font-bold uppercase tracking-wide transition-colors ${
        activeTab === "indicadores"
          ? "text-[#1B3A6B] border-b-2 border-[#1B3A6B] bg-blue-50/50"
          : "text-gray-400 hover:text-gray-600 hover:bg-gray-50"
      }`}
    >
      📊 Indicadores · Predicción IA
    </button>
    {prediccion?.contexto_conductual?.length > 0 && (
      <button
        onClick={() => setActiveTab("alertas")}
        className={`flex-1 px-4 py-2.5 text-[11px] font-bold uppercase tracking-wide transition-colors ${
          activeTab === "alertas"
            ? "text-[#1B3A6B] border-b-2 border-[#1B3A6B] bg-blue-50/50"
            : "text-gray-400 hover:text-gray-600 hover:bg-gray-50"
        }`}
      >
        ⚡ Alertas conductuales
        <span className="bg-red-100 text-red-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full ml-1.5">
          {prediccion.contexto_conductual.length}
        </span>
      </button>
    )}
    {(contrafactual?.contrafactual_conductual?.escenarios?.length > 0 || recomendaciones.length > 0) && (
      <button
        onClick={() => setActiveTab("acciones")}
        className={`flex-1 px-4 py-2.5 text-[11px] font-bold uppercase tracking-wide transition-colors ${
          activeTab === "acciones"
            ? "text-[#1B3A6B] border-b-2 border-[#1B3A6B] bg-blue-50/50"
            : "text-gray-400 hover:text-gray-600 hover:bg-gray-50"
        }`}
      >
        🎯 ¿Qué puede hacer el estudiante?
      </button>
    )}
  </div>

  {/* Tab content */}
  <div className="p-4">
    {/* ── Tab: Indicadores · Predicción IA ── */}
    {activeTab === "indicadores" && (
      <div className="space-y-3">
        {prediccion?.xai && (
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
        )}
        {/* Contrafactuales ML (escenarios de cambio cuantitativo) */}
        {contrafactual?.contrafactual_desercion?.cambios?.length > 0 && (
          <div className="space-y-2 mt-3">
            <h4 className="text-[11px] font-bold text-gray-500 uppercase tracking-wide flex items-center gap-1.5">
              🔄 Escenarios Contrafactuales
              <span className="text-[10px] font-normal text-gray-400 normal-case ml-1">¿Qué cambiar para reducir el riesgo?</span>
            </h4>
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
        )}
      </div>
    )}

    {/* ── Tab: Alertas Conductuales ── */}
    {activeTab === "alertas" && prediccion?.contexto_conductual?.length > 0 && (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
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
    )}

    {/* ── Tab: ¿Qué puede hacer el estudiante? ── */}
    {activeTab === "acciones" && (
      <div className="space-y-3">
        {/* Contrafactuales Conductuales */}
        {contrafactual?.contrafactual_conductual?.escenarios?.length > 0 && (
          <div className="space-y-2">
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
                  {/* Botón Notificar Tutoría */}
                  {esc.tipo === "tutoria" && (
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        const btn = e.currentTarget;
                        btn.disabled = true;
                        btn.textContent = "Enviando...";
                        try {
                          const res = await api.notifyTutoria({
                            student_id: esc.student_id,
                            asignatura: esc.asignatura,
                            docente: esc.docente,
                            motivo: esc.motivo_tutoria || esc.valor_actual,
                          });
                          btn.textContent = res.email_enviado ? "✓ Notificado" : "✓ Registrado";
                          btn.className = btn.className.replace("bg-blue-600", "bg-green-600").replace("hover:bg-blue-700", "");
                        } catch (err) {
                          btn.textContent = "Error";
                          btn.disabled = false;
                          console.error(err);
                        }
                      }}
                      className="flex-shrink-0 bg-blue-600 hover:bg-blue-700 text-white text-[10px] font-medium px-3 py-1.5 rounded-lg transition-colors shadow-sm whitespace-nowrap"
                      title="Enviar notificación de tutoría al estudiante y registrar intervención"
                    >
                      📧 Notificar tutoría
                    </button>
                  )}
                </div>
              </div>
              );
            })}
          </div>
        )}

        {/* Recomendaciones Automáticas */}
        {recomendaciones.length > 0 && (
          <div className="space-y-1.5">
            <h4 className="text-[11px] font-bold text-gray-500 uppercase tracking-wide flex items-center gap-1.5">
              💡 Recomendaciones
              {recomendaciones.some(r => (r.prioridad||r.priority) === 'urgente') && (
                <span className="bg-red-100 text-red-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  {recomendaciones.filter(r => (r.prioridad||r.priority) === 'urgente').length} urgentes
                </span>
              )}
            </h4>
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
        )}
      </div>
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
                    {formatNivel(ficha.nivel_academico, ficha.calificaciones, ficha.calificaciones_historicas) || "—"}
                  </div>
                </div>
              </div>

              {/* Tabla de cursos AVAC activos — semestre actual (primera mano) */}
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
                        const totalCurso = ts.find(t => t.total_curso != null)?.total_curso ?? null;
                        const nota = notaTableau ?? totalCurso;
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
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500 whitespace-nowrap">
                              {(() => {
                                const nivNum = parseNivelNum(matchedCal?.nivel);
                                const grp = abbreviateGrupo(matchedCal?.grupo || acceso?.grupo || ts[0]?.grupo);
                                const nivFallback = !nivNum && ficha.nivel_academico > 0 && ficha.nivel_academico <= 12 ? ficha.nivel_academico : null;
                                const niv = nivNum || nivFallback;
                                if (niv && grp) return <>{niv}° Nivel | {grp}</>;
                                if (niv) return <>{niv}° Nivel</>;
                                if (grp) return grp;
                                return <span className="text-gray-300">—</span>;
                              })()}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 font-medium text-gray-800">
                              {toTitleCase(courseName)}
                            </td>
                            <td className={`px-2 py-1 border border-gray-200 text-center font-bold ${noteStyle.bg} ${noteStyle.text}`}>
                              {nota != null ? nota : <span className="text-gray-300">—</span>}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500">
                              {matchedCal?.numero_repitencias != null
                                ? <span className={`px-1 rounded text-[10px] font-semibold ${matchedCal.numero_repitencias > 1 ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-700"}`}>
                                    {matchedCal.numero_repitencias}
                                  </span>
                                : "—"}
                            </td>
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
                            <td className="px-2 py-1 border border-gray-200 text-center">
                              <a href={`https://avac.ups.edu.ec/grado67/course/search.php?search=${codigo}`}
                                 target="_blank" rel="noreferrer"
                                 className="text-blue-500 hover:text-blue-700 font-mono text-[11px]">
                                {codigo}
                              </a>
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-gray-600 text-[11px]">
                              {toTitleCase(acceso?.docente || ts[0]?.docente || matchedCal?.docente)
                                || <span className="text-gray-300 italic">—</span>}
                            </td>
                          </tr>
                        );
                      })}
                      {/* Materias con calificación pero sin actividad AVAC */}
                      {ficha.calificaciones?.filter(cal => {
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
                                const nivFallback = !nivNum && ficha.nivel_academico > 0 && ficha.nivel_academico <= 12 ? ficha.nivel_academico : null;
                                const niv = nivNum || nivFallback;
                                if (niv && grp) return <>{niv}° Nivel | {grp}</>;
                                if (niv) return <>{niv}° Nivel</>;
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

              {/* Tabla de materias — fallback cuando no hay cursos AVAC pero sí calificaciones */}
              {Object.keys(cursos).length === 0 && ficha.calificaciones?.length > 0 && (() => {
                const calsByNivel = {};
                ficha.calificaciones.forEach(cal => {
                  const niv = parseNivelNum(cal.nivel) || parseNivelNum(ficha.nivel_academico) || 0;
                  if (!calsByNivel[niv]) calsByNivel[niv] = [];
                  calsByNivel[niv].push(cal);
                });
                const niveles = Object.keys(calsByNivel).sort((a, b) => a - b);
                const totalMaterias = ficha.calificaciones.length;
                const conNota = ficha.calificaciones.filter(c => c.nota_final != null);
                const promedio = conNota.length > 0 ? conNota.reduce((s, c) => s + c.nota_final, 0) / conNota.length : null;

                return (
                  <div>
                    <div className="flex items-center gap-4 px-3 py-1.5 bg-gray-50 border-b border-gray-200" style={{ fontSize: "10px" }}>
                      <span className="text-gray-500">{totalMaterias} materias matriculadas</span>
                      {promedio != null && (
                        <>
                          <span className="text-gray-300">|</span>
                          <span className="text-gray-500">
                            Promedio{" "}
                            <strong className={promedio >= 70 ? "text-emerald-700" : promedio >= 60 ? "text-amber-600" : "text-red-600"}>
                              {promedio.toFixed(1)}
                            </strong>
                          </span>
                        </>
                      )}
                      <span className="ml-auto px-2 py-0.5 rounded bg-amber-50 text-amber-600 font-medium" style={{ fontSize: "9px" }}>
                        Sin datos AVAC
                      </span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse" style={{ fontSize: "11px" }}>
                        <thead>
                          <tr style={{ background: "linear-gradient(to right, #1e3a5f, #2d5a8e)", color: "white" }}>
                            <th className="text-center px-2 py-1.5 font-semibold whitespace-nowrap" style={{ fontSize: "10px", width: "90px" }}>Nivel</th>
                            <th className="text-left px-2 py-1.5 font-semibold" style={{ fontSize: "10px" }}>Asignatura</th>
                            <th className="text-center px-2 py-1.5 font-semibold" style={{ fontSize: "10px", width: "55px" }}>Nota</th>
                            <th className="text-center px-2 py-1.5 font-semibold" style={{ fontSize: "10px", width: "40px" }}>Mat</th>
                            <th className="text-left px-2 py-1.5 font-semibold" style={{ fontSize: "10px" }}>Docente</th>
                          </tr>
                        </thead>
                        <tbody>
                          {niveles.map(niv => {
                            const cals = calsByNivel[niv];
                            return cals.map((cal, idx) => {
                              const noteStyle = getNoteStyleHistorico(cal.nota_final);
                              const grp = abbreviateGrupo(cal.grupo);
                              const nivNum = parseNivelNum(cal.nivel) || parseNivelNum(ficha.nivel_academico);
                              return (
                                <tr key={`${niv}-${idx}`}
                                    className={idx % 2 === 0 ? "bg-white" : "bg-[#f8fafc]"}
                                    style={{ borderBottom: "1px solid #e5e7eb" }}>
                                  {idx === 0 ? (
                                    <td rowSpan={cals.length}
                                        className="px-2 py-1 text-center align-top font-semibold"
                                        style={{ fontSize: "10px", color: "#1e3a5f", borderRight: "2px solid #e5e7eb", background: "#f1f5f9" }}>
                                      {nivNum ? `${nivNum}° Nivel` : "—"}
                                      {grp && <div className="font-normal text-gray-400" style={{ fontSize: "9px" }}>{grp}</div>}
                                    </td>
                                  ) : null}
                                  <td className="px-2 py-1 font-medium text-gray-800">{toTitleCase(cal.asignatura)}</td>
                                  <td className={`px-2 py-1 text-center font-bold ${noteStyle.bg} ${noteStyle.text}`}
                                      style={{ borderRadius: "3px" }}>
                                    {cal.nota_final ?? <span className="text-gray-300 font-normal">—</span>}
                                  </td>
                                  <td className="px-2 py-1 text-center text-gray-500" style={{ fontSize: "10px" }}>
                                    {cal.numero_repitencias != null ? (
                                      <span className={`px-1 rounded ${cal.numero_repitencias > 1 ? "bg-orange-100 text-orange-700 font-semibold" : ""}`}>
                                        {cal.numero_repitencias}
                                      </span>
                                    ) : "—"}
                                  </td>
                                  <td className="px-2 py-1 text-gray-600" style={{ fontSize: "10px" }}>
                                    {toTitleCase(cal.docente) || <span className="text-gray-300">—</span>}
                                  </td>
                                </tr>
                              );
                            });
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })()}

              {/* ═══ KPIs AVAC ═══ */}
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

              {/* ══ MALLA CURRICULAR FIJA (grid por niveles canónicos) ══ */}
              {ficha.malla_curricular?.semestres?.length > 0 && (() => {
                const malla = ficha.malla_curricular;
                return (
                  <div className="border-t border-gray-200">
                    <SectionHeader>
                      Malla curricular — {malla.total_semestres} niveles · {malla.total_asignaturas_malla} asignaturas
                      <span className="text-gray-400 font-normal ml-2 text-[9px] normal-case tracking-normal">
                        {malla.total_aprobadas} aprobadas · {malla.total_cursando} cursando · {malla.total_reprobadas} reprobadas · {malla.total_no_cursado} pendientes
                      </span>
                    </SectionHeader>
                    {/* Leyenda compacta arriba del grid */}
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 px-3 py-1.5 bg-[#FAFAFA]" style={{ fontSize: "9px", color: "#6b7280" }}>
                      <span className="flex items-center gap-1">
                        <span className="inline-block w-2 h-2 rounded-sm bg-green-100 border border-green-300"></span>Aprobada
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="inline-block w-2 h-2 rounded-sm bg-amber-100 border border-amber-400"></span>Cursando
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="inline-block w-2 h-2 rounded-sm bg-yellow-100 border border-yellow-300"></span>En proceso
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="inline-block w-2 h-2 rounded-sm bg-red-100 border border-red-300"></span>Reprobada
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="inline-block w-2 h-2 rounded-sm bg-gray-100 border border-gray-200"></span>No cursada
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="inline-block w-2 h-2 rounded-sm bg-white border border-gray-200" style={{ borderLeftWidth: "2px", borderLeftColor: "#f97316" }}></span>Repetición
                      </span>
                    </div>
                    {/* Grid de niveles con años que abarcan 2 columnas */}
                    <div className="bg-[#FAFAFA] px-1.5 pb-2">
                      {/* Fila de años — cada año abarca 2 niveles */}
                      <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${malla.total_semestres}, minmax(0, 1fr))` }}>
                        {(() => {
                          const yearCells = [];
                          const totalSem = malla.total_semestres;
                          for (let i = 0; i < totalSem; i += 2) {
                            const yearNum = Math.floor(i / 2) + 1;
                            const YEAR_NAMES = { 1: "Primer Año", 2: "Segundo Año", 3: "Tercer Año", 4: "Cuarto Año", 5: "Quinto Año" };
                            const label = YEAR_NAMES[yearNum] || `${yearNum}° Año`;
                            const span = (i + 1 < totalSem) ? 2 : 1;
                            yearCells.push(
                              <div key={`year-${i}`}
                                   className="bg-[#0F2A4A] text-white text-center font-bold uppercase tracking-wider rounded-t"
                                   style={{ fontSize: "8px", padding: "3px 2px", gridColumn: `span ${span}` }}>
                                {label}
                              </div>
                            );
                          }
                          return yearCells;
                        })()}
                      </div>
                      {/* Fila de encabezados de nivel — todos alineados */}
                      <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${malla.total_semestres}, minmax(0, 1fr))`, marginTop: "-1px" }}>
                        {malla.semestres.map((sem) => (
                          <div key={`hdr-${sem.numero}`}
                               className="bg-[#1B3A6B] text-white text-center font-bold uppercase tracking-wider"
                               style={{ fontSize: "11px", padding: "4px 2px" }}>
                            {sem.numero}°
                          </div>
                        ))}
                      </div>
                      {/* Filas de contenido — asignaturas */}
                      <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${malla.total_semestres}, minmax(0, 1fr))`, marginTop: "-1px" }}>
                        {malla.semestres.map((sem) => {
                          const promedioStyle = getNoteStyleHistorico(sem.promedio != null ? Math.round(sem.promedio) : null);
                          return (
                            <div key={`col-${sem.numero}`} className="border border-t-0 border-gray-200 rounded-b bg-white flex flex-col gap-0.5 min-w-0" style={{ padding: "4px" }}>
                              {sem.asignaturas.length > 0 ? (
                                sem.asignaturas.map((asig, ai) => (
                                  <MallaCeldaFija key={ai} asignatura={asig} />
                                ))
                              ) : (
                                <div className="text-gray-300 text-center py-2 italic" style={{ fontSize: "9px" }}>Sin datos</div>
                              )}
                              {/* Promedio del nivel */}
                              <div className={`text-center font-bold border-t border-gray-100 ${promedioStyle.text}`}
                                   style={{ fontSize: "10px", paddingTop: "3px", marginTop: "3px" }}>
                                x&#772; {sem.promedio != null ? sem.promedio.toFixed(1) : "—"}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Fallback: si no hay malla canónica pero hay calificaciones, mostrar vista legacy */}
              {(!ficha.malla_curricular?.semestres?.length) && (ficha.calificaciones_historicas?.length > 0 || ficha.calificaciones?.length > 0) && (() => {
                const allGrades = [...(ficha.calificaciones_historicas || []), ...(ficha.calificaciones || [])];
                const porPeriodo = {};
                allGrades.forEach(c => {
                  const p = c.periodo || "Actual";
                  if (!porPeriodo[p]) porPeriodo[p] = [];
                  porPeriodo[p].push(c);
                });
                const periodos = Object.keys(porPeriodo).sort();
                return (
                  <div className="border-t border-gray-200">
                    <SectionHeader>Malla curricular (vista simplificada)</SectionHeader>
                    <div className="overflow-x-auto bg-[#FAFAFA] px-2 py-2">
                      <div className="flex gap-2" style={{ minWidth: "max-content" }}>
                        {periodos.map(periodo => {
                          const asigs = porPeriodo[periodo];
                          const promedio = asigs.reduce((s, c) => s + (c.nota_final ?? 0), 0) / asigs.length;
                          const promedioStyle = getNoteStyleHistorico(Math.round(promedio));
                          const isActual = periodo === "Actual";
                          return (
                            <div key={periodo} className="flex-shrink-0 flex flex-col" style={{ minWidth: "80px" }}>
                              <div className={`${isActual ? "bg-[#F0B000]" : "bg-[#1B3A6B]"} text-white text-center rounded-t px-1 py-0.5 text-[9px] font-bold uppercase tracking-wider`}>
                                {periodo}
                              </div>
                              <div className="border border-t-0 border-gray-200 rounded-b bg-white px-1 pt-1 pb-0.5 flex flex-col gap-0.5">
                                {asigs.map((c, i) => (
                                  <MallaChip key={i} asignatura={c.asignatura} nota_final={c.nota_final} docente={c.docente} />
                                ))}
                                <div className={`mt-0.5 text-center text-[9px] font-bold border-t border-gray-100 pt-0.5 ${promedioStyle.text}`}>
                                  x&#772; {isNaN(promedio) ? "—" : promedio.toFixed(1)}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Tendencia Académica */}
              <TrendChart calificacionesHistoricas={ficha.calificaciones_historicas} calificaciones={ficha.calificaciones} />

              {/* Estado vacío: solo si no hay absolutamente nada (ni cursos, ni calificaciones, ni historial, ni malla) */}
              {Object.keys(cursos).length === 0
                && !ficha.calificaciones?.length
                && !ficha.calificaciones_historicas?.length
                && !ficha.malla_curricular?.semestres?.length && (
                <div className="flex-1 flex items-center justify-center py-8 text-center text-gray-300">
                  <div>
                    <div className="text-2xl mb-1">📚</div>
                    <div className="text-[11px]">Sin actividad académica registrada</div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ═══ ANÁLISIS COMPARATIVO ═══ */}
          <div className="border-t border-gray-300">
            <div className="bg-[#1B3A6B] text-white px-4 py-1 text-[10px] font-bold uppercase tracking-wider">
              Análisis Comparativo — vs. Compañeros de Carrera
            </div>
            <div className="bg-white">
              {loadingComparativa ? (
                <div className="py-4 text-center text-[11px] text-gray-400">Cargando análisis comparativo...</div>
              ) : comparativa?.asignaturas?.length > 0 ? (
                <div>
                  {/* Resumen general */}
                  <div className="px-4 py-2 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-[11px]">
                    <div>
                      <span className="text-gray-500">Promedio estudiante:</span>{" "}
                      <strong className={comparativa.promedio_estudiante >= 70 ? "text-green-700" : comparativa.promedio_estudiante >= 60 ? "text-yellow-700" : "text-red-700"}>
                        {comparativa.promedio_estudiante ?? "—"}
                      </strong>
                    </div>
                    <div>
                      <span className="text-gray-500">Promedio carrera:</span>{" "}
                      <strong className="text-gray-700">{comparativa.promedio_carrera ?? "—"}</strong>
                    </div>
                    {comparativa.percentil_general != null && (
                      <div>
                        <span className="text-gray-500">Percentil general:</span>{" "}
                        <strong className={comparativa.percentil_general >= 70 ? "text-green-700" : comparativa.percentil_general >= 40 ? "text-yellow-700" : "text-red-700"}>
                          {comparativa.percentil_general}%
                        </strong>
                        <span className="text-gray-400 ml-1">
                          (supera al {comparativa.percentil_general?.toFixed(0)}% de compañeros)
                        </span>
                      </div>
                    )}
                  </div>
                  {/* Tabla por asignatura */}
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="border-b border-gray-200 bg-gray-50/50">
                        <th className="text-left px-3 py-1.5 font-semibold text-gray-600">Asignatura</th>
                        <th className="text-center px-2 py-1.5 font-semibold text-gray-600">Nota</th>
                        <th className="text-center px-2 py-1.5 font-semibold text-gray-600">Prom. Grupo</th>
                        <th className="text-center px-2 py-1.5 font-semibold text-gray-600">Mín</th>
                        <th className="text-center px-2 py-1.5 font-semibold text-gray-600">Máx</th>
                        <th className="text-center px-2 py-1.5 font-semibold text-gray-600">Posición</th>
                        <th className="px-2 py-1.5 font-semibold text-gray-600 w-24">Comparación</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparativa.asignaturas.map((a, idx) => {
                        const diff = a.nota_estudiante != null && a.promedio_grupo != null ? a.nota_estudiante - a.promedio_grupo : null;
                        const barWidth = a.percentil != null ? Math.max(a.percentil, 3) : 0;
                        return (
                          <tr key={idx} className="border-b border-gray-50 hover:bg-blue-50/30">
                            <td className="px-3 py-1.5 text-gray-800">{a.asignatura}</td>
                            <td className="px-2 py-1.5 text-center">
                              <span className={`font-bold font-mono ${
                                a.nota_estudiante >= 70 ? "text-green-700" : a.nota_estudiante >= 60 ? "text-yellow-700" : "text-red-700"
                              }`}>{a.nota_estudiante ?? "—"}</span>
                            </td>
                            <td className="px-2 py-1.5 text-center font-mono text-gray-600">{a.promedio_grupo ?? "—"}</td>
                            <td className="px-2 py-1.5 text-center font-mono text-gray-400">{a.nota_minima ?? "—"}</td>
                            <td className="px-2 py-1.5 text-center font-mono text-gray-400">{a.nota_maxima ?? "—"}</td>
                            <td className="px-2 py-1.5 text-center">
                              {a.posicion != null && a.total_estudiantes > 0 && (
                                <span className={`font-semibold ${a.posicion <= 3 ? "text-green-700" : a.posicion <= Math.ceil(a.total_estudiantes / 2) ? "text-gray-700" : "text-red-600"}`}>
                                  {a.posicion}/{a.total_estudiantes}
                                </span>
                              )}
                            </td>
                            <td className="px-2 py-1.5">
                              <div className="flex items-center gap-1">
                                <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${barWidth >= 70 ? "bg-green-500" : barWidth >= 40 ? "bg-yellow-400" : "bg-red-400"}`}
                                    style={{ width: `${barWidth}%` }}
                                  />
                                </div>
                                {diff != null && (
                                  <span className={`text-[10px] font-bold whitespace-nowrap ${diff > 0 ? "text-green-600" : diff < 0 ? "text-red-600" : "text-gray-500"}`}>
                                    {diff > 0 ? "+" : ""}{diff.toFixed(1)}
                                  </span>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-4 text-center text-[11px] text-gray-400 italic">
                  Sin datos comparativos disponibles para este semestre
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
