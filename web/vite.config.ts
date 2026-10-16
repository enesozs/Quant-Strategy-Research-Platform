/// <reference types="vitest/config" />
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    port: 5190,
    strictPort: true,
    // FastAPI runs on API_PORT (default 8020) in development; the browser only talks to Vite.
    proxy: { '/api': `http://localhost:${process.env.API_PORT ?? 8020}` },
  },
  build: {
    outDir: 'dist',
    // ECharts is one ~550 kB chunk even tree-shaken; it is cached separately from the app.
    chunkSizeWarningLimit: 700,
    rolldownOptions: {
      output: {
        // Charting code changes rarely; keep it out of the app chunk for caching.
        codeSplitting: {
          groups: [{ name: 'echarts', test: /node_modules[\\/](echarts|zrender)/ }],
        },
      },
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
