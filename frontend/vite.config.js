import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite 配置：开发代理转发到后端，构建产物输出到 dist
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // 后端地址，开发时通过代理转发，避免跨域
  const backend = env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'
  return {
    plugins: [vue()],
    server: {
      host: '0.0.0.0',
      port: Number(env.VITE_PORT) || 5173,
      proxy: {
        '/api': { target: backend, changeOrigin: true },
        '/guard': { target: backend, changeOrigin: true },
        '/ws': { target: backend, ws: true, changeOrigin: true },
        '/docs': { target: backend, changeOrigin: true },
        '/redoc': { target: backend, changeOrigin: true },
        '/openapi.json': { target: backend, changeOrigin: true },
        '/static': { target: backend, changeOrigin: true }
      }
    },
    build: {
      outDir: 'dist',
      chunkSizeWarningLimit: 1500
    }
  }
})
