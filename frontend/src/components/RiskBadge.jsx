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
