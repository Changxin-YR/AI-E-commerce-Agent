import { fileURLToPath, URL } from 'node:url'
import process from 'node:process'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { normalizeApiOrigin } from './src/lib/apiEndpoint.ts'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  if (mode === 'android') {
    normalizeApiOrigin(loadEnv(mode, process.cwd(), 'VITE_').VITE_SOLOOPS_API_ORIGIN)
  }
  return {
    plugins: [vue()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      proxy: { '/api': process.env.SOLOOPS_API_TARGET ?? 'http://127.0.0.1:8000' },
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
  }
})
