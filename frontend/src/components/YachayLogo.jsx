/**
 * Yachay Deep brand logo — SVG iceberg with sun.
 * Faithful reproduction of the official brand image.
 */

/** Shared SVG paths for the iceberg logo */
function IcebergSVG({ size }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 200 220"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="flex-shrink-0"
    >
      {/* Sun — top-left of peak */}
      <circle cx="72" cy="28" r="18" fill="#E8A838" />

      {/* Ice peak — main triangle with secondary ridge */}
      <polygon points="62,100 105,48 148,100" fill="#A8DCE8" />
      <polygon points="62,100 85,60 78,100" fill="#D8EFF4" />

      {/* Waterline — thin dark line */}
      <rect x="38" y="98" width="124" height="4" rx="2" fill="#1B3A6B" opacity="0.25" />

      {/* Deep body — shield/pentagon shape narrowing to point */}
      <path
        d="M38,102 L162,102 L162,140 Q162,148 156,156 L112,210 Q105,218 100,218 Q95,218 88,210 L44,156 Q38,148 38,140 Z"
        fill="#1B3A6B"
      />

      {/* Subtle horizontal line on deep body */}
      <line x1="56" y1="132" x2="144" y2="132" stroke="#0F2444" strokeWidth="2.5" opacity="0.2" />
    </svg>
  );
}

export function YachayLogo({ size = 48, className = "", showText = false }) {
  return (
    <div className={`inline-flex items-center gap-3 ${className}`}>
      <IcebergSVG size={size} />
      {showText && (
        <div className="flex flex-col">
          <span className="text-xl font-bold tracking-tight text-white leading-tight">
            Yachay Deep
          </span>
          <span className="text-xs text-brand-ice opacity-80 leading-tight">
            Monitoreo Académico
          </span>
        </div>
      )}
    </div>
  );
}

/** Compact icon-only version for collapsed sidebar & favicon */
export function YachayIcon({ size = 32, className = "" }) {
  return <IcebergSVG size={size} />;
}
