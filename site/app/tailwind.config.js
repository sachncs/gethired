/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
        display: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
      },
      letterSpacing: {
        tightest: "-0.045em",
        tighter: "-0.03em",
      },
      colors: {
        ink: {
          50: "#F7F7F8",
          100: "#EDEDEF",
          200: "#D7D7DB",
          300: "#B4B4BA",
          400: "#85858E",
          500: "#5C5C66",
          600: "#3F3F48",
          700: "#2A2A33",
          800: "#17171E",
          900: "#0B0B10",
          950: "#06060A",
        },
        accent: {
          DEFAULT: "#7C5CFF",
          50: "#F1EDFF",
          100: "#E2D9FF",
          200: "#C5B3FF",
          300: "#A98DFF",
          400: "#8C6BFF",
          500: "#7C5CFF",
          600: "#5E3DE6",
          700: "#4A2EB8",
          800: "#361F8A",
          900: "#22115C",
        },
      },
      boxShadow: {
        ring: "0 0 0 1px rgba(255,255,255,0.08), 0 1px 0 rgba(255,255,255,0.04) inset",
        soft: "0 1px 2px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.06)",
        glow: "0 0 0 1px rgba(124,92,255,0.25), 0 20px 60px -10px rgba(124,92,255,0.35)",
      },
      backgroundImage: {
        "grid-fade":
          "linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0) 70%, var(--grid-color, rgba(0,0,0,0.04)) 100%)",
      },
      keyframes: {
        floaty: {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        marquee: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        floaty: "floaty 6s ease-in-out infinite",
        shimmer: "shimmer 8s linear infinite",
        marquee: "marquee 38s linear infinite",
        "fade-up": "fade-up 0.7s ease-out both",
      },
    },
  },
  plugins: [],
};