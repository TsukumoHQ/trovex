import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dedicated build for the PRIVATE savings receipt dashboard.
//
// It is deliberately NOT part of the marketing build (vite.config.ts → dist/,
// deployed to trovex.dev at base '/'). The receipt view reads a running
// instance's real data over the local API and must never be published or
// indexed. trovex-backend mounts THIS output (web/dist-receipt) at /receipt on
// the `trovex serve` process, so the base is '/receipt/' and assets resolve
// under /receipt/assets. Keeping it separate is what lets the marketing site
// stay at base '/' while this one lives under /receipt/.
export default defineConfig({
  base: '/receipt/',
  plugins: [react(), tailwindcss()],
  build: {
    outDir: 'dist-receipt',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        receipt: fileURLToPath(new URL('./receipt.html', import.meta.url)),
      },
    },
  },
})
