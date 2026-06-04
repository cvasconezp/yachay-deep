/** @type {import('tailwindcss').Config} */
// Tokens de marca: copia sincronizada de yachaydeep-web/packages/brand/preset.cjs
// (fuente unica de verdad). NO editar colores aqui ni en el preset a mano.
import brandPreset from "./brand.preset.cjs";

export default {
  presets: [brandPreset],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      animation: {
        "spin-slow": "spin 3s linear infinite",
      },
    },
  },
  plugins: [],
};
