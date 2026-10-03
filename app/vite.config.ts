import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  // GitHub Pages serves the app under /<repo>/; BASE_PATH is set by scripts/deploy-pages.sh.
  base: process.env.BASE_PATH ?? '/',
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
        name: 'Tour Assistant',
        short_name: 'Tours',
        description: 'Understand guest enquiries in English, German, Malayalam and Tamil, and reply offline.',
        // Relative URLs resolve against the manifest, so they work at / and under a sub-path.
        start_url: '.',
        scope: '.',
        display: 'standalone',
        background_color: '#faf6f1',
        theme_color: '#6b4226',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
        // Android share sheet → share?text=... (works only once installed).
        share_target: {
          action: 'share',
          method: 'GET',
          params: { title: 'title', text: 'text', url: 'url' },
        },
      },
    }),
  ],
  worker: { format: 'es' },
});
