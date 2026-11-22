/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      colors: {
        industrial: {
          bg: '#080d1a',
          surface: '#0f172a',
          card: '#131e33',
          border: '#1e293b',
          borderLight: '#334155',
          textMuted: '#64748b',
          textMain: '#e2e8f0',
          accent: '#3b82f6',
        },
      },
    },
  },
  plugins: [],
}
