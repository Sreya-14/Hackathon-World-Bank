import { useLiveQuery } from 'dexie-react-hooks';
import { db, useFacts, type Booking } from '../db';
import { fmt } from '../content/format';
import { t } from '../content/ui';
import { go } from '../hooks';

export default function Bookings() {
  const bookings = useLiveQuery(() => db.bookings.orderBy('date').toArray(), []);
  const today = new Date().setHours(0, 0, 0, 0);
  const upcoming = bookings?.filter((b) => b.date >= today) ?? [];
  const past = (bookings?.filter((b) => b.date < today) ?? []).reverse();

  return (
    <section className="stack">
      <h2>📒 {t('bookings')}</h2>
      {bookings?.length === 0 && <p className="muted center">{t('noBookings')}</p>}
      {upcoming.length > 0 && <BookingList title={t('upcoming')} items={upcoming} />}
      {past.length > 0 && <BookingList title={t('past')} items={past} done />}
    </section>
  );
}

function BookingList({ title, items, done }: { title: string; items: Booking[]; done?: boolean }) {
  const facts = useFacts();
  const f = fmt('en');
  return (
    <>
      <div className="label">{title}</div>
      <ul className="list">
        {items.map((b) => (
          <li key={b.id}>
            <button className={`row ${done ? 'done' : ''}`} onClick={() => go(`#/e/${b.enquiryId}`)}>
              <span className="row-icons">📅</span>
              <span className="row-body">
                <span className="row-text strong">
                  {f.date(new Date(b.date))}
                  {facts && ` · ${facts.startTime}`}
                </span>
                <span className="row-meta">
                  {b.groupSize && <span className="chip">👥 {b.groupSize} {t('people')}</span>}
                  {b.guestPhone && <span>📞 {b.guestPhone}</span>}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
