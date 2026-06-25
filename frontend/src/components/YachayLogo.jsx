/**
 * Yachay Deep — marcas de marca (UNIFICADAS con @yachaydeep/brand).
 *
 * Los activos viven en /public/brand/ y se sincronizan automáticamente desde
 * https://github.com/cvasconezp/yachaydeep-brand (scripts/sync-brand.mjs +
 * GitHub Action "Sync de marca"). NO editar logos a mano aquí.
 *
 * Variantes canónicas (idénticas al hub corporativo):
 *   full | hero | hero-dark | navbar | banner | icon | simple
 * Alias de compatibilidad con el código previo de la app:
 *   light  → full       (lockup horizontal sobre fondo claro)
 *   dark   → hero-dark   (lockup sobre fondo oscuro)
 */
// SVG: nitidez en cualquier tamaño y ~10x menos peso.
const VARIANT_SRC = {
  full:        "/brand/logo-full.svg",
  hero:        "/brand/logo-hero.svg",
  "hero-dark": "/brand/logo-hero-dark.svg",
  navbar:      "/brand/logo-navbar.svg",
  banner:      "/brand/banner.svg",
  icon:        "/brand/logo-icon.svg",
  simple:      "/brand/logo-icon-simple.svg",
  stacked:     "/brand/logo-stacked.svg",
  // alias retrocompatibles
  light:       "/brand/logo-full.svg",
  dark:        "/brand/logo-hero-dark.svg",
};

const ICON_SRC = "/brand/logo-icon.svg";

export function YachayLogo({ variant = "full", size, className = "" }) {
  const src = VARIANT_SRC[variant] ?? VARIANT_SRC.full;
  const dimensions = size != null ? { height: size } : {};
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

export function YachayIcon({ size, className = "" }) {
  const dimensions = size != null ? { width: size, height: size } : {};
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
