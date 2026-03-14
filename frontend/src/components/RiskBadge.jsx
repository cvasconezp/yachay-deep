const RISK_CONFIG = {
  Alto:  { bg: "bg-red-100",    text: "text-red-700",    dot: "bg-red-500",    label: "Alto" },
  Medio: { bg: "bg-yellow-100", text: "text-yellow-700", dot: "bg-yellow-500", label: "Medio" },
  Bajo:  { bg: "bg-green-100",  text: "text-green-700",  dot: "bg-green-500",  label: "Bajo" },
};

export function RiskBadge({ nivel, showDot = true, size = "sm" }) {
  const config = RISK_CONFIG[nivel] || { bg: "bg-gray-100", text: "text-gray-600", dot: "bg-gray-400", label: nivel || "—" };
  const padding = size === "lg" ? "px-3 py-1.5 text-sm" : "px-2 py-0.5 text-xs";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${config.bg} ${config.text} ${padding}`}>
      {showDot && <span className={`w-2 h-2 rounded-full ${config.dot}`} />}
      {config.label}
    </span>
  );
}

export function PredictionBadge({ value, label }) {
  if (value == null) return <span className="text-gray-400 text-xs">--</span>;
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "text-red-700 bg-red-100"
    : pct >= 40 ? "text-orange-700 bg-orange-100"
    : "text-green-700 bg-green-100";
  const riskText = pct >= 70 ? "Alto" : pct >= 40 ? "Moderado" : "Bajo";
  const tooltipText = label === "Desercion"
    ? `${riskText} riesgo de deserción (${pct}%). Modelo ML basado en: promedio, nota mínima, dispersión de notas y materias reprobadas. Comparado contra patrones históricos P60-P67.`
    : `${label}: ${pct}%`;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${color}`}
      title={tooltipText}>
      {pct}%
    </span>
  );
}

export function PredictionBar({ value, label, tooltip }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const barColor = pct >= 70 ? "bg-red-500" : pct >= 40 ? "bg-orange-400" : "bg-green-500";
  const textColor = pct >= 70 ? "text-red-700" : pct >= 40 ? "text-orange-700" : "text-green-700";
  return (
    <div className="group relative flex items-center gap-2 cursor-help">
      <span className="text-xs text-gray-600 w-24 text-right">{label}</span>
      <div className="flex-1 bg-gray-200 rounded-full h-2.5">
        <div className={`h-2.5 rounded-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-bold w-10 ${textColor}`}>{pct}%</span>
      {tooltip && (
        <div className="absolute left-0 bottom-full mb-2 w-72 bg-gray-900 text-white text-[10px] leading-relaxed rounded-lg px-3 py-2 shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
          {tooltip}
          <div className="absolute left-6 top-full w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-gray-900" />
        </div>
      )}
    </div>
  );
}

export function CompromisoBar({ valor }) {
  if (valor == null) return <span className="text-gray-400 text-xs">—</span>;
  const pct = Math.round(valor * 100);
  const color = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-400" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-gray-600 w-8">{pct}%</span>
    </div>
  );
}
