// Locale formatting via Intl, so weekday names, dates, lists and money need no hand translation.
import type { Lang } from '../engine';
import type { Currency, Weekday } from './facts';

export type { Lang };

// 2023-01-01 was a Sunday, so day n of that week has getDay() === n.
const weekdayDate = (d: Weekday) => new Date(2023, 0, 1 + d);

export function fmt(lang: Lang) {
  const list = new Intl.ListFormat(lang, { type: 'conjunction' });
  const orList = new Intl.ListFormat(lang, { type: 'disjunction' });
  const dayName = new Intl.DateTimeFormat(lang, { weekday: 'long' });
  const weekday = (d: Weekday) => dayName.format(weekdayDate(d));
  return {
    and: (items: string[]) => list.format(items),
    or: (items: string[]) => orList.format(items),
    money: (n: number, currency: Currency) =>
      new Intl.NumberFormat(lang, { style: 'currency', currency, maximumFractionDigits: 0 }).format(n),
    num: (n: number) => new Intl.NumberFormat(lang, { maximumFractionDigits: 1 }).format(n),
    weekday,
    /** Monday-first order. */
    weekdays: (days: Weekday[]) => list.format([...days].sort((a, b) => ((a + 6) % 7) - ((b + 6) % 7)).map(weekday)),
    date: (d: Date) => new Intl.DateTimeFormat(lang, { weekday: 'long', day: 'numeric', month: 'long' }).format(d),
    time: (hhmm: string) => hhmm,
  };
}

export type Fmt = ReturnType<typeof fmt>;
