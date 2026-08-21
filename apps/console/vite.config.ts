import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['marko-icon.svg'],
      manifest: {
        name: 'Marko — Console de auditoria',
        short_name: 'Marko',
        description: 'Leitura auditável de accounting, research, decisions e shadow.',
        lang: 'pt-BR',
        theme_color: '#18202a',
        background_color: '#eaf1f5',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/marko-icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
          { src: '/marko-maskable.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'maskable' },
        ],
      },
    }),
  ],
  server: {
    port: 4173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
  },
})
