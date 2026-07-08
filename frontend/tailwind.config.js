/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#722ed1',
          dark: '#531dab',
          light: '#f9f0ff',
        }
      }
    },
  },
  plugins: [],
}
