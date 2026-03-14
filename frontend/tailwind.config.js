/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#1B3A6B",
          dark: "#0F2444",
          light: "#2B5AA0",
          gold: "#E8A838",
          "gold-light": "#F5C563",
          ice: "#A8DCE8",
          "ice-light": "#D8EFF4",
        },
      },
    },
  },
  plugins: [],
};
