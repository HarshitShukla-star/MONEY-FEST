import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: [
      'moneyfest.app',
      'www.moneyfest.app'
    ],
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/videos': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/thumbnails': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/gallery': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/video': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/render': {
        target: 'http://renderer:3100',
        changeOrigin: true,
      }
    }
  }
})
