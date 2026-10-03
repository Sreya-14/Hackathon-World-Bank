import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { API_URL, loadListings } from './api';
import type { SavedArea } from './db';
import { Carousel, CategoryChips, DetailSheet, MenuSheet, TopBar } from './components';
import { useLang } from './i18n';
import MapView from './MapView';
import { getSavedArea, removeArea, saveArea, tilesUrl } from './tiles';
import type { Category, ListingCollection } from './types';

const REFRESH_MS = 30_000; // new pins appear without a reload

function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (cb) => {
      const m = matchMedia(query);
      m.addEventListener('change', cb);
      return () => m.removeEventListener('change', cb);
    },
    () => matchMedia(query).matches,
  );
}

function useOnline(): boolean {
  return useSyncExternalStore(
    (cb) => {
      addEventListener('online', cb);
      addEventListener('offline', cb);
      return () => (removeEventListener('online', cb), removeEventListener('offline', cb));
    },
    () => navigator.onLine,
  );
}

export default function App() {
  const lang = useLang();
  const online = useOnline();
  const dark = useMedia('(prefers-color-scheme: dark)');
  const [data, setData] = useState<ListingCollection>({ type: 'FeatureCollection', features: [] });
  const [category, setCategory] = useState<Category | 'all'>('all');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [saved, setSaved] = useState<SavedArea | undefined>();
  const [areaChecked, setAreaChecked] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [saveError, setSaveError] = useState(false);
  const [locateSignal, setLocateSignal] = useState(0);

  useEffect(() => {
    getSavedArea().then((a) => (setSaved(a), setAreaChecked(true)));
  }, []);

  const refresh = useCallback(() => {
    loadListings().then(({ data }) => setData(data)).catch((err) => console.warn('listings unavailable', err));
  }, []);

  useEffect(() => {
    refresh();
    if (!API_URL) return;
    const timer = setInterval(() => navigator.onLine && refresh(), REFRESH_MS);
    addEventListener('online', refresh);
    return () => (clearInterval(timer), removeEventListener('online', refresh));
  }, [refresh]);

  const tiles = useMemo(() => tilesUrl(saved), [saved]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: data.features.length };
    for (const f of data.features) c[f.properties.category] = (c[f.properties.category] ?? 0) + 1;
    return c;
  }, [data]);

  // Hosts with their porch light on (checked in recently) come first.
  const visible = useMemo(
    () =>
      data.features
        .filter((f) => category === 'all' || f.properties.category === category)
        .sort((a, b) => (a.properties.days_since_checkin ?? 99) - (b.properties.days_since_checkin ?? 99)),
    [data, category],
  );

  const select = useCallback((id: number | null) => {
    setSelectedId(id);
    setDetailOpen(id !== null);
  }, []);

  async function save() {
    setSaveError(false);
    setProgress(0);
    try {
      const area = await saveArea(setProgress);
      setSaved(area);
      refresh();
    } catch (err) {
      console.error(err);
      setSaveError(true);
    } finally {
      setProgress(null);
    }
  }

  async function remove() {
    await removeArea();
    setSaved(undefined);
  }

  const selected = data.features.find((f) => f.properties.id === selectedId) ?? null;

  return (
    <div className={`app ${detailOpen ? 'has-detail' : ''}`}>
      {areaChecked && (
        <MapView listings={visible} selectedId={selectedId} onSelect={select} tiles={tiles} dark={dark} lang={lang} locateSignal={locateSignal} />
      )}
      <div className="overlay-top">
        <TopBar online={online} offlineReady={!!saved} onMenu={() => setMenuOpen(true)} />
        <CategoryChips value={category} onChange={(c) => (setCategory(c), select(null))} counts={counts} />
      </div>
      <Carousel listings={visible} selectedId={selectedId} onOpen={select} onLocate={() => setLocateSignal((n) => n + 1)} />
      <DetailSheet listing={detailOpen ? selected : null} online={online} onClose={() => setDetailOpen(false)} />
      <MenuSheet open={menuOpen} onClose={() => setMenuOpen(false)} saved={saved} progress={progress} error={saveError} onSave={save} onRemove={remove} />
    </div>
  );
}
