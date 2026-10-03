import { useEffect, useRef, useState, type ReactNode } from 'react';
import { contactLink, sendFeedback } from './api';
import { getMarked, mark, type SavedArea } from './db';
import { CATEGORY, setLang, useT } from './i18n';
import { AREA_MB } from './tiles';
import type { Category, Lang, Listing, ListingProps } from './types';

// --- Small pieces -------------------------------------------------------------------

export function Thumb({ p, large }: { p: ListingProps; large?: boolean }) {
  const cat = CATEGORY[p.category];
  return (
    <div className={`thumb ${large ? 'thumb-lg' : ''}`} style={{ ['--hue' as string]: cat.hue }}>
      {p.photo_url ? <img src={p.photo_url} alt="" loading="lazy" /> : <span aria-hidden>{cat.icon}</span>}
    </div>
  );
}

export function Activity({ p }: { p: ListingProps }) {
  const { t } = useT();
  const d = p.days_since_checkin;
  if (d !== null && d < 1)
    return (
      <span className="activity on">
        <span className="dot" /> {t('lightOn')}
      </span>
    );
  if (d !== null && d < 2) return <span className="activity">{t('activeYesterday')}</span>;
  if (d !== null && d <= 7) return <span className="activity">{t('activeDaysAgo', { n: Math.floor(d) })}</span>;
  return <span className="activity stale">{t('notActive')}</span>;
}

function Sheet({ open, onClose, label, children, className = '' }: { open: boolean; onClose: () => void; label: string; children: ReactNode; className?: string }) {
  const { t } = useT();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    addEventListener('keydown', onKey);
    return () => removeEventListener('keydown', onKey);
  }, [open, onClose]);
  return (
    <div className={`sheet-layer ${open ? 'open' : ''}`} aria-hidden={!open}>
      <div className="backdrop" onClick={onClose} />
      <section className={`sheet ${className}`} role="dialog" aria-modal="true" aria-label={label}>
        <div className="grabber" aria-hidden />
        <button className="icon-btn sheet-close" onClick={onClose} aria-label={t('close')}>
          ✕
        </button>
        {open && children}
      </section>
    </div>
  );
}

// --- Top bar -------------------------------------------------------------------------

export function TopBar({ online, offlineReady, onMenu }: { online: boolean; offlineReady: boolean; onMenu: () => void }) {
  const { t, lang } = useT();
  return (
    <header className="topbar">
      <button className="brand" onClick={onMenu} aria-label={t('aboutTitle')}>
        <span className="logo" aria-hidden>
          <svg viewBox="0 0 32 32"><circle cx="16" cy="13" r="7" /><path d="M16 30c-1-4-9-9-9-17a9 9 0 0 1 18 0c0 8-8 13-9 17z" /></svg>
        </span>
        <span className="brand-text">
          <strong>Lantern</strong>
          <small>{t('tagline')}</small>
        </span>
      </button>
      <div className="topbar-actions">
        <button className={`status ${online ? 'is-online' : 'is-offline'}`} onClick={onMenu}>
          <span className="dot" />
          {online ? t('online') : t('offline')}
          {offlineReady && <span title={t('saved')}> · ✓</span>}
        </button>
        <div className="segmented" role="group" aria-label="Language">
          {(['en', 'de'] as Lang[]).map((l) => (
            <button key={l} className={l === lang ? 'on' : ''} onClick={() => setLang(l)} aria-pressed={l === lang}>
              {l.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}

export function CategoryChips({ value, onChange, counts }: { value: Category | 'all'; onChange: (c: Category | 'all') => void; counts: Record<string, number> }) {
  const { t, lang } = useT();
  const cats = (Object.keys(CATEGORY) as Category[]).filter((c) => counts[c]);
  return (
    <nav className="chips" aria-label="Categories">
      <button className={value === 'all' ? 'on' : ''} onClick={() => onChange('all')}>
        {t('all')} <span className="count">{counts.all ?? 0}</span>
      </button>
      {cats.map((c) => (
        <button key={c} className={value === c ? 'on' : ''} onClick={() => onChange(c)} style={{ ['--hue' as string]: CATEGORY[c].hue }}>
          <span aria-hidden>{CATEGORY[c].icon}</span> {CATEGORY[c].label[lang]}
        </button>
      ))}
    </nav>
  );
}

// --- Bottom carousel -----------------------------------------------------------------

export function Carousel({ listings, selectedId, onOpen, onLocate }: { listings: Listing[]; selectedId: number | null; onOpen: (id: number) => void; onLocate: () => void }) {
  const { t, lang } = useT();
  const track = useRef<HTMLDivElement>(null);

  useEffect(() => {
    track.current?.querySelector(`[data-id="${selectedId}"]`)?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }, [selectedId]);

  return (
    <div className="carousel">
      <div className="carousel-head">
        <span>
          <strong>{listings.length}</strong> {listings.length === 1 ? t('placeNearby') : t('placesNearby')}
        </span>
        <button className="fab" onClick={onLocate} aria-label={t('locateMe')} title={t('locateMe')}>
          <svg viewBox="0 0 24 24" aria-hidden><circle cx="12" cy="12" r="3.2" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /><circle cx="12" cy="12" r="7" fill="none" /></svg>
        </button>
      </div>
      {listings.length === 0 ? (
        <p className="empty">{t('noneInCategory')}</p>
      ) : (
        <div className="track" ref={track}>
          {listings.map(({ properties: p }) => (
            <button key={p.id} data-id={p.id} className={`card ${p.id === selectedId ? 'is-selected' : ''}`} onClick={() => onOpen(p.id)}>
              <Thumb p={p} />
              <span className="card-body">
                <span className="card-cat">
                  {CATEGORY[p.category].label[lang]}
                  {p.seed && <span className="tag">{t('sample')}</span>}
                </span>
                <span className="card-title">{p.title[lang]}</span>
                <Activity p={p} />
                {p.price && <span className="card-price">{p.price}</span>}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Listing detail ------------------------------------------------------------------

export function DetailSheet({ listing, online, onClose }: { listing: Listing | null; online: boolean; onClose: () => void }) {
  const { t, lang } = useT();
  const p = listing?.properties;
  const [met, setMet] = useState(false);
  const [reported, setReported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!p) return;
    setNote(null);
    Promise.all([getMarked('met'), getMarked('reported')]).then(([m, r]) => {
      setMet(m.includes(p.id));
      setReported(r.includes(p.id));
    });
  }, [p?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function contact() {
    if (!p) return;
    setBusy(true);
    const url = await contactLink(p.id, p.whatsapp_url);
    setBusy(false);
    if (!url) return setNote(t('needsOnline'));
    if (!online) setNote(t('offlineQueued'));
    window.open(url, '_blank', 'noopener');
  }

  async function iMet() {
    if (!p || met) return;
    setMet(true);
    await mark('met', p.id);
    await sendFeedback(p.id, 'met');
  }

  async function report() {
    if (!p || reported || !confirm(t('reportConfirm'))) return;
    setReported(true);
    await mark('reported', p.id);
    await sendFeedback(p.id, 'report');
  }

  const [lon, lat] = listing?.geometry.coordinates ?? [0, 0];
  const metCount = (p?.met_count ?? 0) + (met ? 1 : 0);

  return (
    <Sheet open={!!listing} onClose={onClose} label={p?.title[lang] ?? ''} className="detail">
      {p && (
        <>
          <Thumb p={p} large />
          <div className="detail-body">
            <div className="detail-tags">
              <span className="pill" style={{ ['--hue' as string]: CATEGORY[p.category].hue }}>
                {CATEGORY[p.category].icon} {CATEGORY[p.category].label[lang]}
              </span>
              {p.verified && <span className="pill ok">✓ {t('verified')}</span>}
              {p.seed && <span className="pill warn">{t('sample')}</span>}
            </div>
            <h2>{p.title[lang]}</h2>
            <Activity p={p} />
            <p className="desc">{p.description[lang]}</p>
            <p className="ai-note">
              🤖 {t('aiNote')}
              {p.machine_translated?.includes(lang) && ` ${t('machineTranslated')}`}
            </p>

            {!!p.includes?.[lang]?.length && (
              <div className="includes">
                <span className="includes-label">{t('includes')}</span>
                {p.includes[lang].map((item) => (
                  <span key={item} className="pill">✓ {item}</span>
                ))}
              </div>
            )}

            <dl className="facts">
              <div>
                <dt>{t('price')}</dt>
                <dd>{p.price ?? <span className="muted">{t('askHost')}</span>}</dd>
              </div>
              <div>
                <dt>{t('hours')}</dt>
                <dd>{p.hours ?? <span className="muted">{t('askHost')}</span>}</dd>
              </div>
              {p.duration && (
                <div className="wide">
                  <dt>{t('duration')}</dt>
                  <dd>{p.duration}</dd>
                </div>
              )}
              <div className="wide">
                <dt>{t('location')}</dt>
                <dd>
                  {p.privacy === 'area' ? `◌ ${t('area', { n: p.radius_m ?? 200 })}` : p.privacy === 'meeting' ? `🚩 ${t('meeting')}` : `📍 ${t('exact')}`}
                  {p.meeting_point?.[lang] && <span className="meeting-note">“{p.meeting_point[lang]}”</span>}
                </dd>
              </div>
            </dl>

            {p.seed ? (
              <p className="notice">{t('sampleNote')}</p>
            ) : (
              <button className="cta" onClick={contact} disabled={busy}>
                <svg viewBox="0 0 24 24" aria-hidden><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm5.3 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.5-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.8s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.3.5-.4.4c-.1.2-.3.3-.1.6.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.3 2.4 1.5.3.1.5.1.6-.1l.9-1c.2-.3.4-.2.6-.1l1.9.9c.3.1.5.2.5.3.1.2.1.7-.1 1.2z" /></svg>
                <span>
                  <strong>{t('interested')}</strong>
                  <small>{t('interestedSub')}</small>
                </span>
              </button>
            )}
            {note && <p className="notice">{note}</p>}

            <div className="row-actions">
              <a className="ghost" href={`geo:${lat},${lon}?q=${lat},${lon}`}>🧭 {t('directions')}</a>
              <button className="ghost" onClick={iMet} disabled={met || p.seed}>
                🤝 {met ? t('thanks') : t('iMet')}
              </button>
            </div>
            {metCount > 0 && <p className="muted small">{metCount === 1 ? t('metOne') : t('metCount', { n: metCount })}</p>}
            {!p.seed && (
              <button className="link" onClick={report} disabled={reported}>
                {reported ? t('reported') : t('report')}
              </button>
            )}
          </div>
        </>
      )}
    </Sheet>
  );
}

// --- Offline + about ------------------------------------------------------------------

export function MenuSheet({ open, onClose, saved, progress, error, onSave, onRemove }: {
  open: boolean; onClose: () => void; saved?: SavedArea; progress: number | null; error: boolean; onSave: () => void; onRemove: () => void;
}) {
  const { t, lang } = useT();
  const date = saved ? new Date(saved.savedAt).toLocaleDateString(lang, { day: 'numeric', month: 'short', year: 'numeric' }) : '';
  return (
    <Sheet open={open} onClose={onClose} label={t('offlineMap')} className="menu">
      <div className="detail-body">
        <h2>{t('offlineMap')}</h2>
        <div className={`offline-card ${saved ? 'is-saved' : ''}`}>
          <div className="offline-icon" aria-hidden>{saved ? '✓' : '⤓'}</div>
          <div>
            <strong>{saved ? t('saved') : t('saveArea')}</strong>
            <p className="muted small">{saved ? t('savedOn', { date }) : t('saveAreaSub', { mb: AREA_MB })}</p>
          </div>
        </div>
        {progress !== null ? (
          <div className="progress" role="progressbar" aria-valuenow={Math.round(progress * 100)}>
            <span style={{ width: `${progress * 100}%` }} />
            <em>{t('saving')} {Math.round(progress * 100)}%</em>
          </div>
        ) : saved ? (
          <div className="row-actions">
            <button className="ghost" onClick={onSave}>↻ {t('update')}</button>
            <button className="ghost" onClick={onRemove}>🗑 {t('remove')}</button>
          </div>
        ) : (
          <button className="cta cta-plain" onClick={onSave}>⤓ {t('saveArea')}</button>
        )}
        {error && <p className="notice">{t('saveFailed')}</p>}

        <h2 className="mt">{t('aboutTitle')}</h2>
        <p className="desc">{t('about')}</p>
      </div>
    </Sheet>
  );
}
