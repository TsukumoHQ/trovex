import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
// Multi-page: the marketing landing (index.html) + the /savings calculator
// (savings.html). Each is its own entry so they ship independent bundles.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Dev only: the /receipt dashboard (served at /receipt.html here) fetches the
  // local trovex server's real savings data. Proxy /api to it so same-origin
  // relative fetches work in `vite dev`. No effect on the production build.
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8765', changeOrigin: true },
    },
  },
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
