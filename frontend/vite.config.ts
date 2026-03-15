import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',  // bind to all interfaces so 127.0.0.1:5555 works
    port: 5555,
    strictPort: true,
  },
})
