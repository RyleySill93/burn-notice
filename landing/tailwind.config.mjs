/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,ts}'],
  theme: {
    extend: {
      colors: {
        brand: {
          orange: '#f97316',
          green: '#22c55e',
        },
        surface: {
          bg: '#0a0a0a',
          card: '#1a1a1a',
          border: 'rgba(255,255,255,0.1)',
        },
      },
      fontFamily: {
        bangers: ['Bangers', 'cursive'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.6s ease-out forwards',
        'fade-in-up-delay-1': 'fadeInUp 0.6s ease-out 0.15s forwards',
        'fade-in-up-delay-2': 'fadeInUp 0.6s ease-out 0.3s forwards',
        'float': 'float 6s ease-in-out infinite',
        'glow-pulse': 'glowPulse 3s ease-in-out infinite',
        'blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(24px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-12px)' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 40px rgba(249,115,22,0.3)' },
          '50%': { boxShadow: '0 0 80px rgba(249,115,22,0.5)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
};
