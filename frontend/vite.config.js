import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/health':       'http://127.0.0.1:8000',
      '/stations':     'http://127.0.0.1:8000',
      '/observations': 'http://127.0.0.1:8000',
      '/weather':      'http://127.0.0.1:8000',
      '/fire':         'http://127.0.0.1:8000',
      '/pipeline':     'http://127.0.0.1:8000',
      '/forecast':     'http://127.0.0.1:8000',
      // Auth / OTP endpoints — proxied so no API keys are in the frontend
      '/auth':         'http://127.0.0.1:8000',
    },
  },
})
