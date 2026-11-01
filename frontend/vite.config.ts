import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The FastAPI backend runs on :3000. In dev the proxy avoids CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true,
      },
    },
  },
})
