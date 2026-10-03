// Owned by the Engine track. E3: tiny stopword + diacritic scorer, no model.
// Unsupported Latin-script languages are scored too, so Dutch is not mistaken for German.
import type { TouristLang } from './types';

type Scored = TouristLang | 'fr' | 'es' | 'it' | 'pt' | 'nl';

const STOPWORDS: Record<Scored, string[]> = {
  en: ['the', 'is', 'are', 'we', 'you', 'how', 'much', 'what', 'can', 'do', 'does', 'of', 'and', 'to', 'for', 'with', 'there', 'your', 'our', 'it', 'this', 'tour', 'would', 'like', 'please', 'hi', 'hello', 'thanks', 'i', 'a', 'in', 'on', 'at', 'us', 'will', 'have', 'any', 'be'],
  fr: ['le', 'la', 'les', 'est', 'nous', 'vous', 'combien', 'pour', 'avec', 'une', 'un', 'des', 'et', 'que', 'qui', 'pouvons', 'pouvez', 'je', 'il', 'du', 'au', 'sur', 'ce', 'merci', 'bonjour', 'svp', 'votre', 'notre', 'sommes', 'avez', 'faut', 'y', 'quel', 'quelle', 'peut', 'pas', 'en'],
  de: ['der', 'die', 'das', 'ist', 'wir', 'sie', 'und', 'wie', 'viel', 'kostet', 'für', 'mit', 'ein', 'eine', 'ich', 'es', 'auf', 'zu', 'den', 'dem', 'haben', 'gibt', 'können', 'kann', 'bitte', 'danke', 'hallo', 'ihr', 'ihre', 'uns', 'sind', 'nicht', 'was', 'wann', 'wo', 'auch', 'tour'],
  es: ['el', 'los', 'las', 'es', 'nosotros', 'usted', 'cuánto', 'cuanto', 'para', 'con', 'una', 'y', 'que', 'por', 'hola', 'gracias', 'podemos', 'puede', 'hay', 'somos', 'del', 'precio', 'cuesta'],
  it: ['il', 'lo', 'gli', 'è', 'siamo', 'quanto', 'costa', 'per', 'con', 'una', 'che', 'ciao', 'grazie', 'possiamo', 'può', 'della', 'del', 'sono', 'ci'],
  pt: ['o', 'os', 'as', 'é', 'nós', 'você', 'quanto', 'custa', 'para', 'com', 'uma', 'que', 'olá', 'obrigado', 'obrigada', 'podemos', 'pode', 'tem', 'somos', 'do', 'da', 'não'],
  nl: ['de', 'het', 'is', 'wij', 'we', 'jullie', 'hoeveel', 'kost', 'voor', 'met', 'een', 'en', 'dat', 'hallo', 'bedankt', 'kunnen', 'kan', 'zijn', 'niet', 'ook', 'wat', 'waar'],
};

// Characters that are strong evidence for one language.
const MARKS: [Scored, RegExp][] = [
  ['de', /[äöüß]/g],
  ['fr', /[éèêàçùûœ]|\b(?:qu'|c'|j'|l'|d'|n')/g],
  ['es', /[ñ¿¡]|ción\b/g],
  ['pt', /[ãõ]|ção\b/g],
  ['it', /\b(?:perché|cioè)\b/g],
];

const INDEX = new Map<string, Scored[]>();
for (const [lang, words] of Object.entries(STOPWORDS) as [Scored, string[]][]) {
  for (const w of words) INDEX.set(w, [...(INDEX.get(w) ?? []), lang]);
}

const SUPPORTED = new Set<string>(['en', 'de']);

export interface LangGuess {
  lang: TouristLang | 'unknown';
  /** Best-scoring language, including unsupported ones (for eval/debug). */
  best: Scored | 'none';
  scores: Partial<Record<Scored, number>>;
}

export function detectLang(text: string): LangGuess {
  // Non-Latin script (Cyrillic, Arabic, CJK, ...): not something we can handle.
  const letters = text.match(/\p{L}/gu) ?? [];
  const latin = letters.filter((c) => /\p{Script=Latin}/u.test(c)).length;
  if (letters.length === 0 || latin / letters.length < 0.7) return { lang: 'unknown', best: 'none', scores: {} };

  const lower = text.toLowerCase();
  const scores: Partial<Record<Scored, number>> = {};
  const add = (l: Scored, n: number) => (scores[l] = (scores[l] ?? 0) + n);

  // A word shared by several languages ('de', 'en', 'is') splits its vote.
  for (const tok of lower.match(/\p{L}+/gu) ?? []) {
    const langs = INDEX.get(tok);
    if (langs) for (const l of langs) add(l, 1 / langs.length);
  }
  for (const [l, re] of MARKS) add(l, (lower.match(re)?.length ?? 0) * 1.5);

  const ranked = (Object.entries(scores) as [Scored, number][]).filter(([, s]) => s > 0).sort((a, b) => b[1] - a[1]);
  if (ranked.length === 0) {
    // No evidence at all ("Price?", "Saturday 10am"): plain ASCII is most likely English.
    return { lang: /^[\x00-\x7f]*$/.test(text) ? 'en' : 'unknown', best: 'none', scores };
  }
  const [best, top] = ranked[0];
  // Ties go to English, the language the rest of the pipeline handles best.
  if (scores.en === top) return { lang: 'en', best: 'en', scores };
  return { lang: SUPPORTED.has(best) ? (best as TouristLang) : 'unknown', best, scores };
}
