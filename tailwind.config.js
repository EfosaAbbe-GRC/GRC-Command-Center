/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'grc-dark': '#0f172a',
        'grc-panel': '#1e293b',
        'grc-accent': '#3b82f6',
        'grc-risk': '#ef4444',
        'grc-safe': '#10b981',
        'grc-warn': '#f59e0b',
      }
    },
  },
  plugins: [],
}
