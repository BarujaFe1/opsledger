/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0c1210",
          900: "#121a17",
          800: "#1a2621",
          700: "#2a3b34",
          600: "#3d5349",
          500: "#5a7367",
          400: "#7f978a",
          300: "#a8b9b0",
          200: "#d0dbd5",
          100: "#e8eeeB",
          50: "#f4f7f5",
        },
        accent: {
          DEFAULT: "#1f6f5b",
          soft: "#2d8f74",
          muted: "#d7efe6",
          warm: "#c45c26",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "Segoe UI", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "grid-faint":
          "linear-gradient(to right, rgba(18,26,23,0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(18,26,23,0.04) 1px, transparent 1px)",
        "hero-wash":
          "radial-gradient(ellipse 80% 60% at 70% 20%, rgba(45,143,116,0.18), transparent 55%), radial-gradient(ellipse 50% 40% at 10% 80%, rgba(196,92,38,0.10), transparent 50%), linear-gradient(160deg, #f4f7f5 0%, #e8eeeB 45%, #d7efe6 100%)",
      },
      boxShadow: {
        soft: "0 12px 40px -20px rgba(12,18,16,0.35)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.6s ease-out both",
        "fade-up-delay": "fade-up 0.7s ease-out 0.12s both",
        "fade-up-delay-2": "fade-up 0.7s ease-out 0.24s both",
        "pulse-soft": "pulse-soft 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
