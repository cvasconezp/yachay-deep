import { useState, useEffect, useRef, Component } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";
import { PeriodSelector } from "../components/PeriodSelector";
import EcuadorMap from "../components/EcuadorMap";
import InterventionForm from "./InterventionForm";

// Componentes extraídos (Épica 1.5)
import {
  SectionHeader, PersonalRow, TaskCell, RecoveryScoreCard,
  GradeChip, MallaChip, MallaCeldaFija,
  getNoteStyle, getDiagnosticoStyle, getRiesgoStyle, getCompromisoLabel,
  parseLocalDate, calcAge, ordinalNivel, compactarAcceso,
  toTitleCase, abbreviateGrupo, formatNivel, parseNivelNum,
  getNoteStyleHistorico, getMallaEstado, abreviarAsignatura,
} from "../components/ficha";
// ── ErrorBoundary: captura crashes de render y permite recargar ──────────────
class FichaErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error("FichaEstudiante crash:", error, info?.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="max-w-2xl mx-auto mt-16 bg-white rounded-2xl shadow-lg p-8 text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <h2 className="text-lg font-bold text-gray-800 mb-2">Algo salió mal</h2>
          <p className="text-sm text-gray-500 mb-4">
            Ocurrió un error al mostrar la ficha del estudiante.
          </p>
          <pre className="text-xs text-red-600 bg-red-50 rounded p-3 mb-4 text-left overflow-auto max-h-32">
            {String(this.state.error?.message || this.state.error)}
          </pre>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg text-sm font-medium transition"
          >
            Recargar página
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/** Trend chart component: BI-style sparkline + KPIs — full-width, compact height */
function TrendChart({ calificacionesHistoricas, calificaciones }) {
  const chartRef = useRef(null);
  const [chartW, setChartW] = useState(600);
  const [hoveredIdx, setHoveredIdx] = useState(null);

  // Responsive width — hook DEBE estar antes de cualquier early return
  useEffect(() => {
    if (!chartRef.current) return;
    const ro = new ResizeObserver(entries => {
      for (const e of entries) setChartW(e.contentRect.width);
    });
    ro.observe(chartRef.current);
    return () => ro.disconnect();
  }, []);

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

// ── Prácticas Preprofesionales ────────────────────────────────────────────────
/** Componente colapsable que muestra las prácticas preprofesionales del estudiante.
 *  Solo se expande por defecto si hay prácticas asignadas. Diseño basado en tabla
 *  Excel con encabezados naranja/azul similar a la ficha original.
 */
function PracticasSection({ practicas }) {
  const hasPracticas = practicas.length > 0;
  const [expanded, setExpanded] = useState(hasPracticas);

  // Actualizar estado si cambia el estudiante (prácticas cambian)
  useEffect(() => {
    setExpanded(practicas.length > 0);
  }, [practicas]);

  return (
    <div className="border-t border-gray-300">
      {/* Header clickable para expandir/colapsar */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full bg-[#1B3A6B] text-white px-4 py-1 text-[10px] font-bold uppercase tracking-wider flex items-center justify-between hover:bg-[#24477a] transition-colors"
      >
        <span>
          Prácticas Preprofesionales
          {hasPracticas && <span className="ml-2 opacity-60">({practicas.length})</span>}
        </span>
        <span className="flex items-center gap-1 normal-case">
          <svg xmlns="http://www.w3.org/2000/svg" className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
          <span className="text-[9px] opacity-70 font-medium">{expanded ? "Minimizar" : "Expandir"}</span>
        </span>
      </button>

      {expanded && (
        <div className="bg-white">
          {!hasPracticas ? (
            <div className="py-4 text-center text-[11px] text-gray-300 italic">
              Sin prácticas preprofesionales asignadas en este período
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {practicas.map((p, idx) => (
                <div key={p.id || idx} className="px-0">
                  {/* Título de la práctica — barra naranja */}
                  <div className="bg-[#F0B000] px-3 py-1 flex items-center justify-between">
                    <span className="text-[11px] font-bold text-[#1B3A6B] uppercase tracking-wide">
                      {p.nombre_practica || p.nivel_y_practica || "Práctica Preprofesional"}
                    </span>
                    {p.periodo && (
                      <span className="text-[10px] font-semibold text-[#1B3A6B]/60">{p.periodo}</span>
                    )}
                  </div>

                  {/* Tabla de datos tipo Excel */}
                  <table className="w-full border-collapse">
                    <tbody>
                      {/* Nombre de la práctica */}
                      <tr>
                        <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#D6E4F0] whitespace-nowrap w-36">
                          Nombre práctica
                        </td>
                        <td className="text-[11px] px-2 py-0.5 border border-gray-200 text-gray-800 font-medium" colSpan={3}>
                          {p.nombre_practica || <span className="text-gray-300 italic">—</span>}
                        </td>
                      </tr>

                      {/* IE Práctica */}
                      <tr>
                        <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#D6E4F0] whitespace-nowrap">
                          IE Práctica
                        </td>
                        <td className="text-[11px] px-2 py-0.5 border border-gray-200 text-gray-800 font-medium" colSpan={3}>
                          {p.nombre_escuela || <span className="text-gray-300 italic">—</span>}
                        </td>
                      </tr>

                      {/* Ubicación IE */}
                      <tr>
                        <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#D6E4F0] whitespace-nowrap">
                          Ubicación IE
                        </td>
                        <td className="text-[11px] px-2 py-0.5 border border-gray-200 text-gray-700" colSpan={3}>
                          {p.ubicacion_escuela || <span className="text-gray-300 italic">—</span>}
                        </td>
                      </tr>

                      {/* Distrito y AMIE */}
                      <tr>
                        <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#D6E4F0] whitespace-nowrap">
                          Distrito y AMIE
                        </td>
                        <td className="text-[11px] px-2 py-0.5 border border-gray-200 text-gray-700" colSpan={3}>
                          {p.distrito || ""}
                          {p.distrito && p.amie_escuela ? " | " : ""}
                          {p.amie_escuela ? <span>AMIE: <strong className="font-mono">{p.amie_escuela}</strong></span> : ""}
                          {!p.distrito && !p.amie_escuela && <span className="text-gray-300 italic">—</span>}
                        </td>
                      </tr>

                      {/* Jurisdicción */}
                      <tr>
                        <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#D6E4F0] whitespace-nowrap">
                          Jurisdicción
                        </td>
                        <td className="text-[11px] px-2 py-0.5 border border-gray-200" colSpan={3}>
                          {p.jurisdiccion ? (
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                              p.jurisdiccion?.toLowerCase().includes("bilingüe") || p.jurisdiccion?.toLowerCase().includes("bilingue")
                                ? "bg-amber-100 text-amber-800"
                                : "bg-blue-100 text-blue-700"
                            }`}>
                              {p.jurisdiccion}
                            </span>
                          ) : <span className="text-gray-300 italic">—</span>}
                        </td>
                      </tr>

                      {/* Autoridad */}
                      <tr className="bg-[#FFF8E7]">
                        <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#D6E4F0] whitespace-nowrap">
                          Nombre autoridad
                        </td>
                        <td className="text-[11px] px-2 py-0.5 border border-gray-200 text-gray-800 font-medium">
                          {p.nombre_autoridad || <span className="text-gray-300 italic">—</span>}
                        </td>
                        <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#D6E4F0] whitespace-nowrap w-20">
                          Celular
                        </td>
                        <td className="text-[11px] px-2 py-0.5 border border-gray-200 text-gray-700 font-mono">
                          {p.telefono_autoridad || <span className="text-gray-300 italic">—</span>}
                        </td>
                      </tr>

                      {/* Cargo */}
                      <tr>
                        <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#D6E4F0] whitespace-nowrap">
                          Cargo
                        </td>
                        <td className="text-[11px] px-2 py-0.5 border border-gray-200 text-gray-700">
                          {p.cargo_autoridad || <span className="text-gray-300 italic">—</span>}
                        </td>
                        <td className="text-right text-[10px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#D6E4F0] whitespace-nowrap">
                          Mineduc
                        </td>
                        <td className="text-[11px] px-2 py-0.5 border border-gray-200">
                          {p.en_mineduc ? (
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                              p.en_mineduc.toLowerCase() === "sí" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
                            }`}>
                              {p.en_mineduc}
                            </span>
                          ) : <span className="text-gray-300 italic">—</span>}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ── Componente principal ───────────────────────────────────────────────────────
function FichaEstudianteInner() {
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [comparativa, setComparativa] = useState(null);
  const [loadingComparativa, setLoadingComparativa] = useState(false);
  const [mlPeriodos, setMlPeriodos] = useState(null);  // periodos dinámicos del modelo ML
  const [iaPanelExpanded, setIaPanelExpanded] = useState(true);  // expand/collapse del panel IA
  const [selectedPeriodo, setSelectedPeriodo] = useState("");   // periodo seleccionado (PeriodSelector default)
  const searchTimeout = useRef(null);
  const searchAbort = useRef(null);
  const searchContainerRef = useRef(null);
  const searchInputRef = useRef(null);

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
        setRecomendaciones(Array.isArray(data) ? data : (data?.recommendations || data?.recomendaciones || []));
      } catch (err) {
        console.error('Error cargando recomendaciones:', err);
      }
    };
    loadPrediction();
    loadRecomendaciones();
    // Cargar contrafactuales
    api.getCounterfactual(studentId).then(setContrafactual).catch(() => {});
    // Cargar periodos del modelo ML (para label dinámico)
    api.getPredictionStatus().then(s => {
      if (s?.metadata?.periodos?.length) {
        const p = s.metadata.periodos;
        setMlPeriodos(`${p[0]}-${p[p.length - 1]}`);
      }
    }).catch(() => {});
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

  // Clear the search input quickly so the user can search for someone else.
  const handleClearSearch = () => {
    if (searchAbort.current) searchAbort.current.abort();
    clearTimeout(searchTimeout.current);
    setQuery("");
    setSearchResults([]);
    // Refocus the input so the user can type immediately.
    searchInputRef.current?.focus();
  };

  const handleCarreraChange = (carrera) => {
    setSelectedCarrera(carrera);
    triggerSearch(query, carrera);
  };

  const loadFicha = async (id, periodo) => {
    setLoading(true);
    setError(null);
    setSearchResults([]);
    setActiveTab("indicadores");
    try {
      const data = await api.getFicha(id, periodo || selectedPeriodo || undefined);
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

  // Recargar ficha cuando cambia el periodo seleccionado
  const handlePeriodoChange = (newPeriodo) => {
    setSelectedPeriodo(newPeriodo);
    if (ficha?.id) {
      loadFicha(ficha.id, newPeriodo);
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

  // Derivar la base URL de AVAC desde el periodo consultado (grado67, grado68, etc.)
  const gradoNum = (() => {
    const p = ficha?.periodo_consulta || selectedPeriodo || "";
    const m = p.match(/\d+/);
    return m ? m[0] : "68"; // fallback a 68
  })();
  const avacBaseUrl = `https://avac.ups.edu.ec/grado${gradoNum}/course/search.php`;

  // Construir mapa de cursos AVAC (todos, sin filtrar — se cruzan luego por enrollment)
  const cursosAvac = {};
  if (ficha) {
    (ficha.accesos_avac || []).forEach(a => {
      if (!cursosAvac[a.codigo_curso]) cursosAvac[a.codigo_curso] = { acceso: null, tareas: [] };
      cursosAvac[a.codigo_curso].acceso = a;
    });
    (ficha.tareas || []).forEach(t => {
      if (!cursosAvac[t.codigo_curso]) cursosAvac[t.codigo_curso] = { acceso: null, tareas: [] };
      cursosAvac[t.codigo_curso].tareas.push(t);
    });
  }

  // Deduplicar enrollments del reporte (preferir grupo principal sobre PRÁCTICA)
  const enrollmentsUniq = (() => {
    if (!ficha?.enrollments?.length) return [];
    const seen = {};
    const result = [];
    ficha.enrollments.forEach(enr => {
      const key = (enr.asignatura || "").toUpperCase().replace(/_x[0-9a-fA-F]{4}_/g, " ").replace(/\s+/g, " ").trim();
      const isPrac = (enr.nombre_grupo || "").toUpperCase().includes("PRÁCTICA") || (enr.nombre_grupo || "").toUpperCase().includes("PRACTICA");
      if (!seen[key]) { seen[key] = { enr, isPrac }; result.push(enr); }
      else if (seen[key].isPrac && !isPrac) {
        const i = result.indexOf(seen[key].enr);
        if (i >= 0) result[i] = enr;
        seen[key] = { enr, isPrac };
      }
    });
    return result;
  })();

  // Cursos legacy (para fallback si no hay enrollments)
  const cursos = cursosAvac;

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
      <div className="mb-4 flex items-center gap-3">
        {ficha && window.history.length > 1 && (
          <button
            onClick={() => window.history.back()}
            className="p-2 rounded-lg border border-gray-300 hover:bg-gray-100 text-gray-600 transition-colors"
            title="Volver"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          </button>
        )}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Ficha del Estudiante</h1>
          <p className="text-gray-400 text-sm">Monitoreo académico individual</p>
        </div>
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
            ref={searchInputRef}
            type="text"
            value={query}
            onChange={e => handleSearch(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Escape" && query.length > 0) {
                e.preventDefault();
                handleClearSearch();
              }
            }}
            placeholder="🔍 Buscar por nombre, correo o cédula..."
            className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 pr-10 bg-white shadow-sm"
          />
          {/* Loading takes priority; otherwise show clear (×) button when query has text. */}
          {loading ? (
            <span className="absolute right-3 top-3.5 text-gray-400 text-sm">⏳</span>
          ) : query.length > 0 ? (
            <button
              type="button"
              onClick={handleClearSearch}
              aria-label="Limpiar búsqueda"
              title="Limpiar (Esc)"
              className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <span className="text-lg leading-none">×</span>
            </button>
          ) : null}
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
                <div className="[&>div>label]:hidden">
                  <PeriodSelector
                    value={selectedPeriodo}
                    onChange={handlePeriodoChange}
                    className="!min-w-[120px] !py-1 !text-xs !bg-white/10 !text-white !border-white/20 !shadow-none !rounded-md [&>option]:text-gray-900"
                  />
                </div>
                {!ficha.periodo_es_actual && (
                  <span className="bg-amber-500/20 text-amber-200 text-[10px] px-2 py-0.5 rounded-full font-medium">
                    Histórico
                  </span>
                )}
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

          {/* ═══ INDICADORES — COMPACTO SINGLE-LINE ═══ */}
          <div className="bg-white border-b border-gray-200">
            <div className="flex items-center justify-between px-4 py-1 bg-gray-50/80 border-b border-gray-100">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Indicadores · Predicción IA</span>
              <span className="text-[9px] text-gray-400">
                Modelo ML{mlPeriodos ? ` · ${mlPeriodos}` : ""}
                {ficha.prediccion_updated_at && (
                  <> · {new Date(ficha.prediccion_updated_at).toLocaleDateString("es-EC")}</>
                )}
              </span>
            </div>
            <div className="grid grid-cols-3 divide-x divide-gray-100">
              {/* Compromiso — single line */}
              <div className="px-4 py-1.5 cursor-help flex items-center gap-2" title="Índice de compromiso: acceso AVAC (30%), tareas (30%), rendimiento (25%), matrícula (15%)">
                <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider whitespace-nowrap">Compromiso</span>
                <span className={`text-lg font-bold leading-none ${compromisoColor}`}>{compromisoStr || "—"}</span>
                <span className={`text-[10px] font-semibold ${compromisoColor}`}>{compromisoLabel}</span>
                {ficha.indice_compromiso != null && (
                  <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden min-w-[40px]">
                    <div className={`h-full rounded-full transition-all duration-500 ${
                      ficha.indice_compromiso >= 0.7 ? "bg-green-500" : ficha.indice_compromiso >= 0.4 ? "bg-yellow-400" : "bg-red-500"
                    }`} style={{ width: `${Math.round(ficha.indice_compromiso * 100)}%` }} />
                  </div>
                )}
              </div>
              {/* Predicción Deserción — single line */}
              {(() => {
                const pctDes = ficha.prob_desercion != null ? Math.round(ficha.prob_desercion * 100) : null;
                const colorDes = pctDes == null ? "text-gray-300" : pctDes >= 70 ? "text-red-600" : pctDes >= 40 ? "text-orange-600" : "text-green-600";
                const barDes = pctDes >= 70 ? "bg-red-500" : pctDes >= 40 ? "bg-orange-400" : "bg-green-500";
                const labelDes = pctDes == null ? "—" : pctDes >= 70 ? "Alto" : pctDes >= 40 ? "Moderado" : "Bajo";
                return (
                  <div className="px-4 py-1.5 cursor-help flex items-center gap-2" title="Probabilidad de deserción predicha por modelo ML">
                    <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider whitespace-nowrap">Deserción</span>
                    <span className={`text-lg font-bold leading-none ${colorDes}`}>{pctDes != null ? `${pctDes}%` : "—"}</span>
                    <span className={`text-[10px] font-semibold ${colorDes}`}>{labelDes}</span>
                    {pctDes != null && (
                      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden min-w-[40px]">
                        <div className={`h-full rounded-full transition-all duration-500 ${barDes}`} style={{ width: `${pctDes}%` }} />
                      </div>
                    )}
                  </div>
                );
              })()}
              {/* Predicción Reprobación — single line */}
              {(() => {
                const pctRep = ficha.prob_reprobacion != null ? Math.round(ficha.prob_reprobacion * 100) : null;
                const colorRep = pctRep == null ? "text-gray-300" : pctRep >= 70 ? "text-red-600" : pctRep >= 40 ? "text-orange-600" : "text-green-600";
                const barRep = pctRep >= 70 ? "bg-red-500" : pctRep >= 40 ? "bg-orange-400" : "bg-green-500";
                const labelRep = pctRep == null ? "—" : pctRep >= 70 ? "Alto" : pctRep >= 40 ? "Moderado" : "Bajo";
                return (
                  <div className="px-4 py-1.5 cursor-help flex items-center gap-2" title="Probabilidad de reprobar al menos una materia">
                    <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider whitespace-nowrap">Reprobación</span>
                    <span className={`text-lg font-bold leading-none ${colorRep}`}>{pctRep != null ? `${pctRep}%` : "—"}</span>
                    <span className={`text-[10px] font-semibold ${colorRep}`}>{labelRep}</span>
                    {pctRep != null && (
                      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden min-w-[40px]">
                        <div className={`h-full rounded-full transition-all duration-500 ${barRep}`} style={{ width: `${pctRep}%` }} />
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          </div>

          {/* ===== PANEL IA: Collapsible Tabbed Navigation ===== */}
{(prediccion?.xai || prediccion?.contexto_conductual?.length > 0 || contrafactual?.contrafactual_desercion?.cambios?.length > 0 || contrafactual?.contrafactual_conductual?.escenarios?.length > 0 || recomendaciones.length > 0) && (
<div className="border-t border-gray-200 bg-[#FAFBFF]">
  {/* Tab headers — with collapse toggle */}
  <div className="flex border-b border-gray-200 bg-white">
    <button
      onClick={() => setIaPanelExpanded(!iaPanelExpanded)}
      className="px-2.5 py-2 text-[#1B3A6B] bg-blue-50 hover:bg-blue-100 transition-colors border-r border-gray-200 flex items-center gap-1"
      title={iaPanelExpanded ? "Minimizar panel IA" : "Expandir panel IA"}
    >
      <svg xmlns="http://www.w3.org/2000/svg" className={`w-3.5 h-3.5 transition-transform ${iaPanelExpanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    </button>
    <button
      onClick={() => { setActiveTab("indicadores"); setIaPanelExpanded(true); }}
      className={`flex-1 px-4 py-2 text-[11px] font-bold uppercase tracking-wide transition-colors ${
        activeTab === "indicadores" && iaPanelExpanded
          ? "text-[#1B3A6B] border-b-2 border-[#1B3A6B] bg-blue-50/50"
          : "text-gray-400 hover:text-gray-600 hover:bg-gray-50"
      }`}
    >
      📊 Indicadores · Predicción IA
    </button>
    {prediccion?.contexto_conductual?.length > 0 && (
      <button
        onClick={() => { setActiveTab("alertas"); setIaPanelExpanded(true); }}
        className={`flex-1 px-4 py-2 text-[11px] font-bold uppercase tracking-wide transition-colors ${
          activeTab === "alertas" && iaPanelExpanded
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
        onClick={() => { setActiveTab("acciones"); setIaPanelExpanded(true); }}
        className={`flex-1 px-4 py-2 text-[11px] font-bold uppercase tracking-wide transition-colors ${
          activeTab === "acciones" && iaPanelExpanded
            ? "text-[#1B3A6B] border-b-2 border-[#1B3A6B] bg-blue-50/50"
            : "text-gray-400 hover:text-gray-600 hover:bg-gray-50"
        }`}
      >
        🎯 ¿Qué puede hacer el estudiante?
      </button>
    )}
  </div>

  {/* Tab content — collapsible */}
  {iaPanelExpanded && <div className="p-4">
    {/* ── Tab: Indicadores · Predicción IA ── */}
    {activeTab === "indicadores" && (
      <div className="space-y-3">
        {prediccion?.xai && (() => {
          const FactorCard = ({ f, i, tipo, colorUp, colorBar }) => {
            const sube = f.direccion === 'incrementa';
            const pct = Math.min(100, Math.round(Math.abs(f.contribucion || 0) * 100));
            return (
              <div key={i} className="group relative cursor-help">
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="font-medium text-gray-700">{f.label || f.feature}</span>
                  <span className={sube ? colorUp : 'text-emerald-500'}>{sube ? '↑ aumenta riesgo' : '↓ reduce riesgo'}</span>
                </div>
                <p className="text-xs text-gray-400 mb-1">Valor: {typeof f.valor === 'number' ? f.valor.toFixed(2) : f.valor} · Media: {typeof f.media_carrera === 'number' ? f.media_carrera.toFixed(2) : f.media_carrera}</p>
                <div className="h-1.5 bg-gray-100 rounded-full">
                  <div className={'h-1.5 rounded-full ' + (sube ? colorBar : 'bg-emerald-400')} style={{ width: pct + '%' }} />
                </div>
                <div className="invisible group-hover:visible absolute z-20 left-0 right-0 top-full mt-1 bg-gray-900 text-white text-[11px] leading-relaxed rounded-lg px-3 py-2 shadow-lg">
                  {f.explicacion || `${f.label || f.feature}: valor ${f.valor} (media: ${f.media_carrera})`}
                </div>
              </div>
            );
          };
          return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {prediccion.xai.desercion?.length > 0 && (
            <div className="bg-white rounded-xl border border-red-100 shadow-sm p-4">
              <p className="text-xs font-bold text-red-700 mb-3 uppercase">Factores · Deserción</p>
              <p className="text-[10px] text-gray-400 -mt-2 mb-3">Pasa el cursor sobre cada factor para ver la explicación</p>
              <div className="space-y-3">
                {prediccion.xai.desercion.slice(0, 3).map((f, i) => (
                  <FactorCard key={i} f={f} i={i} tipo="desercion" colorUp="text-red-500" colorBar="bg-red-400" />
                ))}
              </div>
            </div>
            )}
            {prediccion.xai.reprobacion?.length > 0 && (
            <div className="bg-white rounded-xl border border-orange-100 shadow-sm p-4">
              <p className="text-xs font-bold text-orange-700 mb-3 uppercase">Factores · Reprobación</p>
              <p className="text-[10px] text-gray-400 -mt-2 mb-3">Pasa el cursor sobre cada factor para ver la explicación</p>
              <div className="space-y-3">
                {prediccion.xai.reprobacion.slice(0, 3).map((f, i) => (
                  <FactorCard key={i} f={f} i={i} tipo="reprobacion" colorUp="text-orange-500" colorBar="bg-orange-400" />
                ))}
              </div>
            </div>
            )}
          </div>
          );
        })()}
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
  </div>}
</div>
)}

          {/* ═══ CUERPO PRINCIPAL: 2 columnas ═══ */}
          <div className="flex divide-x divide-gray-200 bg-white">

            {/* ─── COLUMNA IZQUIERDA (colapsable) ─── */}
            <div
              className="flex-shrink-0 bg-white transition-all duration-300 overflow-hidden relative"
              style={{ width: sidebarCollapsed ? "28px" : "300px" }}
            >
              {/* Collapsed state: vertical tab with label */}
              {sidebarCollapsed && (
                <button
                  onClick={() => setSidebarCollapsed(false)}
                  className="absolute inset-0 w-full h-full flex flex-col items-center justify-center gap-2 bg-gradient-to-b from-[#1B3A6B] to-[#24477a] hover:from-[#24477a] hover:to-[#2d5594] text-white cursor-pointer transition-all"
                  title="Expandir datos del estudiante"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                  <span className="text-[9px] font-semibold tracking-widest uppercase" style={{ writingMode: "vertical-lr" }}>Datos del estudiante</span>
                </button>
              )}

              {!sidebarCollapsed && (<>

              {/* Header con botón de minimizar integrado */}
              <button
                onClick={() => setSidebarCollapsed(true)}
                className="w-full flex items-center justify-between px-3 py-1.5 bg-[#1B3A6B] text-white hover:bg-[#24477a] transition-colors"
                title="Minimizar datos del estudiante"
              >
                <span className="text-[10px] font-bold uppercase tracking-wider">Datos del estudiante</span>
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                </svg>
              </button>

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

              {/* Estado socioeconómico */}
              <SectionHeader>Estado socioeconómico</SectionHeader>
              <table className="w-full border-collapse">
                <tbody>
                  <PersonalRow label="Nivel de beca" value={ficha.nivel_beca} />
                  {/* Pago matrícula: Ya pagó / Aún no paga */}
                  <tr className={ficha.estado_matricula === "Matriculado" ? "bg-green-50" : ficha.estado_matricula ? "bg-red-50" : ""}>
                    <td className="text-right text-[11px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#F2F2F2] whitespace-nowrap w-28">Pago matrícula</td>
                    <td className={`text-[11px] px-2 py-0.5 border border-gray-200 font-semibold ${
                      ficha.estado_matricula === "Matriculado" ? "text-green-700" : ficha.estado_matricula ? "text-red-600" : "text-gray-300 italic"
                    }`}>
                      {ficha.estado_matricula === "Matriculado" ? "Ya pagó la matrícula"
                        : ficha.estado_matricula ? "Aún no paga"
                        : "—"}
                    </td>
                  </tr>
                  {/* Pago colegiatura: valor total + deuda */}
                  <tr>
                    <td className="text-right text-[11px] text-gray-500 font-semibold px-2 py-0.5 border border-gray-200 bg-[#F2F2F2] whitespace-nowrap w-28">Pago colegiatura</td>
                    <td className="text-[11px] px-2 py-0.5 border border-gray-200">
                      {ficha.pago_colegiatura_total != null ? (
                        <span>
                          <span className="font-semibold text-gray-800">${ficha.pago_colegiatura_total}</span>
                          {ficha.deuda_cuotas > 0 && (
                            <span className="ml-1.5 text-red-600 font-medium">(deuda {ficha.deuda_cuotas} cuotas)</span>
                          )}
                        </span>
                      ) : <span className="text-gray-300 italic">—</span>}
                    </td>
                  </tr>
                  <PersonalRow label="Empleabilidad" value={ficha.empleabilidad} />
                  <PersonalRow label="Madre o padre de familia" value={ficha.es_padre_madre != null ? (ficha.es_padre_madre ? "Sí" : "No") : null} />
                </tbody>
              </table>

              </>)}
            </div>

            {/* ─── SECCIÓN DERECHA ─── */}
            <div className="flex-1 overflow-hidden flex flex-col">

              {/* Aviso de período histórico */}
              {!ficha.periodo_es_actual && (
                <div className="bg-amber-50 border-b border-amber-200 px-3 py-1.5 flex items-center gap-2">
                  <span className="text-amber-600 text-[10px]">Viendo datos del período <strong>{ficha.periodo_consulta}</strong></span>
                </div>
              )}

              {/* Barra de info: Datos Académicos | Centro de Apoyo (EIB) | Nivel */}
              <div className="bg-[#1B3A6B] text-white px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider flex items-center gap-4">
                <span>Datos académicos</span>
                {isEIB && (
                  <span className="font-normal text-[9px] text-white/60 normal-case tracking-normal">
                    Centro de apoyo: <strong className="text-white font-semibold">{sedeDisplay}</strong>
                  </span>
                )}
                <span className="font-normal text-[9px] text-white/60 normal-case tracking-normal">
                  Nivel: <strong className="text-white font-semibold">{formatNivel(ficha.nivel_academico, ficha.calificaciones, ficha.calificaciones_historicas) || "—"}</strong>
                </span>
                <span className="ml-auto">
                  <button
                    onClick={() => navigate("/entregas")}
                    className="text-[9px] text-white/70 hover:text-white normal-case tracking-normal font-normal underline"
                  >
                    Ver entregas pendientes
                  </button>
                </span>
              </div>

              {/* ═══ TABLA DE DATOS ACADÉMICOS — basada en enrollments del reporte ═══ */}
              {enrollmentsUniq.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-xs">
                    <thead>
                      <tr className="bg-[#BDD7EE]">
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 whitespace-nowrap text-[10px]">Nivel y grupo</th>
                        <th className="text-left px-2 py-1 border border-gray-300 font-semibold text-gray-700 text-[10px]" style={{ minWidth: "180px" }}>Asignaturas matriculadas</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-14 text-[10px]">Nota</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-10 text-[10px]">Mat</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-12 text-[10px]">Bloque</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-16 text-[10px]">AVAC</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-28 text-[10px]">Actividades</th>
                        <th className="text-center px-2 py-1 border border-gray-300 font-semibold text-gray-700 w-14 text-[10px]">Link</th>
                        <th className="text-left px-2 py-1 border border-gray-300 font-semibold text-gray-700 text-[10px]">Docente</th>
                      </tr>
                    </thead>
                    <tbody>
                      {enrollmentsUniq.map((enr, idx) => {
                        const codigo = String(enr.codigo_grupo || "").trim();
                        const avac = cursosAvac[codigo] || null;
                        const acceso = avac?.acceso;
                        const ts = avac?.tareas || [];
                        const matchedCal = matchNota(enr.asignatura, ficha.calificaciones);
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
                        const grp = abbreviateGrupo(enr.nombre_grupo);

                        return (
                          <tr key={`enr-${idx}`} className={idx % 2 === 0 ? "bg-white" : "bg-[#F9F9F9]"}>
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500 whitespace-nowrap">
                              {enr.nivel ? <>{enr.nivel}° Nivel</> : "—"}
                              {grp ? <> | {grp}</> : ""}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 font-medium text-gray-800">
                              {toTitleCase(enr.asignatura)}
                            </td>
                            <td className={`px-2 py-1 border border-gray-200 text-center font-bold ${noteStyle.bg} ${noteStyle.text}`}>
                              {nota != null ? nota : <span className="text-amber-600 font-semibold text-[10px]">Cursando</span>}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500">
                              {(enr.numero_repitencias ?? matchedCal?.numero_repitencias) != null
                                ? <span className={`px-1 rounded text-[10px] font-semibold ${(enr.numero_repitencias ?? matchedCal?.numero_repitencias) > 1 ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-700"}`}>
                                    {enr.numero_repitencias ?? matchedCal?.numero_repitencias}
                                  </span>
                                : "—"}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px]">
                              {enr.bloque != null
                                ? <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${enr.bloque === 1 ? "bg-blue-100 text-blue-700" : "bg-purple-100 text-purple-700"}`}>
                                    B{enr.bloque}
                                  </span>
                                : <span className="text-gray-300">—</span>}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-center">
                              {acceso ? (
                                <>
                                  <span className={`font-mono text-[11px] ${diasColor}`}>
                                    {diasInt != null ? `${diasInt}d` : "—"}
                                  </span>
                                  {acceso.ultimo_acceso_texto && (
                                    <div className="text-[10px] text-gray-400 leading-tight whitespace-nowrap">
                                      {compactarAcceso(acceso.ultimo_acceso_texto)}
                                    </div>
                                  )}
                                </>
                              ) : (
                                <span className="text-[10px] text-gray-300 italic">Sin AVAC</span>
                              )}
                            </td>
                            <td className="px-2 py-1 border border-gray-200">
                              {sortedTasks.length > 0 ? (
                                <div className="flex gap-0.5 justify-center flex-wrap">
                                  {sortedTasks.slice(0, 8).map((t, i) => (
                                    <TaskCell key={i} entregada={t.entregada} calificada={t.calificada} retrasada={t.retrasada}
                                      title={`Unidad ${t.unidad}: ${t.entregada ? (t.calificada ? "Entregada ✓" : "Entregada (sin calificar)") : t.retrasada ? "Retrasada" : "Pendiente"}`} />
                                  ))}
                                  {sortedTasks.length > 8 && <span className="text-[10px] text-gray-400 self-center">+{sortedTasks.length - 8}</span>}
                                </div>
                              ) : (
                                <span className="text-[10px] text-gray-300 italic">—</span>
                              )}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-center">
                              {codigo ? (
                                <a href={`${avacBaseUrl}?areaids=core_course-course&q=${codigo}`}
                                   target="_blank" rel="noreferrer"
                                   className="text-blue-500 hover:text-blue-700 font-mono text-[11px]">
                                  {codigo}
                                </a>
                              ) : <span className="text-gray-300">—</span>}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 text-gray-600 text-[11px]">
                              {toTitleCase(enr.docente || acceso?.docente || matchedCal?.docente)
                                || <span className="text-gray-300 italic">—</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* ═══ FALLBACK: Tabla AVAC cuando NO hay enrollments ═══ */}
              {enrollmentsUniq.length === 0 && Object.keys(cursos).length > 0 && (
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
                      {/* Filas de cursos con datos AVAC */}
                      {Object.entries(cursos).map(([codigo, { acceso, tareas: ts }], idx) => {
                        const courseName = acceso?.nombre_curso || ts[0]?.nombre_curso || codigo;
                        const matchedCal = matchNota(courseName, ficha.calificaciones)
                          || matchNota(courseName, ficha.calificaciones_historicas);
                        const nota = matchedCal?.nota_final ?? ts.find(t => t.total_curso != null)?.total_curso ?? null;
                        const noteStyle = getNoteStyleHistorico(nota);
                        const sortedTasks = [...ts].sort((a, b) => String(a.unidad).localeCompare(String(b.unidad), undefined, { numeric: true }));
                        const diasInt = acceso?.dias_sin_acceso != null ? Math.round(acceso.dias_sin_acceso) : null;
                        const diasColor = diasInt == null ? "text-gray-300" : diasInt > 14 ? "text-red-600 font-bold" : diasInt > 7 ? "text-orange-500" : "text-green-600";
                        return (
                          <tr key={codigo} className={idx % 2 === 0 ? "bg-white" : "bg-[#F9F9F9]"}>
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500 whitespace-nowrap">
                              {(() => { const niv = parseNivelNum(matchedCal?.nivel) || (ficha.nivel_academico > 0 ? ficha.nivel_academico : null); const grp = abbreviateGrupo(matchedCal?.grupo || acceso?.grupo); return niv ? <>{niv}° Nivel{grp ? <> | {grp}</> : ""}</> : grp || <span className="text-gray-300">—</span>; })()}
                            </td>
                            <td className="px-2 py-1 border border-gray-200 font-medium text-gray-800">{toTitleCase(courseName)}</td>
                            <td className={`px-2 py-1 border border-gray-200 text-center font-bold ${noteStyle.bg} ${noteStyle.text}`}>{nota != null ? nota : <span className="text-gray-300">—</span>}</td>
                            <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500">{matchedCal?.numero_repitencias != null ? <span className={`px-1 rounded text-[10px] font-semibold ${matchedCal.numero_repitencias > 1 ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-700"}`}>{matchedCal.numero_repitencias}</span> : "—"}</td>
                            <td className="px-2 py-1 border border-gray-200 text-center"><span className={`font-mono text-[11px] ${diasColor}`}>{diasInt != null ? `${diasInt}d` : "—"}</span>{acceso?.ultimo_acceso_texto && <div className="text-[10px] text-gray-400 leading-tight whitespace-nowrap">{compactarAcceso(acceso.ultimo_acceso_texto)}</div>}</td>
                            <td className="px-2 py-1 border border-gray-200"><div className="flex gap-0.5 justify-center flex-wrap">{sortedTasks.slice(0, 8).map((t, i) => <TaskCell key={i} entregada={t.entregada} calificada={t.calificada} retrasada={t.retrasada} title={`Unidad ${t.unidad}: ${t.entregada ? (t.calificada ? "Entregada ✓" : "Entregada (sin calificar)") : t.retrasada ? "Retrasada" : "Pendiente"}`} />)}{sortedTasks.length > 8 && <span className="text-[10px] text-gray-400 self-center">+{sortedTasks.length - 8}</span>}{sortedTasks.length === 0 && <span className="text-[10px] text-gray-300 italic">Sin tareas</span>}</div></td>
                            <td className="px-2 py-1 border border-gray-200 text-center"><a href={`${avacBaseUrl}?areaids=core_course-course&q=${codigo}`} target="_blank" rel="noreferrer" className="text-blue-500 hover:text-blue-700 font-mono text-[11px]">{codigo}</a></td>
                            <td className="px-2 py-1 border border-gray-200 text-gray-600 text-[11px]">{toTitleCase(acceso?.docente || ts[0]?.docente || matchedCal?.docente) || <span className="text-gray-300 italic">—</span>}</td>
                          </tr>
                        );
                      })}
                      {/* Filas de calificaciones SIN match AVAC (materias que no aparecen en cursos AVAC) */}
                      {(() => {
                        const avacCourseNames = Object.entries(cursos).map(([codigo, { acceso, tareas: ts }]) => {
                          const name = acceso?.nombre_curso || ts[0]?.nombre_curso || codigo;
                          return name;
                        });
                        const norm = s => (s || "").toLowerCase().replace(/[^a-záéíóúñ0-9]/gi, "").slice(0, 12);
                        const avacNorms = avacCourseNames.map(n => norm(n));
                        const unmatchedCals = (ficha.calificaciones || []).filter(cal => {
                          const cn = norm(cal.asignatura);
                          return !avacNorms.some(an => an && cn && (an.startsWith(cn.slice(0, 8)) || cn.startsWith(an.slice(0, 8))));
                        });
                        const baseIdx = Object.keys(cursos).length;
                        return unmatchedCals.map((cal, idx) => {
                          const noteStyle = getNoteStyleHistorico(cal.nota_final);
                          const grp = abbreviateGrupo(cal.grupo);
                          const nivNum = parseNivelNum(cal.nivel) || parseNivelNum(ficha.nivel_academico);
                          return (
                            <tr key={`cal-extra-${idx}`} className={(baseIdx + idx) % 2 === 0 ? "bg-white" : "bg-[#F9F9F9]"}>
                              <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500 whitespace-nowrap">
                                {nivNum ? <>{nivNum}° Nivel</> : "—"}{grp ? <> | {grp}</> : ""}
                              </td>
                              <td className="px-2 py-1 border border-gray-200 font-medium text-gray-800">{toTitleCase(cal.asignatura)}</td>
                              <td className={`px-2 py-1 border border-gray-200 text-center font-bold ${noteStyle.bg} ${noteStyle.text}`}>
                                {cal.nota_final != null ? cal.nota_final : <span className="text-gray-300 font-normal">—</span>}
                              </td>
                              <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500">
                                {cal.numero_repitencias != null
                                  ? <span className={`px-1 rounded text-[10px] font-semibold ${cal.numero_repitencias > 1 ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-700"}`}>{cal.numero_repitencias}</span>
                                  : "—"}
                              </td>
                              <td className="px-2 py-1 border border-gray-200 text-center"><span className="text-[10px] text-gray-300 italic">—</span></td>
                              <td className="px-2 py-1 border border-gray-200 text-center"><span className="text-[10px] text-gray-300 italic">—</span></td>
                              <td className="px-2 py-1 border border-gray-200 text-center"><span className="text-gray-300">—</span></td>
                              <td className="px-2 py-1 border border-gray-200 text-gray-600 text-[11px]">{toTitleCase(cal.docente) || <span className="text-gray-300 italic">—</span>}</td>
                            </tr>
                          );
                        });
                      })()}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Tabla de materias — fallback cuando no hay cursos AVAC, ni enrollments, pero sí calificaciones */}
              {Object.keys(cursos).length === 0 && !ficha.enrollments?.length && ficha.calificaciones?.length > 0 && (() => {
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
                    </div>
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
                            const grp = abbreviateGrupo(cal.grupo);
                            const nivNum = parseNivelNum(cal.nivel) || parseNivelNum(ficha.nivel_academico);
                            return (
                              <tr key={`cal-${idx}`} className={idx % 2 === 0 ? "bg-white" : "bg-[#F9F9F9]"}>
                                <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500 whitespace-nowrap">
                                  {nivNum ? <>{nivNum}° Nivel</> : "—"}
                                  {grp ? <> | {grp}</> : ""}
                                </td>
                                <td className="px-2 py-1 border border-gray-200 font-medium text-gray-800">
                                  {toTitleCase(cal.asignatura)}
                                </td>
                                <td className={`px-2 py-1 border border-gray-200 text-center font-bold ${noteStyle.bg} ${noteStyle.text}`}>
                                  {cal.nota_final != null ? cal.nota_final : <span className="text-gray-300 font-normal">—</span>}
                                </td>
                                <td className="px-2 py-1 border border-gray-200 text-center text-[11px] text-gray-500">
                                  {cal.numero_repitencias != null
                                    ? <span className={`px-1 rounded text-[10px] font-semibold ${cal.numero_repitencias > 1 ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-700"}`}>
                                        {cal.numero_repitencias}
                                      </span>
                                    : "—"}
                                </td>
                                <td className="px-2 py-1 border border-gray-200 text-center">
                                  <span className="text-[10px] text-gray-300 italic">—</span>
                                </td>
                                <td className="px-2 py-1 border border-gray-200 text-center">
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
                  </div>
                );
              })()}

              {/* ═══ KPIs AVAC — compact single-line ═══ */}
              <div className="grid grid-cols-2 divide-x divide-gray-200 border-t border-gray-200 bg-gradient-to-r from-gray-50 to-white">
                <div className="px-4 py-1.5 flex items-center gap-2">
                  <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider whitespace-nowrap">Días sin AVAC</span>
                  <span className={`text-lg font-bold leading-none ${
                    ficha.dias_sin_acceso == null ? "text-gray-300"
                    : ficha.dias_sin_acceso > 14 ? "text-red-600"
                    : ficha.dias_sin_acceso > 7 ? "text-orange-500"
                    : "text-green-600"}`}>
                    {ficha.dias_sin_acceso != null ? `${Math.round(ficha.dias_sin_acceso)}d` : "—"}
                  </span>
                </div>
                <div className="px-4 py-1.5 flex items-center gap-2">
                  <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider whitespace-nowrap">Tareas entregadas</span>
                  <span className={`text-lg font-bold leading-none ${
                    ficha.porcentaje_tareas == null ? "text-gray-300"
                    : ficha.porcentaje_tareas < 50 ? "text-red-600"
                    : ficha.porcentaje_tareas < 75 ? "text-orange-500"
                    : "text-green-600"}`}>
                    {ficha.porcentaje_tareas != null ? `${Math.round(ficha.porcentaje_tareas)}%` : "—"}
                  </span>
                </div>
              </div>

              {/* ══ SCORE DE RECUPERABILIDAD (Épica 1.4) ══ */}
              <RecoveryScoreCard studentId={ficha.id} />

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

              {/* Estado vacío: solo si no hay absolutamente nada (ni cursos, ni enrollments, ni calificaciones, ni historial, ni malla) */}
              {Object.keys(cursos).length === 0
                && !ficha.enrollments?.length
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

          {/* ═══ PRÁCTICAS PREPROFESIONALES ═══ */}
          <PracticasSection practicas={ficha.practicas_preprofesionales || []} />

          {/* ═══ SEGUIMIENTO E INTERVENCIONES ═══ */}

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
            Yachay Deep © &nbsp;·&nbsp; {today}
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

// Wrapper con ErrorBoundary para capturar crashes de render
export default function FichaEstudiante() {
  return (
    <FichaErrorBoundary>
      <FichaEstudianteInner />
    </FichaErrorBoundary>
  );
}
