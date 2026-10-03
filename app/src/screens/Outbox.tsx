// Store-and-forward: approved replies wait here and open in WhatsApp/SMS once there's signal.
// The vendor taps send in that app, so nothing ever leaves without a human.
import { useLiveQuery } from 'dexie-react-hooks';
import { db, type OutboxItem } from '../db';
import { t } from '../content/ui';
import { useOnline } from '../hooks';

function sendLink(o: OutboxItem): string {
  const body = encodeURIComponent(o.text);
  if (o.channel === 'whatsapp') return `https://wa.me/${(o.to ?? '').replace(/\D/g, '')}?text=${body}`;
  return `sms:${(o.to ?? '').replace(/[^\d+]/g, '')}?body=${body}`;
}

export default function Outbox() {
  const online = useOnline();
  const unsent = useLiveQuery(() => db.outbox.orderBy('createdAt').filter((o) => !o.sentAt).toArray(), []);
  const sent = useLiveQuery(
    () => db.outbox.orderBy('createdAt').reverse().filter((o) => !!o.sentAt).limit(10).toArray(),
    [],
  );

  return (
    <section className="stack">
      <h2>📤 {t('outbox')}</h2>
      {!online && unsent && unsent.length > 0 && <p className="banner offline">📵 {t('offlineQueued')}</p>}
      {unsent?.length === 0 && <p className="muted center">{t('outboxEmpty')}</p>}

      {unsent?.map((o) => (
        <div key={o.id} className="card stack-sm">
          <div className="label">
            {o.channel === 'whatsapp' ? '💬 WhatsApp' : '✉️ SMS'} {o.to && `· ${o.to}`}
          </div>
          <p className="pre clamp">{o.text}</p>
          {online && (
            <div className="grid2">
              <a className="button primary" href={sendLink(o)} target="_blank" rel="noopener noreferrer">
                {o.channel === 'whatsapp' ? t('openWhatsApp') : t('openSms')}
              </a>
              <button className="secondary" onClick={() => db.outbox.update(o.id!, { sentAt: Date.now() })}>
                ✓ {t('markSent')}
              </button>
            </div>
          )}
        </div>
      ))}

      {sent && sent.length > 0 && (
        <>
          <div className="label">{t('sent')}</div>
          <ul className="list">
            {sent.map((o) => (
              <li key={o.id} className="row done">
                <span className="row-icons">✓</span>
                <span className="row-body">
                  <span className="row-text">{o.text}</span>
                  <span className="row-meta">
                    <time>{new Date(o.sentAt!).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</time>
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
