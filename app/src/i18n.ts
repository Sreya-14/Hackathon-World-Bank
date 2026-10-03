import { useSyncExternalStore } from 'react';
import type { Category, Lang } from './types';

const STRINGS = {
  tagline: { en: 'Local hosts in Wayanad', de: 'Lokale Gastgeber in Wayanad' },
  all: { en: 'All', de: 'Alle' },
  placesNearby: { en: 'places to visit', de: 'Orte zum Besuchen' },
  placeNearby: { en: 'place to visit', de: 'Ort zum Besuchen' },
  noneInCategory: { en: 'Nothing in this category yet.', de: 'In dieser Kategorie gibt es noch nichts.' },
  lightOn: { en: 'Porch light on today', de: 'Heute geöffnet' },
  activeDaysAgo: { en: 'Active {n} days ago', de: 'Vor {n} Tagen aktiv' },
  activeYesterday: { en: 'Active yesterday', de: 'Gestern aktiv' },
  notActive: { en: 'Not checked in recently', de: 'Länger nicht aktiv' },
  verified: { en: 'Verified by a partner', de: 'Von Partner bestätigt' },
  sample: { en: 'Sample listing', de: 'Beispieleintrag' },
  sampleNote: { en: 'Demo data, not a real host. Contact is disabled.', de: 'Demodaten, kein echter Gastgeber. Kontakt deaktiviert.' },
  price: { en: 'Price', de: 'Preis' },
  hours: { en: 'Hours', de: 'Zeiten' },
  askHost: { en: 'Ask the host', de: 'Gastgeber fragen' },
  location: { en: 'Location', de: 'Ort' },
  exact: { en: 'Exact location', de: 'Genauer Ort' },
  area: { en: 'Approximate area (~{n} m). The host shares the exact spot when you message.', de: 'Ungefähre Gegend (~{n} m). Den genauen Ort teilt der Gastgeber auf Nachfrage.' },
  meeting: { en: 'Meeting point. The host meets you here.', de: 'Treffpunkt. Der Gastgeber holt Sie hier ab.' },
  interested: { en: "I'm interested", de: 'Ich habe Interesse' },
  interestedSub: { en: 'Opens WhatsApp with a greeting in Malayalam', de: 'Öffnet WhatsApp mit einem Gruß auf Malayalam' },
  offlineQueued: { en: 'WhatsApp will send it when you are back online.', de: 'WhatsApp sendet die Nachricht, sobald Sie wieder online sind.' },
  needsOnline: { en: 'Connect once to get this host’s contact.', de: 'Einmal online gehen, um den Kontakt zu laden.' },
  directions: { en: 'Directions', de: 'Route' },
  metCount: { en: '{n} travellers met this host', de: '{n} Reisende haben diesen Gastgeber getroffen' },
  metOne: { en: '1 traveller met this host', de: '1 Reisende(r) hat diesen Gastgeber getroffen' },
  iMet: { en: 'I met this host', de: 'Ich war dort' },
  thanks: { en: 'Thanks!', de: 'Danke!' },
  report: { en: 'Report a problem', de: 'Problem melden' },
  reported: { en: 'Reported. Thank you.', de: 'Gemeldet. Danke.' },
  reportConfirm: { en: 'Report this listing? Three reports hide it until a partner checks.', de: 'Diesen Eintrag melden? Nach drei Meldungen wird er ausgeblendet, bis ein Partner ihn prüft.' },
  close: { en: 'Close', de: 'Schließen' },
  online: { en: 'Online', de: 'Online' },
  offline: { en: 'Offline', de: 'Offline' },
  offlineMap: { en: 'Offline map', de: 'Offline-Karte' },
  saveArea: { en: 'Save Wayanad for offline', de: 'Wayanad offline speichern' },
  saveAreaSub: { en: 'Map and all listings, about {mb} MB. Works in airplane mode.', de: 'Karte und alle Einträge, ca. {mb} MB. Funktioniert im Flugmodus.' },
  saving: { en: 'Saving…', de: 'Wird gespeichert…' },
  saved: { en: 'Saved for offline', de: 'Offline gespeichert' },
  savedOn: { en: 'Saved {date}. Listings update when you are online.', de: 'Gespeichert am {date}. Einträge werden online aktualisiert.' },
  update: { en: 'Update', de: 'Aktualisieren' },
  remove: { en: 'Remove', de: 'Entfernen' },
  saveFailed: { en: 'Could not save. Check your connection and try again.', de: 'Speichern fehlgeschlagen. Verbindung prüfen und erneut versuchen.' },
  locateMe: { en: 'Show my location', de: 'Meinen Standort zeigen' },
  aboutTitle: { en: 'About Porchlight', de: 'Über Porchlight' },
  about: {
    en: 'Hosts describe their tour or craft in a WhatsApp voice note, in their own language. A small AI writes the listing; the host hears it read back and approves it before it appears here. Nothing is invented: prices and hours show only if the host said them.',
    de: 'Gastgeber beschreiben ihre Tour oder ihr Handwerk per WhatsApp-Sprachnachricht in ihrer eigenen Sprache. Eine kleine KI schreibt den Eintrag; der Gastgeber hört ihn sich an und gibt ihn frei, bevor er hier erscheint. Nichts wird erfunden: Preise und Zeiten erscheinen nur, wenn der Gastgeber sie genannt hat.',
  },
  aiNote: { en: 'Written by AI from the host’s voice note, approved by the host.', de: 'Von KI aus der Sprachnachricht erstellt, vom Gastgeber freigegeben.' },
} satisfies Record<string, Record<Lang, string>>;

export type StringKey = keyof typeof STRINGS;

export const CATEGORY: Record<Category, { icon: string; label: Record<Lang, string>; hue: number }> = {
  tour: { icon: '🌿', label: { en: 'Tours', de: 'Touren' }, hue: 140 },
  food: { icon: '🍛', label: { en: 'Food', de: 'Essen' }, hue: 25 },
  craft: { icon: '🧺', label: { en: 'Crafts', de: 'Handwerk' }, hue: 38 },
  textile: { icon: '🧵', label: { en: 'Textiles', de: 'Textilien' }, hue: 330 },
  experience: { icon: '✨', label: { en: 'Experiences', de: 'Erlebnisse' }, hue: 265 },
  other: { icon: '📍', label: { en: 'Other', de: 'Sonstiges' }, hue: 210 },
};

// --- Language store (a per-device preference, so localStorage is fine) ---

const KEY = 'porchlight.lang';
let current: Lang = (() => {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === 'en' || saved === 'de') return saved;
  } catch {
    /* storage blocked */
  }
  return navigator.language.toLowerCase().startsWith('de') ? 'de' : 'en';
})();
const listeners = new Set<() => void>();

export function setLang(lang: Lang) {
  current = lang;
  document.documentElement.lang = lang;
  try {
    localStorage.setItem(KEY, lang);
  } catch {
    /* keep in memory */
  }
  listeners.forEach((l) => l());
}

export function useLang(): Lang {
  return useSyncExternalStore((l) => (listeners.add(l), () => listeners.delete(l)), () => current);
}

export function useT() {
  const lang = useLang();
  const t = (k: StringKey, vars: Record<string, string | number> = {}) =>
    STRINGS[k][lang].replace(/\{(\w+)\}/g, (_, v) => String(vars[v] ?? ''));
  return { lang, t };
}

export const initialLang = () => current;
