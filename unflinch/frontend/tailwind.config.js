/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Bebas Neue"', 'sans-serif'],
        body: ['"DM Sans"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        obsidian: '#0A0A0F',
        carbon: '#111118',
        graphite: '#1C1C28',
        steel: '#2A2A3C',
        mist: '#8B8BA0',
        chalk: '#E8E8F0',
        white: '#FFFFFF',
        ember: '#FF4D1C',
        amber: '#FF8C42',
        jade: '#00E5A0',
        azure: '#4A9EFF',
        violet: '#8B5CF6',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
        'record-ring': 'recordRing 1.5s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: 0 }, '100%': { opacity: 1 } },
        slideUp: { '0%': { opacity: 0, transform: 'translateY(20px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        recordRing: {
          '0%, 100%': { transform: 'scale(1)', opacity: 0.8 },
          '50%': { transform: 'scale(1.15)', opacity: 0.3 },
        },
      },
    },
  },
  plugins: [],
}
