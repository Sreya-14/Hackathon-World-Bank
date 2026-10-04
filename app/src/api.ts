// Listings come from the Lantern server when VITE_API_URL is set; otherwise the
// app shows bundled sample listings so the map works on its own (e.g. GitHub Pages).
import { cacheListings, getCachedListings } from './db';
import type { ListingCollection } from './types';

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '';
const SAMPLE_URL = `${import.meta.env.BASE_URL}data/sample-listings.json`;
// A server behind a free ngrok tunnel answers browsers with a warning page unless this header is sent.
const API_HEADERS: HeadersInit = /ngrok/.test(API_URL) ? { 'ngrok-skip-browser-warning': '1' } : {};

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = url.startsWith(API_URL || '\0') ? API_HEADERS : {};
  const res = await fetch(url, { ...init, headers, signal: AbortSignal.timeout(10_000) });
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
      const saved = new Map(cached?.features.map((f) => [f.properties.id, f.properties]));
      data.features.forEach((f) => {
        const old = saved.get(f.properties.id);
        f.properties.whatsapp_url ??= old?.whatsapp_url ?? null;
        f.properties.sms_url ??= old?.sms_url ?? null;
      });
    }
    await cacheListings(data);
    return { data, fromCache: false };
  } catch (err) {
    const cached = await getCachedListings();
    if (cached) return { data: cached, fromCache: true };
    throw err;
  }
}

export interface ContactLinks {
  whatsapp_url: string | null;
  sms_url: string | null;
}

/** The host's WhatsApp and SMS links. Fetched on tap (counts interest); falls back to the offline copy. */
export async function contactLinks(id: number, offlineCopy: ContactLinks): Promise<ContactLinks> {
  if (API_URL && navigator.onLine) {
    try {
      return await getJson<ContactLinks>(`${API_URL}/api/listings/${id}/contact`, { method: 'POST' });
    } catch {
      /* fall through to the saved copy */
    }
  }
  return offlineCopy;
}

/**
 * A photo URL the browser can show. Photos from a server behind ngrok are fetched with the
 * skip-warning header (an <img> can't send it) and shown from a blob URL.
 */
export async function photoSrc(url: string): Promise<string> {
  if (!API_URL || !url.startsWith(API_URL) || !('ngrok-skip-browser-warning' in API_HEADERS)) return url;
  const res = await fetch(url, { headers: API_HEADERS });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return URL.createObjectURL(await res.blob());
}

export async function sendFeedback(id: number, kind: 'met' | 'report'): Promise<void> {
  if (!API_URL) return;
  await fetch(`${API_URL}/api/listings/${id}/${kind}`, { method: 'POST', headers: API_HEADERS }).catch(() => undefined);
}
