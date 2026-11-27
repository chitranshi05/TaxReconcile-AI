import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const { VITE_API_BASE_URL } = loadEnv(mode, process.cwd(), 'VITE_')

  return {
    plugins: [react()],
    server: {
      proxy: VITE_API_BASE_URL
        ? {
            '/api': { target: VITE_API_BASE_URL, changeOrigin: true },
            '/health': { target: VITE_API_BASE_URL, changeOrigin: true },
          }
        : undefined,
    },
  }
})
