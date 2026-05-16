/**
 * Yachay Deep brand logo — official iceberg + sun (2026 brand).
 * The SVG file lives in `frontend/public/yachay-logo.svg` so it can be
 * referenced both by this component and by <link rel="icon"> in index.html.
 */

const LOGO_SRC = "/yachay-logo.svg";

export function YachayLogo({ size = 48, className = "", showText = false }) {
  return (
    <div className={`inline-flex items-center gap-3 ${className}`}>
      <img
        src={LOGO_SRC}
        alt="Yachay Deep"
        width={size}
        height={size}
        className="flex-shrink-0 select-none"
        draggable={false}
      />
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

/** Compact icon-only version for collapsed sidebar & favicon previews */
export function YachayIcon({ size = 32, className = "" }) {
  return (
    <img
      src={LOGO_SRC}
      alt="Yachay Deep"
      width={size}
      height={size}
      className={`flex-shrink-0 select-none ${className}`}
      draggable={false}
    />
  );
}
