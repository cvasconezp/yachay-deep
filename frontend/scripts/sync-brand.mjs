/**
 * Copia los activos de marca instalados (@yachaydeep/brand/assets) a public/brand.
 * Lo ejecuta el workflow "Sync de marca" tras actualizar la dependencia.
 * Uso local:  node scripts/sync-brand.mjs
 */
import { cpSync, mkdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../node_modules/@yachaydeep/brand/assets");
const dest = resolve(here, "../public/brand");

if (!existsSync(src)) {
  console.error("No se encontró @yachaydeep/brand/assets. ¿Instalaste la dependencia?");
  process.exit(1);
}
mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true });
console.log("✓ Activos de marca sincronizados:", src, "→", dest);
