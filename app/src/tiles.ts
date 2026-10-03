// Map tiles: a single PMTiles file for Wayanad. Online it streams from the site;
// after "Save for offline" it's read from a Blob in IndexedDB, so the map works in airplane mode.
import maplibregl from 'maplibre-gl';
import { FileSource, PMTiles, Protocol } from 'pmtiles';
import { loadListings } from './api';
import { db, type SavedArea } from './db';

export const REMOTE_TILES = new URL(`${import.meta.env.BASE_URL}tiles/wayanad.pmtiles`, location.href).href;
export const AREA_MB = 6.6;
const OFFLINE_KEY = 'wayanad-offline.pmtiles';

const protocol = new Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);

/** Source URL for the basemap: the saved copy if there is one, otherwise the network. */
export function tilesUrl(saved: SavedArea | undefined): string {
  if (!saved) return `pmtiles://${REMOTE_TILES}`;
  protocol.add(new PMTiles(new FileSource(new File([saved.tiles], OFFLINE_KEY))));
  return `pmtiles://${OFFLINE_KEY}`;
}

export const getSavedArea = () => db.areas.get('area');

/** Downloads the tiles and the listings bundle (with contact links) for offline use. */
export async function saveArea(onProgress: (fraction: number) => void): Promise<SavedArea> {
  const res = await fetch(REMOTE_TILES, { cache: 'no-store' });
  if (!res.ok || !res.body) throw new Error(`tiles ${res.status}`);
  const total = Number(res.headers.get('content-length')) || AREA_MB * 1e6;
  const reader = res.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    onProgress(Math.min(received / total, 0.95));
  }
  await loadListings(true);
  const area: SavedArea = { key: 'area', tiles: new Blob(chunks as BlobPart[]), savedAt: new Date().toISOString(), bytes: received };
  await db.areas.put(area);
  onProgress(1);
  return area;
}

export const removeArea = () => db.areas.delete('area');
