/**
 * Yachay Deep brand logo — SVG iceberg with sun.
 * Based on the official brand image.
 */
export function YachayLogo({ size = 48, className = "", showText = false }) {
  return (
    <div className={`inline-flex items-center gap-3 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 200 200"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="flex-shrink-0"
      >
        {/* Sun */}
        <circle cx="100" cy="32" r="20" fill="#E8A838" />

        {/* Iceberg top (ice) */}
        <polygon points="60,90 100,50 140,90" fill="#A8DCE8" />
        <polygon points="50,90 80,65 70,90" fill="#D8EFF4" />

        {/* Waterline */}
        <rect x="45" y="88" width="110" height="6" rx="3" fill="#1B3A6B" opacity="0.3" />

        {/* Iceberg bottom (deep) */}
        <polygon points="40,94 160,94 130,180 70,180" fill="#1B3A6B" />

        {/* Subtle depth line on iceberg bottom */}
        <line x1="60" y1="120" x2="140" y2="120" stroke="#0F2444" strokeWidth="2" opacity="0.3" />
      </svg>

      {showText && (
        <div className="flex flex-col">
          <span className="text-xl font-bold tracking-tight text-white leading-tight">
            Yachay Deep
          </span>
          <span className="text-xs text-brand-ice opacity-80 leading-tight">
            Monitoreo Academico
          </span>
        </div>
      )}
    </div>
  );
}

/** Compact icon-only version for collapsed sidebar & favicon */
export function YachayIcon({ size = 32, className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <circle cx="100" cy="32" r="20" fill="#E8A838" />
      <polygon points="60,90 100,50 140,90" fill="#A8DCE8" />
      <polygon points="50,90 80,65 70,90" fill="#D8EFF4" />
      <rect x="45" y="88" width="110" height="6" rx="3" fill="#1B3A6B" opacity="0.3" />
      <polygon points="40,94 160,94 130,180 70,180" fill="#1B3A6B" />
      <line x1="60" y1="120" x2="140" y2="120" stroke="#0F2444" strokeWidth="2" opacity="0.3" />
    </svg>
  );
}
