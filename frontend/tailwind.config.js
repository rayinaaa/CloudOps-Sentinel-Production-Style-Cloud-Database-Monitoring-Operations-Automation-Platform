/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        sentinel: {
          950: "#070B12", // Deepest background
          900: "#0D1424", // Primary canvas
          850: "#131C31", // Surface card
          800: "#1B2742", // Elevated border & panel
          700: "#2B3C62", // Hover states
          600: "#415888",
          muted: "#94A3B8",
          accent: "#0284C7", // Cyan / sky ops blue
          accentLight: "#38BDF8",
          success: "#10B981", // Emerald healthy
          warning: "#F59E0B", // Amber warning
          danger: "#EF4444",  // Red critical
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "Courier New", "monospace"],
      },
    },
  },
  plugins: [],
}

