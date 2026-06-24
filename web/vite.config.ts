import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
// Multi-page: the marketing landing (index.html) + the /savings calculator
// (savings.html). Each is its own entry so they ship independent bundles.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        savings: fileURLToPath(new URL('./savings.html', import.meta.url)),
        audit: fileURLToPath(new URL('./audit.html', import.meta.url)),
      },
    },
  },
})
