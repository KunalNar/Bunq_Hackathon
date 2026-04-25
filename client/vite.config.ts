import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': 'http://localhost:8000',
      '/voice': 'http://localhost:8000',
      '/receipt': 'http://localhost:8000',
      '/state': 'http://localhost:8000',
      '/reset': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  build: {
    outDir: '../web/dist',
    emptyOutDir: true,
  },
})
