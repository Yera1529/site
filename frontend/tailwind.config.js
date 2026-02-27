/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#e8eef8",
          100: "#c5d4ee",
          200: "#9eb8e3",
          300: "#7499d6",
          400: "#5480cb",
          500: "#3366bf",
          600: "#0033aa",
          700: "#002d96",
          800: "#002480",
          900: "#001a66",
          950: "#001040",
        },
        accent: {
          50: "#e6f2ff",
          100: "#cce5ff",
          200: "#99cbff",
          300: "#66b0ff",
          400: "#3396ff",
          500: "#007bff",
          600: "#0062cc",
          700: "#004a99",
          800: "#003166",
          900: "#001933",
        },
      },
      fontFamily: {
        sans: ['"Inter"', '"Segoe UI"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
