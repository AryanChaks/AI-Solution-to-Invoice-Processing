import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// The browser only talks to Vite (localhost:5173); /api is proxied to the backend, so no DB/secret ever reaches React.
export default defineConfig({
  plugins: [react()],
  server: { host: 'localhost', allowedHosts: true, port: 5173, proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } } },
})
