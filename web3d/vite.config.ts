import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const target = process.env.VITE_ENGINE_URL ?? 'http://127.0.0.1:8020'

export default defineConfig({
  plugins: [react()],
  server: { port: 5175, proxy: { '/api': target } },
  test: { environment: 'node', include: ['tests/**/*.test.ts'] },
})
