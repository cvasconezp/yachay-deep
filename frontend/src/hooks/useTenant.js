/**
 * Tenant detection based on subdomain.
 * 
 * yachaydeep.com          → tenant: null  (landing page)
 * ups.yachaydeep.com      → tenant: "ups"
 * demo.yachaydeep.com     → tenant: "demo"
 * localhost:3000           → tenant: null  (dev mode, shows landing)
 * localhost:3000?tenant=demo → tenant: "demo" (dev override)
 */

// "kapak.yachaydeep.com" va PRIMERO: es el host del panel de administracion (KAPAK)
// y debe tratarse como dominio raiz (tenant null), no como tenant "kapak".
const MAIN_DOMAINS = ["kapak.yachaydeep.com", "yachaydeep.com", "yachay-deep.vercel.app"];

export function getTenant() {
  const hostname = window.location.hostname;

  // Dev override via query param: ?tenant=demo
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    const params = new URLSearchParams(window.location.search);
    return params.get("tenant") || null;
  }

  // Check if it's a subdomain of yachaydeep.com
  for (const main of MAIN_DOMAINS) {
    if (hostname === main) return null; // root domain = landing
    if (hostname.endsWith(`.${main}`)) {
      const sub = hostname.slice(0, -(main.length + 1));
      // Only single-level subdomains (no dots)
      if (sub && !sub.includes(".")) return sub;
    }
  }

  return null;
}

export function isSubdomain() {
  return getTenant() !== null;
}

export function isDemoTenant() {
  return getTenant() === "demo";
}

/**
 * React hook for tenant context
 */
import { useMemo } from "react";

export function useTenant() {
  const tenant = useMemo(() => getTenant(), []);
  return {
    tenant,
    isSubdomain: tenant !== null,
    isDemo: tenant === "demo",
    isUps: tenant === "ups",
    displayName: tenant ? tenant.toUpperCase() : "YachayDeep",
  };
}
