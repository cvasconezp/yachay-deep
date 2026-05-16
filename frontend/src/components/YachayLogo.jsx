/**
 * Yachay Deep brand marks — 2026 brand system.
 *
 * Three assets live in /frontend/public/:
 *   - yachay-favicon.svg       isotype only (iceberg + sun), 1:1 — used as favicon
 *                              and inside <YachayIcon />
 *   - yachay-logo-light.svg    full horizontal lockup designed FOR a LIGHT bg
 *                              (wordmark "Deep" rendered in dark blue)
 *   - yachay-logo-dark.svg     full horizontal lockup designed FOR a DARK bg
 *                              (wordmark "Deep" rendered in white)
 *
 *   Header viewBox is 840x445 (aspect ≈ 1.888 : 1). `size` is interpreted as
 *   the rendered HEIGHT and the width is computed automatically.
 */

const HEADER_ASPECT = 840 / 445;

const HEADER_SRC = {
  light: "/yachay-logo-light.svg",
  dark:  "/yachay-logo-dark.svg",
};

const ICON_SRC = "/yachay-favicon.svg";

/**
 * Full horizontal Yachay Deep logo (iceberg + wordmark).
 * The wordmark "Yachay Deep" is built into the SVG — do NOT render it
 * again next to this component.
 *
 * Props:
 *   variant: "light" (default) — for use on light backgrounds (dark text)
 *            "dark"            — for use on dark  backgrounds (white text)
 *   size:    rendered height in px (default 48)
 */
export function YachayLogo({ variant = "light", size = 48, className = "" }) {
  const src = HEADER_SRC[variant] ?? HEADER_SRC.light;
  const width = Math.round(size * HEADER_ASPECT);
  return (
    <img
      src={src}
      alt="Yachay Deep"
      width={width}
      height={size}
      className={`flex-shrink-0 select-none ${className}`}
      draggable={false}
    />
  );
}

/**
 * Compact icon-only version (the isotype / favicon — iceberg + sun, no text).
 * Use this in narrow places (e.g. collapsed sidebar) or as a visual accent
 * next to a separate page heading.
 */
export function YachayIcon({ size = 32, className = "" }) {
  return (
    <img
      src={ICON_SRC}
      alt="Yachay Deep"
      width={size}
      height={size}
      className={`flex-shrink-0 select-none ${className}`}
      draggable={false}
    />
  );
}
