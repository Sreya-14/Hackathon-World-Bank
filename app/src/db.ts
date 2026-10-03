// Everything the tourist saves for offline lives in IndexedDB on their phone.
import Dexie, { type EntityTable } from 'dexie';
import type { ListingCollection } from './types';

interface KV {
  key: string;
  value: unknown;
}

export interface SavedArea {
  key: 'area';
  tiles: Blob;
  savedAt: string;
  bytes: number;
}

export const db = new Dexie('lantern') as Dexie & {
  kv: EntityTable<KV, 'key'>;
  areas: EntityTable<SavedArea, 'key'>;
};

db.version(1).stores({ kv: 'key', areas: 'key' });

export async function getCachedListings(): Promise<ListingCollection | undefined> {
  return (await db.kv.get('listings'))?.value as ListingCollection | undefined;
}

export async function cacheListings(data: ListingCollection) {
  await db.kv.put({ key: 'listings', value: data });
}

export async function getMarked(kind: 'met' | 'reported'): Promise<number[]> {
  return ((await db.kv.get(kind))?.value as number[] | undefined) ?? [];
}

export async function mark(kind: 'met' | 'reported', id: number) {
  const ids = await getMarked(kind);
  if (!ids.includes(id)) await db.kv.put({ key: kind, value: [...ids, id] });
}
