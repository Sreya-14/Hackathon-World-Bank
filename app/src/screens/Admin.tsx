// Admin: tour facts, PIN, export and wipe. Same phone, guarded by an optional PIN.
import { useEffect, useState } from 'react';
import { LANGS } from '../engine';
import { checkPin, exportAll, saveFacts, setPin, useFacts, useHasPin, wipeAll } from '../db';
import { CURRENCIES, type TourFacts, type Weekday } from '../content/facts';
import { fmt } from '../content/format';
import { LANG_NAME, t, type StringKey } from '../content/ui';

// Stays unlocked until the vendor taps Lock or the app reloads.
let unlockedThisSession = false;

export default function Admin() {
  const hasPin = useHasPin();
  const [unlocked, setUnlocked] = useState(unlockedThisSession);

  const unlock = () => setUnlocked((unlockedThisSession = true));

  if (hasPin === undefined) return null;
  if (hasPin && !unlocked) return <PinGate onUnlock={unlock} />;
  return (
    <section className="stack">
      <GuestLanguages />
      <TourForm />
      {/* Setting a PIN keeps this session open; it locks on Lock or reload. */}
      <PinSection hasPin={hasPin} onPinSet={unlock} onLock={() => setUnlocked((unlockedThisSession = false))} />
      <DataSection />
    </section>
  );
}

function PinGate({ onUnlock }: { onUnlock: () => void }) {
  const [pin, setPinValue] = useState('');
  const [wrong, setWrong] = useState(false);

  async function submit(ev: React.FormEvent) {
    ev.preventDefault();
    if (await checkPin(pin)) onUnlock();
    else {
      setWrong(true);
      setPinValue('');
    }
  }

  return (
    <form className="card stack center-col" onSubmit={submit}>
      <div className="big">🔒 {t('enterPin')}</div>
      <input
        type="password"
        inputMode="numeric"
        autoComplete="off"
        className="pin"
        value={pin}
        onChange={(e) => setPinValue(e.target.value.replace(/\D/g, ''))}
        autoFocus
      />
      {wrong && <p className="warn-text">{t('wrongPin')}</p>}
      <button className="primary" disabled={pin.length < 4}>
        {t('unlock')}
      </button>
    </form>
  );
}

/** Which guest languages are covered; anything else goes to "not sure". */
function GuestLanguages() {
  return (
    <div className="card stack-sm">
      <div className="label">🌐 {t('guestLanguages')}</div>
      <div className="chips">
        {LANGS.map((l) => (
          <span key={l} className="chip">
            {LANG_NAME[l]}
          </span>
        ))}
      </div>
      <p className="muted">{t('guestLanguagesNote')}</p>
    </div>
  );
}

const MONDAY_FIRST: Weekday[] = [1, 2, 3, 4, 5, 6, 0];

function TourForm() {
  const facts = useFacts();
  const [draft, setDraft] = useState<TourFacts | undefined>();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (facts && !draft) setDraft(facts);
  }, [facts, draft]);
  if (!draft) return null;

  const f = fmt('en');
  const set = (patch: Partial<TourFacts>) => {
    setDraft({ ...draft, ...patch });
    setSaved(false);
  };
  const toggleDay = (d: Weekday) =>
    set({ days: draft.days.includes(d) ? draft.days.filter((x) => x !== d) : [...draft.days, d] });

  const check = <G extends 'included' | 'payment'>(group: G, k: keyof TourFacts[G] & StringKey) => {
    const value = draft[group][k] as boolean;
    return (
      <label key={k} className="check">
        <input type="checkbox" checked={value} onChange={() => set({ [group]: { ...draft[group], [k]: !value } })} />
        {t(k)}
      </label>
    );
  };

  async function save() {
    await saveFacts(draft!);
    setSaved(true);
  }

  return (
    <div className="card stack-sm">
      <h2>🧾 {t('tourDetails')}</h2>

      <label>
        {t('vendorName')}
        <input value={draft.vendorName} onChange={(e) => set({ vendorName: e.target.value })} />
      </label>

      <div className="grid2">
        <label>
          {t('price')}
          <input type="number" min={0} inputMode="numeric" value={draft.price || ''} onChange={(e) => set({ price: Number(e.target.value) })} />
        </label>
        <label>
          &nbsp;
          <select value={draft.currency} onChange={(e) => set({ currency: e.target.value as TourFacts['currency'] })}>
            {CURRENCIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="label">{t('days')}</div>
      <div className="chips">
        {MONDAY_FIRST.map((d) => (
          <button key={d} className={`intent ${draft.days.includes(d) ? 'on' : ''}`} onClick={() => toggleDay(d)} aria-pressed={draft.days.includes(d)}>
            {f.weekday(d)}
          </button>
        ))}
      </div>

      <div className="grid3">
        <label>
          {t('startTime')}
          <input type="time" value={draft.startTime} onChange={(e) => set({ startTime: e.target.value })} />
        </label>
        <label>
          {t('duration')}
          <input type="number" min={0.5} step={0.5} value={draft.durationHours || ''} onChange={(e) => set({ durationHours: Number(e.target.value) })} />
        </label>
        <label>
          {t('maxGroup')}
          <input type="number" min={1} value={draft.maxGroup || ''} onChange={(e) => set({ maxGroup: Number(e.target.value) })} />
        </label>
      </div>

      <label>
        {t('meetingPoint')}
        <input value={draft.meetingPoint} onChange={(e) => set({ meetingPoint: e.target.value })} />
      </label>
      <label>
        {t('mapsLink')}
        <input type="url" inputMode="url" value={draft.mapsLink} onChange={(e) => set({ mapsLink: e.target.value })} placeholder="https://maps.app.goo.gl/…" />
      </label>

      <div className="label">{t('included')}</div>
      <div className="checks">{(['coffeeTasting', 'lunch', 'guide', 'transport'] as const).map((k) => check('included', k))}</div>

      <div className="label">{t('canOffer')}</div>
      <div className="checks">
        {(['vegetarian', 'kidsWelcome', 'wheelchair'] as const).map((k) => (
          <label key={k} className="check">
            <input type="checkbox" checked={draft[k]} onChange={() => set({ [k]: !draft[k] })} />
            {t(k === 'kidsWelcome' ? 'kids' : k)}
          </label>
        ))}
      </div>

      <div className="label">{t('payment')}</div>
      <div className="checks">{(['cash', 'upi', 'card'] as const).map((k) => check('payment', k))}</div>

      <button className="primary big" onClick={save}>
        {saved ? `✓ ${t('saved')}` : `💾 ${t('save')}`}
      </button>
    </div>
  );
}

function PinSection({ hasPin, onPinSet, onLock }: { hasPin: boolean; onPinSet: () => void; onLock: () => void }) {
  const [pin, setPinValue] = useState('');
  const [saved, setSaved] = useState(false);

  async function save() {
    onPinSet();
    await setPin(pin);
    setPinValue('');
    setSaved(true);
  }

  return (
    <div className="card stack-sm">
      <h2>🔒 {t('adminPin')}</h2>
      {!hasPin && <p className="warn-text">{t('noPinYet')}</p>}
      <label>
        {t('setPin')}
        <input
          type="password"
          inputMode="numeric"
          autoComplete="new-password"
          value={pin}
          onChange={(e) => {
            setPinValue(e.target.value.replace(/\D/g, ''));
            setSaved(false);
          }}
        />
      </label>
      <div className="grid2">
        <button className="secondary" onClick={save} disabled={pin.length < 4}>
          {saved ? `✓ ${t('saved')}` : t('save')}
        </button>
        {hasPin && (
          <button className="secondary" onClick={onLock}>
            🔒 {t('lock')}
          </button>
        )}
      </div>
    </div>
  );
}

function DataSection() {

  async function download() {
    const url = URL.createObjectURL(await exportAll());
    const a = document.createElement('a');
    a.href = url;
    a.download = `tour-assistant-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function wipe() {
    if (!confirm(t('wipeConfirm'))) return;
    await wipeAll();
    location.replace(import.meta.env.BASE_URL);
  }

  return (
    <div className="card stack-sm">
      <h2>🗄 {t('yourData')}</h2>
      <p className="muted">{t('dataOnPhone')}</p>
      <button className="secondary" onClick={download}>
        ⬇️ {t('exportData')}
      </button>
      <button className="secondary danger" onClick={wipe}>
        🗑 {t('wipeData')}
      </button>
    </div>
  );
}
