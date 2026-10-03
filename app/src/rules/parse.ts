// Deterministic extraction from the guest's message: date, group size, specific topics.
// chrono parses English and German directly; Malayalam and Tamil go through the English pivot.
import * as chrono from 'chrono-node';
import type { Lang } from '../engine';
import type { Asked } from '../content/templates';

// Malayalam and Tamil weekday stems (index = Date.getDay()), plus "tomorrow".
// A direct match so dates don't depend on machine-translation quality.
const INDIC_WEEKDAYS: Record<'ml' | 'ta', string[]> = {
  ml: ['ഞായർ', 'തിങ്കൾ', 'ചൊവ്വ', 'ബുധൻ', 'വ്യാഴ', 'വെള്ളി', 'ശനി'],
  ta: ['ஞாயிறு', 'திங்கள்', 'செவ்வாய்', 'புதன்', 'வியாழ', 'வெள்ளி', 'சனி'],
};
const INDIC_TOMORROW: Record<'ml' | 'ta', string> = { ml: 'നാളെ', ta: 'நாளை' };

function parseIndicDay(text: string, lang: 'ml' | 'ta', ref: Date): Date | undefined {
  const d = new Date(ref);
  d.setHours(0, 0, 0, 0);
  if (text.includes(INDIC_TOMORROW[lang])) {
    d.setDate(d.getDate() + 1);
    return d;
  }
  const wd = INDIC_WEEKDAYS[lang].findIndex((stem) => text.includes(stem));
  if (wd < 0) return undefined;
  d.setDate(d.getDate() + ((wd - d.getDay() + 7) % 7));
  return d;
}

/** First mention of a day; a bare time like "10am" does not count. */
export function parseDate(text: string, lang: Lang | 'unknown', english: string, ref = new Date()): Date | undefined {
  if (lang === 'ml' || lang === 'ta') {
    const direct = parseIndicDay(text, lang, ref);
    if (direct) return direct;
  }
  const tries: [chrono.Chrono, string][] =
    lang === 'de' ? [[chrono.de.casual, text], [chrono.en.casual, english]]
    : lang === 'en' || lang === 'unknown' ? [[chrono.en.casual, text]]
    : [[chrono.en.casual, english]];
  for (const [parser, t] of tries) {
    const hit = parser
      .parse(t, ref, { forwardDate: true })
      .find((r) => r.start.isCertain('day') || r.start.isCertain('weekday'));
    if (hit) {
      const d = hit.start.date();
      d.setHours(0, 0, 0, 0);
      return d;
    }
  }
  return undefined;
}

const NUMBER_WORDS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
  ein: 1, eine: 1, zwei: 2, drei: 3, vier: 4, fünf: 5, sechs: 6, sieben: 7, acht: 8, neun: 9, zehn: 10, elf: 11, zwölf: 12,
};
// German "zu viert" = "as a group of four".
const ZU: Record<string, number> = { zweit: 2, dritt: 3, viert: 4, fünft: 5, sechst: 6, siebt: 7, acht: 8 };

const N = `(\\d{1,2}|${Object.keys(NUMBER_WORDS).join('|')})`;
const toNum = (s: string) => (/^\d+$/.test(s) ? Number(s) : NUMBER_WORDS[s.toLowerCase()]);

// Indic scripts have no \b word boundaries, so those patterns match on the digit + noun alone.
const PARTS = [
  new RegExp(`${N}\\s+(adults?|children|kids?|erwachsene|kinder)\\b`, 'giu'),
  /(\d{1,2})\s*(മുതിർന്നവർ|കുട്ടികൾ|பெரியவர்கள்|குழந்தைகள்)/gu,
];
const WHOLE = [
  new RegExp(`${N}\\s+(of us|people|persons|guests|pax|personen|leute|gäste)\\b`, 'iu'),
  new RegExp(`\\b(?:group of|party of|we are|we're|there are|wir sind|gruppe von)\\s+${N}\\b`, 'iu'),
  /(\d{1,2})\s*(പേർ|പേര്|ആളുകൾ|பேர்|நபர்கள்)/u, // ml "4 പേർ", ta "4 பேர்" = 4 people
];

export function parseGroupSize(text: string, english = ''): number | undefined {
  for (const t of [text, english]) {
    const parts = PARTS.flatMap((re) => [...t.matchAll(re)]).map((m) => toNum(m[1])).filter(Boolean);
    if (parts.length) return parts.reduce((a, b) => a + b, 0);
    for (const re of WHOLE) {
      const m = t.match(re);
      if (m) return toNum(m[1]);
    }
    const zu = t.match(/\bzu (zweit|dritt|viert|fünft|sechst|siebt|acht)\b/iu);
    if (zu) return ZU[zu[1].toLowerCase()];
  }
  return undefined;
}

export function parseAsked(text: string, english = ''): Asked {
  const t = `${text}\n${english}`;
  return {
    vegetarian: /vegetar|vegan|veggie|വെജിറ്റേറിയൻ|സസ്യാഹാര|சைவ|வெஜிடேரியன்/iu.test(t),
    kids: /\b(child|children|kids?|baby|toddler|kinder|kind)\b|കുട്ടി|குழந்தை/iu.test(t),
    wheelchair: /wheelchair|disab|mobility|rollstuhl|behindert|barrierefrei|വീൽചെയർ|சக்கர நாற்காலி/iu.test(t),
    card: /\b(card|credit|visa|mastercard|karte|kreditkarte)\b|കാർഡ്|கார்டு/iu.test(t),
  };
}
