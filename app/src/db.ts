// All app data lives on the phone, in IndexedDB. Nothing goes to a server.
import Dexie, { type EntityTable } from 'dexie';
import { useLiveQuery } from 'dexie-react-hooks';
import type { IntentId, Understanding } from './engine';
import type { Asked } from './content/templates';
import { DEFAULT_FACTS, type TourFacts } from './content/facts';

/** What the vendor decided on the enquiry screen. Starts with what the rules extracted. */
export interface Decision {
  date?: number; // ms, local midnight
  groupSize?: number;
  /** Yes/no for availability and booking. */
  open?: boolean;
  /** Set when the vendor picks the topic themselves (overrides the engine). */
  intents?: IntentId[];
}

export interface Enquiry {
  id?: number;
  receivedAt: number;
  text: string;
  status: 'new' | 'ready' | 'replied' | 'dismissed';
  understanding?: Understanding;
  asked?: Asked;
  decision: Decision;
  guestPhone?: string;
}

export type Channel = 'whatsapp' | 'sms';

export interface OutboxItem {
  id?: number;
  enquiryId: number;
  channel: Channel;
  to?: string;
  text: string;
  createdAt: number;
  sentAt?: number;
}

export interface Booking {
  id?: number;
  enquiryId: number;
  date: number;
  groupSize?: number;
  guestPhone?: string;
  createdAt: number;
}

interface KV {
  key: string;
  value: unknown;
}

export const db = new Dexie('tour-assistant') as Dexie & {
  enquiries: EntityTable<Enquiry, 'id'>;
  outbox: EntityTable<OutboxItem, 'id'>;
  bookings: EntityTable<Booking, 'id'>;
  kv: EntityTable<KV, 'key'>;
};

db.version(1).stores({
  enquiries: '++id, receivedAt, status',
  outbox: '++id, createdAt, enquiryId',
  bookings: '++id, date, enquiryId',
  kv: 'key',
});

export async function addEnquiry(text: string): Promise<number> {
  const id = await db.enquiries.add({ receivedAt: Date.now(), text: text.trim(), status: 'new', decision: {} });
  return id!;
}

export async function saveFacts(facts: TourFacts) {
  await db.kv.put({ key: 'facts', value: facts });
}

export async function getFacts(): Promise<TourFacts> {
  const row = await db.kv.get('facts');
  return { ...DEFAULT_FACTS, ...(row?.value as Partial<TourFacts> | undefined) };
}

/** undefined while loading. */
export function useFacts(): TourFacts | undefined {
  return useLiveQuery(getFacts);
}

export function useUnsentCount(): number {
  return useLiveQuery(() => db.outbox.filter((o) => !o.sentAt).count(), [], 0);
}

// --- Admin PIN: only a salted SHA-256 hash is stored ---

async function hashPin(pin: string, salt: string): Promise<string> {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${salt}:${pin}`));
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function useHasPin(): boolean | undefined {
  return useLiveQuery(async () => !!(await db.kv.get('pin')));
}

export async function setPin(pin: string) {
  const salt = crypto.randomUUID();
  await db.kv.put({ key: 'pin', value: { salt, hash: await hashPin(pin, salt) } });
}

export async function checkPin(pin: string): Promise<boolean> {
  const row = await db.kv.get('pin');
  if (!row) return true;
  const { salt, hash } = row.value as { salt: string; hash: string };
  return (await hashPin(pin, salt)) === hash;
}

// --- Export / wipe ---

export async function exportAll(): Promise<Blob> {
  const [enquiries, outbox, bookings, facts] = await Promise.all([
    db.enquiries.toArray(),
    db.outbox.toArray(),
    db.bookings.toArray(),
    getFacts(),
  ]);
  const data = { exportedAt: new Date().toISOString(), facts, enquiries, outbox, bookings };
  return new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
}

export async function wipeAll() {
  await db.delete();
}
