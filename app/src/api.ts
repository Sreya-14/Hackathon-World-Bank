// Listings come from the Lantern server when VITE_API_URL is set; otherwise the
// app shows bundled sample listings so the map works on its own (e.g. GitHub Pages).
import { cacheListings, getCachedListings } from './db';
import type { ListingCollection } from './types';

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '';
const SAMPLE_URL = `${import.meta.env.BASE_URL}data/sample-listings.json`;

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, signal: AbortSignal.timeout(10_000) });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json() as Promise<T>;
}

/**
 * Fresh listings when online (cached for later), the cached copy when not.
 * `withContacts` asks for the offline bundle, which includes WhatsApp links.
 */
export async function loadListings(withContacts = false): Promise<{ data: ListingCollection; fromCache: boolean }> {
  try {
    const url = API_URL ? `${API_URL}/api/${withContacts ? 'bundle' : 'listings'}` : SAMPLE_URL;
    const data = await getJson<ListingCollection>(url);
    if (!withContacts) {
      // Keep contact links from an earlier offline bundle so they still work offline.
      const cached = await getCachedListings();
      const links = new Map(cached?.features.map((f) => [f.properties.id, f.properties.whatsapp_url]));
      data.features.forEach((f) => (f.properties.whatsapp_url ??= links.get(f.properties.id) ?? null));
    }
    await cacheListings(data);
    return { data, fromCache: false };
  } catch (err) {
    const cached = await getCachedListings();
    if (cached) return { data: cached, fromCache: true };
    throw err;
  }
}

/** The vendor's WhatsApp link. Fetched on tap (counts interest); falls back to the offline copy. */
export async function contactLink(id: number, offlineCopy?: string | null): Promise<string | null> {
  if (API_URL && navigator.onLine) {
    try {
      return (await getJson<{ whatsapp_url: string }>(`${API_URL}/api/listings/${id}/contact`, { method: 'POST' })).whatsapp_url;
    } catch {
      /* fall through to the saved copy */
    }
  }
  return offlineCopy ?? null;
}

export async function sendFeedback(id: number, kind: 'met' | 'report'): Promise<void> {
  if (!API_URL) return;
  await fetch(`${API_URL}/api/listings/${id}/${kind}`, { method: 'POST' }).catch(() => undefined);
}
