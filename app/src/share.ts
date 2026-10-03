// Web Share Target: Android's share sheet opens <base>share?title=&text=&url= once the PWA is installed.
import { addEnquiry } from './db';

const BASE = import.meta.env.BASE_URL; // "/" locally, "/<repo>/" on GitHub Pages

/** Call once before rendering. Returns the new enquiry id if the app was opened by a share. */
export async function ingestShare(): Promise<number | undefined> {
  if (location.pathname.replace(/\/$/, '') !== `${BASE}share`) return undefined;
  const params = new URLSearchParams(location.search);
  // Clear the URL first so a reload (or StrictMode) can't add the same message twice.
  history.replaceState(null, '', BASE);
  const text = ['title', 'text', 'url'].map((k) => params.get(k)?.trim()).filter(Boolean).join('\n');
  if (!text) return undefined;
  const id = await addEnquiry(text);
  location.hash = `#/e/${id}`;
  return id;
}
