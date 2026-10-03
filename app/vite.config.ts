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
        // App shell, map fonts/icons and sample data are precached. The tile file (6.6 MB)
        // is only stored when the tourist taps "Save for offline".
        globPatterns: ['**/*.{js,css,html,svg,png,pbf,json}'],
        globIgnores: ['**/tiles/**'],
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
        runtimeCaching: [
          {
            // Listing photos from the backend: keep what the tourist has seen.
            urlPattern: ({ url }) => url.pathname.includes('/media/'),
            handler: 'CacheFirst',
            options: { cacheName: 'listing-photos', expiration: { maxEntries: 200 } },
          },
        ],
      },
      manifest: {
        name: 'Porchlight',
        short_name: 'Porchlight',
        description: 'Find local hosts, tours and crafts in Wayanad. Works offline.',
        // Relative URLs resolve against the manifest, so they work at / and under a sub-path.
        start_url: '.',
        scope: '.',
        display: 'standalone',
        background_color: '#f6f1e9',
        theme_color: '#1b2330',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
});
