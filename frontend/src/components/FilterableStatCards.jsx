/**
 * Tarjetas de resumen con filtrado dinámico.
 * Al hacer click en una tarjeta, se activa un filtro.
 * Incluye botón para limpiar filtros.
 *
 * Props:
 *   cards: array de { key, label, value, color, filterFn? }
 *   activeFilter: key de la tarjeta activa (o null)
 *   onFilterChange: (key) => void — llamado al click
 */
export default function FilterableStatCards({ cards = [], activeFilter = null, onFilterChange }) {
  return (
    <div className="flex flex-wrap gap-3 mb-4">
      {cards.map(card => {
        const isActive = activeFilter === card.key;
        const baseClasses = "rounded-xl border px-4 py-3 cursor-pointer transition-all duration-200 min-w-[140px] flex-1";
        const activeClasses = isActive
          ? "ring-2 ring-blue-500 border-blue-300 bg-blue-50 shadow-md scale-[1.02]"
          : "border-gray-200 bg-white hover:shadow-sm hover:border-gray-300";

        return (
          <div
            key={card.key}
            className={`${baseClasses} ${activeClasses}`}
            onClick={() => onFilterChange(isActive ? null : card.key)}
            title={isActive ? "Click para quitar filtro" : `Click para filtrar por ${card.label}`}
          >
            <div className={`text-2xl font-bold ${card.color || "text-gray-900"}`}>
              {card.value}
            </div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mt-0.5">
              {card.label}
            </div>
            {isActive && (
              <div className="text-[9px] text-blue-600 font-medium mt-1">✓ Filtro activo</div>
            )}
          </div>
        );
      })}

      {/* Botón limpiar filtros */}
      {activeFilter && (
        <button
          onClick={() => onFilterChange(null)}
          className="flex items-center gap-1 self-center px-3 py-1.5 rounded-lg text-xs text-gray-500 hover:text-red-600 hover:bg-red-50 border border-gray-200 transition-colors"
        >
          ✕ Limpiar filtro
        </button>
      )}
    </div>
  );
}
