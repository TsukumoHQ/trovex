import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dedicated build for the PRIVATE knowledge-graph view ("the codebase's
// brain"). Like the /receipt dashboard it reads a running instance's real
// index over the local API and must never be published or indexed.
// trovex-backend mounts THIS output (web/dist-graph) at /graph on the
// `trovex serve` process, so the base is '/graph/' and assets resolve under
// /graph/assets. Keeping it separate from the marketing build (base '/') is
// what lets the landing site stay at '/' while this one lives under /graph/.
export default defineConfig({
  base: '/graph/',
  plugins: [react(), tailwindcss()],
  // Dev only: proxy the local trovex server so same-origin /api fetches work
  // in `vite dev --config vite.graph.config.ts`. No effect on the build.
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8765', changeOrigin: true },
    },
  },
  worker: {
    format: 'es',
  },
  build: {
    outDir: 'dist-graph',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        graph: fileURLToPath(new URL('./graph.html', import.meta.url)),
      },
    },
  },
})
