import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    // Escucha en todas las interfaces; útil si corres la app en Docker
    host: '0.0.0.0',

    // Dominios explícitos que puede atender Vite
    allowedHosts: [
      'localhost',
      '127.0.0.1',
      'gestion.127.0.0.1.nip.io',   // ← el que necesitas
    ],

    // Si accedes por un proxy inverso o contenedor, define el host para HMR
    // hmr: { host: 'tienda2.127.0.0.1.nip.io', port: 5173 },
  },
})
