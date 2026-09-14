/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Manrope", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        // Deep ink scale -- the app shell (sidebar/topbar) and dark surfaces.
        ink: {
          950: "#05070d",
          900: "#0a0e1a",
          850: "#0e1424",
          800: "#131b30",
          700: "#1b2544",
          600: "#293563",
          500: "#3a477a",
        },
        // Kept as an alias so any not-yet-migrated class still resolves sanely.
        oil: {
          50: "#f0f5fa", 100: "#dbe6f2", 200: "#b8cde5", 300: "#8caed3", 400: "#5c88bd",
          500: "#3c6aa3", 600: "#2c5285", 700: "#22406a", 800: "#1c3355", 900: "#152941",
        },
        // Brand accent -- a refined amber/gold (industrial-safety signal, echoes
        // hazard signage and the "OIL" in SIFGuard-OIL) rather than generic SaaS blue.
        accent: {
          50: "#fff8ea", 100: "#ffedc4", 200: "#ffdc8a", 300: "#f7c765",
          400: "#f0b143", 500: "#e29a26", 600: "#c17f18", 700: "#976214", 800: "#6f4a10",
        },
        // Secondary accent -- teal, used sparingly for informational/neutral highlights.
        teal: {
          50: "#eefcfb", 100: "#d3f6f2", 300: "#7fdcd2", 500: "#17a396", 600: "#0f8378", 700: "#0c675e",
        },
        // Canonical SIF-risk palette -- used consistently everywhere a
        // classification is rendered (badges, charts, KPI accents). Never
        // reassign these semantically; only refine the exact hue.
        risk: {
          high: "#e0264f",
          medium: "#f2932c",
          low: "#d4a017",
          nonsif: "#189a6b",
          review: "#7c5cf0",
        },
        surface: {
          DEFAULT: "#f5f6fb",
          muted: "#eceef6",
          raised: "#ffffff",
        },
        ink_text: {
          primary: "#121729",
          secondary: "#57607a",
          muted: "#8b93aa",
        },
        line: "#e3e6f0",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px -12px rgba(15, 23, 42, 0.10)",
        raised: "0 4px 16px -4px rgba(15, 23, 42, 0.12), 0 2px 6px -2px rgba(15, 23, 42, 0.08)",
        glow: "0 0 0 1px rgba(226, 154, 38, 0.35), 0 8px 24px -8px rgba(226, 154, 38, 0.35)",
      },
      borderRadius: {
        xl2: "1.1rem",
      },
    },
  },
  plugins: [],
};
