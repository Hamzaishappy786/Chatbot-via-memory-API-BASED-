import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev server proxies backend routes to FastAPI on :8000,
// so the frontend can use relative paths (no CORS juggling).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/documents': 'http://127.0.0.1:8000',
      '/query':     'http://127.0.0.1:8000',
      '/portfolio': 'http://127.0.0.1:8000',
      '/health':    'http://127.0.0.1:8000',
    },
  },
})
