/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#1B3A6B", dark: "#0f2340", light: "#2B5AA0" },
      },
    },
  },
  plugins: [],
};
