import { useSyncExternalStore } from 'react';

export type Route =
  | { name: 'home' }
  | { name: 'enquiry'; id: number }
  | { name: 'outbox' }
  | { name: 'bookings' }
  | { name: 'admin' };

function parseHash(hash: string): Route {
  const [, a, b] = hash.replace(/^#/, '').split('/');
  if (a === 'e' && Number(b)) return { name: 'enquiry', id: Number(b) };
  if (a === 'outbox' || a === 'bookings' || a === 'admin') return { name: a };
  return { name: 'home' };
}

// popstate too: history.pushState/back can change the hash without a hashchange event.
const subscribeHash = (cb: () => void) => {
  addEventListener('hashchange', cb);
  addEventListener('popstate', cb);
  return () => {
    removeEventListener('hashchange', cb);
    removeEventListener('popstate', cb);
  };
};

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribeHash, () => location.hash);
  return parseHash(hash);
}

export const go = (path: string) => (location.hash = path);

const subscribeOnline = (cb: () => void) => {
  addEventListener('online', cb);
  addEventListener('offline', cb);
  return () => {
    removeEventListener('online', cb);
    removeEventListener('offline', cb);
  };
};

export function useOnline(): boolean {
  return useSyncExternalStore(subscribeOnline, () => navigator.onLine);
}
