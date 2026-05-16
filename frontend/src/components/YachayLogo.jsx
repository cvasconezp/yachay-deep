/**
 * Yachay Deep brand marks — 2026 brand system.
 *
 * Three assets live in /frontend/public/:
 *   - yachay-favicon.svg       isotype only (iceberg + sun), 1:1 — also used
 *                              as favicon (favicon.svg / favicon.ico / PNGs).
 *   - yachay-logo-light.svg    full horizontal lockup designed FOR a LIGHT bg
 *                              (wordmark "Deep" rendered in dark blue #1B3A6B).
 *   - yachay-logo-dark.svg     full horizontal lockup designed FOR a DARK bg
 *                              (wordmark "Deep" rendered in white).
 *
 *   Header viewBox is 840x445 (aspect ≈ 1.888 : 1).
 *
 * Sizing:
 *   - `size` (px): treated as rendered HEIGHT; width is computed via aspect
 *     ratio. Use for fixed-size placements.
 *   - `className`: pass Tailwind responsive utilities (e.g. "w-full h-auto",
 *     "h-16 sm:h-20 lg:h-24") for fluid sizing. When `size` is omitted, no
 *     pixel width/height attributes are emitted so CSS controls the box.
 */

const HEADER_ASPECT = 840 / 445;

const HEADER_SRC = {
  light: "/yachay-logo-light.svg",
  dark:  "/yachay-logo-dark.svg",
};

const ICON_SRC = "/yachay-favicon.svg";

/**
 * Full horizontal Yachay Deep logo (iceberg + wordmark).
 * The "Yachay Deep" wordmark is built into the SVG — do NOT render it
 * again next to this component.
 */
export function YachayLogo({ variant = "light", size, className = "" }) {
  const src = HEADER_SRC[variant] ?? HEADER_SRC.light;
  const dimensions = size != null
    ? { width: Math.round(size * HEADER_ASPECT), height: size }
    : {};
  return (
    <img
      src={src}
      alt="Yachay Deep"
      {...dimensions}
      className={`select-none ${className}`}
      draggable={false}
    />
  );
}

/**
 * Compact icon-only version (the isotype / favicon — iceberg + sun, no text).
 * Use in narrow places (collapsed sidebar) or as a visual accent next to a
 * separate page heading.
 */
export function YachayIcon({ size, className = "" }) {
  const dimensions = size != null
    ? { width: size, height: size }
    : {};
  return (
    <img
      src={ICON_SRC}
      alt="Yachay Deep"
      {...dimensions}
      className={`select-none ${className}`}
      draggable={false}
    />
  );
}
