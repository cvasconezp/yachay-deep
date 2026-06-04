/**
 * StatCard — tarjeta de estadística reutilizable.
 *
 * Variante "preset" (Dashboard/Asignaturas/Docentes/Tutorias):
 *   <StatCard label="Total" value={42} color="blue" />
 *
 * Variante "custom" (Intervenciones/ResumenDatos):
 *   <StatCard label="Total" value={42} className="text-brand" sub="detalle" />
 */

const PRESETS = {
  blue:   "bg-blue-50 text-blue-700 border-blue-200",
  red:    "bg-red-50 text-red-700 border-red-200",
  yellow: "bg-yellow-50 text-yellow-700 border-yellow-200",
  green:  "bg-green-50 text-green-700 border-green-200",
};

export function StatCard({ label, value, color, className, sub }) {
  // Preset mode: color is a key like "blue", "red", etc.
  if (color && PRESETS[color]) {
    return (
      <div className={`rounded-xl border p-4 ${PRESETS[color]}`}>
        <div className="text-3xl font-bold">{value}</div>
        <div className="text-xs font-medium mt-1 opacity-80">{label}</div>
      </div>
    );
  }

  // Custom mode: className for value color, optional sub text
  return (
    <div className="bg-white rounded-xl border border-gray-200 px-5 py-4 shadow-sm">
      <div className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${className || color || "text-brand"}`}>{value}</div>
      {sub && <div className="text-[11px] text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

/** Alias for backward compatibility: SummaryCard === StatCard (preset mode) */
export const SummaryCard = StatCard;
