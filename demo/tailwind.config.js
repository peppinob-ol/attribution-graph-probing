/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./app/**/*.py",
    "./islands/**/*.svelte",
    "./static/**/*.html",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Space Grotesk', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        tier: {
          5: '#10b981', // emerald-500
          4: '#84cc16', // lime-500
          3: '#eab308', // yellow-500
          2: '#fb923c', // orange-400
          1: '#ef4444', // red-500
          0: '#475569', // slate-600
        },
      },
      animation: {
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}

