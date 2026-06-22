import { defineConfig } from 'vitest/config'

// Node environment: the suite covers the serverless api/ layer (lead capture,
// rate-limit, OG-meta injection, savings math) — no DOM needed.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['test/**/*.test.{js,ts}'],
  },
})
