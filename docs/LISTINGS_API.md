# Listings API: what the tourist app expects from the backend

The tourist app (`app/`) reads listings from the backend when it's built with `VITE_API_URL` set. Without it, the app shows the bundled sample listings in `app/public/data/sample-listings.json`. Those use the same format, so that file is a working example.

TypeScript types: [`app/src/types.ts`](../app/src/types.ts).

## Endpoints

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/api/listings` | `FeatureCollection` | Live, approved, not-hidden listings. **No phone numbers.** Polled every 30 s while online, so new pins appear without a reload. |
| GET | `/api/bundle` | `FeatureCollection` + `generated_at` | Same as `/api/listings`, plus `whatsapp_url` on each listing. Fetched only when the tourist taps "Save for offline", so contact works in airplane mode. |
| POST | `/api/listings/{id}/contact` | `{ "whatsapp_url": "https://wa.me/…" }` | Called when the tourist taps "I'm interested" (the plan's "phone shown only on tap"). Can be used to count interest. |
| POST | `/api/listings/{id}/met` | any | "I met this host". |
| POST | `/api/listings/{id}/report` | any | Three reports should hide the listing. |

CORS must allow the app's origin, e.g. `https://sreya-14.github.io` and `http://localhost:5173`.

## A listing (GeoJSON Feature)

```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [76.0833, 11.6087] },
  "properties": {
    "id": 101,
    "category": "tour",
    "title": { "en": "Coffee plantation walk near Kalpetta", "de": "Kaffeeplantagen-Spaziergang bei Kalpetta" },
    "description": { "en": "…", "de": "…" },
    "price": "₹500 per person",
    "hours": "9:00–12:00",
    "photo_url": "https://<backend>/media/….jpg",
    "privacy": "area",
    "radius_m": 200,
    "verified": true,
    "met_count": 12,
    "days_since_checkin": 0.2,
    "seed": false,
    "updated_at": "2026-10-03T08:00:00+00:00",
    "whatsapp_url": null
  }
}
```

| Field | Rules |
|---|---|
| `coordinates` | `[lon, lat]`. For `privacy: "area"` this must already be the **snapped** point (~200 m grid); the exact spot never reaches the app. For `"meeting"`, it's the meeting point. |
| `category` | One of `food`, `craft`, `textile`, `tour`, `experience`, `other`. |
| `title`, `description` | English and German. |
| `price`, `hours` | `null` unless the vendor said them (no invented facts). The app shows "Ask the host" for `null`. |
| `privacy` | `exact`, `area` or `meeting`. Controls the pin style and the location text. |
| `radius_m` | Grid size for `area`, otherwise `null`. |
| `days_since_checkin` | Days since the vendor's last 📍 check-in (fractional), or `null`. Under 1 = "porch light on" glow; over 7 = faded pin. |
| `seed` | `true` for sample data; the app disables contact for these. |
| `whatsapp_url` | Only in `/api/bundle`. `https://wa.me/<digits>?text=<greeting>` with the greeting in the vendor's language (Malayalam) plus an English line. |
