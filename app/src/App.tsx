import { useEffect, useState } from 'react';
import { getEngine, type LoadProgress } from './engine';
import { useUnsentCount } from './db';
import { processPending } from './pipeline';
import { t, type StringKey } from './content/ui';
import { go, useOnline, useRoute } from './hooks';
import Home from './screens/Home';
import EnquiryScreen from './screens/Enquiry';
import Outbox from './screens/Outbox';
import Bookings from './screens/Bookings';
import Admin from './screens/Admin';

export default function App() {
  const route = useRoute();
  const online = useOnline();
  const unsent = useUnsentCount();
  const [progress, setProgress] = useState<LoadProgress | null>(null);
  const [ready, setReady] = useState(getEngine().ready().core);

  useEffect(() => {
    const engine = getEngine();
    if (engine.ready().core) return;
    engine
      .loadCore(setProgress)
      .then(() => {
        setReady(true);
        return processPending();
      })
      .catch((err) => console.error('loadCore failed', err));
  }, []);

  return (
    <div className="app">
      <header className="top">
        <strong>{t('appName')}</strong>
        <span className="status">
          <span className={`dot ${online ? 'on' : 'off'}`} />
          {online ? 'Online' : 'Offline'}
        </span>
      </header>

      <main>
        {!ready ? (
          <div className="preparing">
            <div className="big">☕</div>
            <p>{t('preparing')}</p>
            <progress max={1} value={progress?.progress ?? 0} />
          </div>
        ) : route.name === 'enquiry' ? (
          <EnquiryScreen id={route.id} />
        ) : route.name === 'outbox' ? (
          <Outbox />
        ) : route.name === 'bookings' ? (
          <Bookings />
        ) : route.name === 'admin' ? (
          <Admin />
        ) : (
          <Home />
        )}
      </main>

      <nav className="tabs">
        <Tab icon="💬" label="messages" path="#/" active={route.name === 'home' || route.name === 'enquiry'} />
        <Tab icon="📤" label="outbox" path="#/outbox" active={route.name === 'outbox'} badge={unsent} />
        <Tab icon="📒" label="bookings" path="#/bookings" active={route.name === 'bookings'} />
        <Tab icon="⚙️" label="admin" path="#/admin" active={route.name === 'admin'} />
      </nav>
    </div>
  );
}

function Tab({ icon, label, path, active, badge }: { icon: string; label: StringKey; path: string; active: boolean; badge?: number }) {
  return (
    <button className={`tab ${active ? 'on' : ''}`} onClick={() => go(path)} aria-current={active ? 'page' : undefined}>
      <span className="tab-icon" aria-hidden>
        {icon}
        {!!badge && <span className="badge">{badge}</span>}
      </span>
      <span className="tab-label">{t(label)}</span>
    </button>
  );
}
