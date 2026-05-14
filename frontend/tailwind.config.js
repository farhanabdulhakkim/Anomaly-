/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          green: '#22c55e',
          dark:  '#0f1117',
          card:  '#1f2937',
          border:'#374151',
        },
      },
    },
  },
  plugins: [],
}
