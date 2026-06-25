/** @type {import('tailwindcss').Config} */
// Tokens de marca: https://github.com/cvasconezp/yachaydeep-brand
// (fuente unica de verdad). NO definir colores de marca aqui.
import brandPreset from "@yachaydeep/brand/preset";

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
