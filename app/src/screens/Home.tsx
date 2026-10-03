import { useState } from 'react';
import { useLiveQuery } from 'dexie-react-hooks';
import { addEnquiry, db, useFacts, type Enquiry } from '../db';
import { missingFacts } from '../content/facts';
import { INTENT_UI, LANG_NAME, t } from '../content/ui';
import { intentsFor } from '../content/draft';
import { processPending } from '../pipeline';
import { go } from '../hooks';

export default function Home() {
  const facts = useFacts();
  const [text, setText] = useState('');
  const enquiries = useLiveQuery(
    () => db.enquiries.orderBy('receivedAt').reverse().filter((e) => e.status !== 'dismissed').toArray(),
    [],
  );

  async function add() {
    if (!text.trim()) return;
    const id = await addEnquiry(text);
    setText('');
    void processPending();
    go(`#/e/${id}`);
  }

  return (
    <section className="stack">
      {facts && missingFacts(facts).length > 0 && (
        <button className="banner" onClick={() => go('#/admin')}>
          ⚙️ {t('setupFirst')} →
        </button>
      )}

      <div className="card stack">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t('pastePlaceholder')}
          rows={3}
        />
        <button className="primary" onClick={add} disabled={!text.trim()}>
          📋 {t('add')}
        </button>
      </div>

      {enquiries?.length === 0 && <p className="muted center">{t('noMessages')}</p>}
      <ul className="list">
        {enquiries?.map((e) => <EnquiryRow key={e.id} e={e} />)}
      </ul>
    </section>
  );
}

function EnquiryRow({ e }: { e: Enquiry }) {
  const intents = intentsFor(e);
  const notSure = e.status === 'ready' && intents.length === 0;

  return (
    <li>
      <button className={`row ${e.status === 'replied' ? 'done' : ''}`} onClick={() => go(`#/e/${e.id}`)}>
        <span className="row-icons" aria-hidden>
          {e.status === 'new' ? '⏳' : notSure ? '❓' : intents.map((i) => INTENT_UI[i].icon).join('')}
        </span>
        <span className="row-body">
          <span className="row-text">{e.text}</span>
          <span className="row-meta">
            {e.understanding && <span className="chip">{LANG_NAME[e.understanding.lang]}</span>}
            {e.status === 'new' && t('understanding')}
            {notSure && <span className="chip warn">{t('notSure')}</span>}
            {e.status === 'replied' && <span className="chip ok">✓ {t('replied')}</span>}
            <time>{new Date(e.receivedAt).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</time>
          </span>
        </span>
      </button>
    </li>
  );
}
