// vite.config.js — build + dev-server config for the sandbox SPA (CP-4).
//
// API wiring (see frontend/README.md):
//   - The app talks to the backend through the base path `/api` (VITE_API_BASE).
//   - In `npm run dev` (host), the Vite dev server below PROXIES `/api` -> the API
//     (default http://localhost:8000), stripping the `/api` prefix. No CORS needed.
//   - In production (Docker), the static bundle is served by nginx, which reverse-proxies
//     `/api/` -> http://api:8000/ (see frontend/nginx.conf). Same-origin, no CORS.
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Backend origin used ONLY by the dev-server proxy. Overridable for local runs.
const DEV_API_TARGET = process.env.VITE_DEV_API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: DEV_API_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
