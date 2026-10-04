# Lantern

Hack-Nation × World Bank, Small AI for Development: Tourism (Annex C).

A small tour or craft host in Wayanad, Kerala describes what they offer in a voice note, in Malayalam. Small local AI models turn it into a listing in English and German. The host hears it read back in Malayalam and approves it, then chooses how exactly to share their location. Tourists find them on a map that works offline and tap to message them on WhatsApp, with a greeting already written in Malayalam.

```
Host (WhatsApp or /host page)  →  server/  →  ml/pipeline (speech → listing → read-back)
                                     │
                                     └── /api/listings  →  app/ (tourist map, offline)
```

| Folder | What |
|---|---|
| `app/` | **Tourist app**: installable PWA (Vite + React + TypeScript, MapLibre + PMTiles, Dexie). Map of Wayanad, listings in EN/DE, WhatsApp contact, offline area download. |
| `server/` | **Lantern server** (FastAPI): the host's bot over WhatsApp (Twilio) or the `/host` web page, a photo check, a job queue around the ML layer, the approve → location → privacy flow, and the public listings API. |
| `ml/` | **ML layer**: Malayalam voice note → listing + read-back, with small local models (~2.7 GB). See [docs/ENGINE_API.md](docs/ENGINE_API.md). |
| `docs/` | [LISTINGS_API.md](docs/LISTINGS_API.md) (server → app), [ENGINE_API.md](docs/ENGINE_API.md) (ML layer → server). |
| `scripts/deploy-pages.sh` | Builds the tourist app and publishes it to GitHub Pages. |

## Run it locally

Python 3.11 and Node 22.

**1. Server** (mock ML: no models needed)

```bash
cd server
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m scripts.seed          # optional: sample listings on the map
.venv/bin/uvicorn app.main:app --port 8000
```

Hosts open **http://localhost:8000/host**: send a photo, record (or type) a description in Malayalam, listen to the read-back, send 👍, share a location, and choose 1 / 2 / 3 for privacy.

**2. Real ML layer** (instead of the mock)

```bash
cd server
CMAKE_ARGS="-DGGML_METAL=on" .venv/bin/pip install -r ../ml/requirements-pipeline.txt   # Metal flag: Apple Silicon only
cd ../ml && ../server/.venv/bin/python -m pipeline.models                                 # ~2.7 GB, once
cd ../server && MOCK_AI=false .venv/bin/uvicorn app.main:app --port 8000
```

Measured on a MacBook (M-series, CPU): models load in ~14 s, a typed description takes ~7 s, and a voice note takes longer depending on length.

**3. Tourist app**

```bash
cd app && npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Without `VITE_API_URL` the app shows bundled sample listings, which is how the GitHub Pages demo works with no server.

**4. WhatsApp** (optional): create a Twilio WhatsApp Sandbox, copy `server/.env.example` to `server/.env`, fill in the Twilio keys and a public HTTPS `PUBLIC_BASE_URL` (e.g. ngrok), and set the sandbox webhook to `<PUBLIC_BASE_URL>/twilio/whatsapp`.

## Tests

```bash
cd server && .venv/bin/python -m pytest -q              # full host flow against the mock ML layer
MOCK_AI=false .venv/bin/python -m scripts.smoke_real    # one run through the real models
```

## Guardrails

- **Host approval:** nothing goes live until the host hears the read-back and sends 👍.
- **"Not sure":** unclear audio, wrong language, lost translation or an invented fact (`needs_review`) publishes nothing and asks the host to say it again.
- **Location privacy:** exact spot, a ~200 m area (snapped before storing), or a meeting point. The phone number is only shared when a tourist taps "I'm interested". ❌ hides a listing at any time, and three reports hide it until a partner checks.
- **Offline:** the app shell is cached, and "Save Wayanad for offline" stores the map (6.6 MB) and listings on the phone.

## Data

- Map: © OpenStreetMap contributors, via a Protomaps extract (`app/public/tiles/wayanad.pmtiles`).
- Sample listings (`app/public/data/sample-listings.json`) are fictional and marked "Sample listing" in the app.
- ML datasets, models and their limits: [docs/ENGINE_API.md](docs/ENGINE_API.md).
