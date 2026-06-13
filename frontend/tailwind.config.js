/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        vesta: {
          50:  '#f0f4ff',
          100: '#dbe4ff',
          500: '#4263eb',
          600: '#3451d1',
          700: '#2b44ba',
          900: '#1a2a7a',
        },
      },
    },
  },
  plugins: [],
}
