# Porchlight

Hack-Nation × World Bank, Small AI for Development: Tourism (Annex C).

A small tour or craft business in Wayanad, Kerala describes what it offers in a WhatsApp voice note, in Malayalam. Small AI models turn that into a listing in English and German. The vendor hears it read back and approves it, and tourists find the vendor on a map that works offline.

## This repo

| Folder | What |
|---|---|
| `app/` | **Tourist app**: installable PWA (Vite + React + TypeScript, MapLibre + PMTiles, Dexie). Map of Wayanad, listings in EN/DE, WhatsApp contact with a Malayalam greeting, offline area download. |
| `docs/LISTINGS_API.md` | The listings data format the app reads from the backend. |
| `scripts/deploy-pages.sh` | Builds the app and publishes it to GitHub Pages. |

The WhatsApp bot, backend and small-AI pipeline are on a separate branch and will be integrated later.

## Run the app

Node 22:

```bash
cd app && npm install && npm run dev
```

With no backend configured, the map shows clearly labelled **sample listings**. To use a backend:

```bash
VITE_API_URL=https://<backend> npm run dev
```

## Offline

- The app shell, map fonts and icons are cached by a service worker.
- **Save Wayanad for offline** stores the map tiles (6.6 MB, OpenStreetMap data via Protomaps) and all listings, including contact links, on the phone (IndexedDB).
- After that, the map, listings and "I'm interested" all work in airplane mode. WhatsApp sends the message once the phone is back online.

## Data

- Map: © OpenStreetMap contributors, via a Protomaps extract (`app/public/tiles/wayanad.pmtiles`, bbox 75.75,11.45,76.45,11.98, zoom 0–14).
- Sample listings in `app/public/data/sample-listings.json` are fictional and marked "Sample listing" in the app.
