/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: 'class',
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
        glass: {
          light: "rgba(255, 255, 255, 0.7)",
          dark: "rgba(15, 23, 42, 0.7)",
          border: "rgba(255, 255, 255, 0.18)",
          borderDark: "rgba(255, 255, 255, 0.08)",
        }
      },
      fontFamily: {
        sans: ['"Inter"', '"Segoe UI"', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.07)',
        'glass-dark': '0 8px 32px 0 rgba(0, 0, 0, 0.3)',
      },
      backdropBlur: {
        'glass': '12px',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      }
    },
  },
  plugins: [],
};
