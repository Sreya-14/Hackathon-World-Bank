import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        // Models are cached by transformers.js itself, not precached here.
        globIgnores: ['**/models/**'],
        globPatterns: ['**/*.{js,css,html,svg,png,wasm}'],
        maximumFileSizeToCacheInBytes: 40 * 1024 * 1024,
      },
      manifest: {
        name: 'Noor Tour Assistant',
        short_name: 'Noor',
        lang: 'sw',
        start_url: '/',
        display: 'standalone',
        background_color: '#ffffff',
        theme_color: '#6b4226',
        icons: [],
        // Android share sheet → /share?text=... (works only once installed).
        share_target: {
          action: '/share',
          method: 'GET',
          params: { title: 'title', text: 'text', url: 'url' },
        },
      },
    }),
  ],
  worker: { format: 'es' },
});
