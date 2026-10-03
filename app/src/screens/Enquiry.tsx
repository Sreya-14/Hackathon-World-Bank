import { useState } from 'react';
import { useLiveQuery } from 'dexie-react-hooks';
import { INTENTS, type IntentId } from '../engine';
import { db, useFacts, type Channel, type Decision, type Enquiry } from '../db';
import { missingFacts, type TourFacts } from '../content/facts';
import { composeReply, defaultOpen, draftCtx, guestLang, intentsFor } from '../content/draft';
import { INTENT_UI, LANG_NAME, NOT_SURE_UI, summary, t } from '../content/ui';
import { go } from '../hooks';

const toInputDate = (ms?: number) => {
  if (!ms) return '';
  const d = new Date(ms);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const fromInputDate = (s: string) => {
  if (!s) return undefined;
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d).getTime();
};

export default function EnquiryScreen({ id }: { id: number }) {
  const e = useLiveQuery(() => db.enquiries.get(id).then((x) => x ?? null), [id]);
  const facts = useFacts();

  if (e === undefined || !facts) return <p className="muted center">…</p>;
  if (e === null) {
    return (
      <button className="link" onClick={() => go('#/')}>
        ← {t('back')}
      </button>
    );
  }
  return <EnquiryView e={e} facts={facts} />;
}

function EnquiryView({ e, facts }: { e: Enquiry; facts: TourFacts }) {
  const [callYou, setCallYou] = useState(false);
  const [channel, setChannel] = useState<Channel>('whatsapp');

  const u = e.understanding;
  const intents = intentsFor(e);
  const ctx = draftCtx(e, facts);
  const replied = e.status === 'replied';
  const notSure = u?.status === 'not_sure' && !e.decision.intents;
  const needsDecision = intents.includes('availability') || intents.includes('booking');
  const factsReady = missingFacts(facts).length === 0;
  const canDraft = factsReady && (callYou || intents.length > 0);
  const gLang = guestLang(e);

  const setDecision = (patch: Partial<Decision>) => db.enquiries.update(e.id!, { decision: { ...e.decision, ...patch } });

  function setDateOrSize(patch: Pick<Decision, 'date' | 'groupSize'>) {
    const next = { ...e.decision, ...patch };
    const open = defaultOpen(next.date ? new Date(next.date) : undefined, next.groupSize, facts);
    void setDecision({ ...patch, open });
  }

  function toggleIntent(i: IntentId) {
    setCallYou(false);
    void setDecision({ intents: intents.includes(i) ? intents.filter((x) => x !== i) : [...intents, i] });
  }

  async function approve() {
    const text = composeReply(intents, ctx, gLang, { callYou });
    await db.transaction('rw', db.enquiries, db.outbox, db.bookings, async () => {
      await db.outbox.add({ enquiryId: e.id!, channel, to: e.guestPhone, text, createdAt: Date.now() });
      if (!callYou && intents.includes('booking') && e.decision.open && e.decision.date) {
        await db.bookings.add({
          enquiryId: e.id!,
          date: e.decision.date,
          groupSize: e.decision.groupSize,
          guestPhone: e.guestPhone,
          createdAt: Date.now(),
        });
      }
      await db.enquiries.update(e.id!, { status: 'replied' });
    });
    go('#/outbox');
  }

  async function dismiss() {
    await db.enquiries.update(e.id!, { status: 'dismissed' });
    go('#/');
  }

  const date = ctx.date;
  const notTourDay = date && !facts.days.includes(date.getDay() as TourFacts['days'][number]);
  const overMax = ctx.groupSize !== undefined && ctx.groupSize > facts.maxGroup;
  // English machine translation for the vendor; not needed when the guest wrote in English.
  const translation = u && u.lang !== 'en' ? u.english : undefined;

  return (
    <section className="stack">
      <button className="link" onClick={() => go('#/')}>
        ← {t('back')}
      </button>

      <div className="card stack-sm">
        <div className="label">
          {t('original')} {u && <span className="chip">{LANG_NAME[u.lang]}</span>}
        </div>
        <p className="original">{e.text}</p>
        {translation && (
          <div className="mt">
            <div className="label">⚠️ {t('machineTranslated')}</div>
            <p>{translation}</p>
          </div>
        )}
      </div>

      {e.status === 'new' && <p className="muted center">⏳ {t('understanding')}</p>}

      {u && (
        <>
          {notSure && u.reason && (
            <div className="card notsure stack-sm">
              <div className="big">❓ {t('notSure')}</div>
              <p>{NOT_SURE_UI[u.reason]}</p>
              <p className="strong">{t('pleaseDecide')}</p>
            </div>
          )}

          {intents.length > 0 && (
            <div className="card stack-sm">
              <div className="label">{t('guestAsks')}</div>
              {intents.map((i) => (
                <p key={i} className="summary">
                  <span className="icon" aria-hidden>{INTENT_UI[i].icon}</span>
                  {summary(i, ctx)}
                </p>
              ))}
            </div>
          )}

          {!replied && (
            <div className="stack-sm">
              {notSure && <div className="label">{t('pickTopic')}</div>}
              <div className="chips">
                {INTENTS.map((i) => (
                  <button
                    key={i}
                    className={`intent ${intents.includes(i) ? 'on' : ''}`}
                    onClick={() => toggleIntent(i)}
                    aria-pressed={intents.includes(i)}
                  >
                    <span aria-hidden>{INTENT_UI[i].icon}</span> {INTENT_UI[i].label}
                  </button>
                ))}
              </div>
              {notSure && (
                <button className={`secondary ${callYou ? 'on' : ''}`} onClick={() => setCallYou(!callYou)}>
                  📞 {t('callYouInstead')}
                </button>
              )}
            </div>
          )}

          {needsDecision && !callYou && !replied && (
            <div className="card stack-sm">
              <div className="grid2">
                <label>
                  {t('date')}
                  <input
                    type="date"
                    value={toInputDate(e.decision.date)}
                    onChange={(ev) => setDateOrSize({ date: fromInputDate(ev.target.value) })}
                  />
                </label>
                <label>
                  {t('people')}
                  <input
                    type="number"
                    min={1}
                    inputMode="numeric"
                    value={e.decision.groupSize ?? ''}
                    onChange={(ev) => setDateOrSize({ groupSize: ev.target.value ? Number(ev.target.value) : undefined })}
                  />
                </label>
              </div>
              {notTourDay && <p className="warn-text">⚠️ {t('notTourDay')}</p>}
              {overMax && <p className="warn-text">⚠️ {t('overMax')} ({facts.maxGroup})</p>}
              {date && (
                <div className="grid2">
                  <button className={`yes ${e.decision.open === true ? 'on' : ''}`} onClick={() => setDecision({ open: true })}>
                    ✅ {t('yesOpen')}
                  </button>
                  <button className={`no ${e.decision.open === false ? 'on' : ''}`} onClick={() => setDecision({ open: false })}>
                    ❌ {t('noClosed')}
                  </button>
                </div>
              )}
            </div>
          )}

          {!factsReady && (
            <button className="banner" onClick={() => go('#/admin')}>
              ⚙️ {t('setupFirst')} →
            </button>
          )}

          {canDraft && !replied && (
            <div className="card stack-sm reply">
              <div className="label">{t('yourReply')}</div>
              <p className="pre">{composeReply(intents, ctx, 'en', { callYou })}</p>
              {gLang !== 'en' && (
                <details>
                  <summary>
                    {t('guestWillGet')}: {LANG_NAME[gLang]}
                  </summary>
                  <p className="pre">{composeReply(intents, ctx, gLang, { callYou })}</p>
                </details>
              )}

              <label>
                {t('guestPhone')}
                <input
                  type="tel"
                  inputMode="tel"
                  placeholder="+91…"
                  value={e.guestPhone ?? ''}
                  onChange={(ev) => db.enquiries.update(e.id!, { guestPhone: ev.target.value })}
                />
              </label>
              <div className="label">{t('sendVia')}</div>
              <div className="grid2">
                <button className={`secondary ${channel === 'whatsapp' ? 'on' : ''}`} onClick={() => setChannel('whatsapp')}>
                  💬 WhatsApp
                </button>
                <button className={`secondary ${channel === 'sms' ? 'on' : ''}`} onClick={() => setChannel('sms')}>
                  ✉️ SMS
                </button>
              </div>
              <button className="primary big" onClick={approve}>
                👍 {t('approve')}
              </button>
            </div>
          )}

          {replied && <p className="chip ok center">✓ {t('replied')}</p>}
          {!replied && (
            <button className="link danger" onClick={dismiss}>
              🗑 {t('dismiss')}
            </button>
          )}
        </>
      )}
    </section>
  );
}
