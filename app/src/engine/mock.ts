// Owned by the App track. A fake engine so the UI can be built with no models.
// Keyword rules only; it covers the confident, mixed-intent and not-sure paths.
import { INTENTS, type Engine, type IntentId, type TouristLang, type Understanding } from './types';

const KEYWORDS: Record<IntentId, RegExp> = {
  price: /\b(price|cost|how much|prix|combien|preis|kostet)\b/i,
  availability: /\b(open|available|saturday|sunday|ouvert|samedi|geöffnet|samstag)\b/i,
  booking: /\b(book|reserve|of us|people|réserver|personnes|buchen|personen)\b/i,
  directions: /\b(find you|where|directions|trouver|où|finden|wo)\b/i,
  included: /\b(included|lunch|how long|inclus|déjeuner|inklusive|mittagessen)\b/i,
  dietary_kids_access: /\b(vegetarian|vegan|child|kids|wheelchair|végétarien|enfant|kind|kinder)\b/i,
  payment: /\b(card|cash|pay|carte|payer|karte|bezahlen)\b/i,
};

function detectLang(text: string): TouristLang | 'unknown' {
  if (/[äöüß]|\b(und|wir|ist|kostet)\b/i.test(text)) return 'de';
  if (/[éèàç]|\b(nous|est|combien|vous)\b/i.test(text)) return 'fr';
  if (/\b(the|we|is|how|you)\b/i.test(text)) return 'en';
  return 'unknown';
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function createMockEngine(): Engine {
  const state = { core: false, voice: false };

  return {
    async loadCore(onProgress) {
      for (const p of [0.3, 0.7, 1]) {
        onProgress?.({ pack: 'core', model: 'mock', progress: p });
        await delay(150);
      }
      state.core = true;
    },
    async loadVoice(onProgress) {
      onProgress?.({ pack: 'voice', model: 'mock', progress: 1 });
      state.voice = true;
    },
    ready: () => ({ ...state }),

    async understand(message): Promise<Understanding> {
      await delay(300);
      const lang = detectLang(message);
      const intents = INTENTS.map((intent) => ({
        intent,
        score: KEYWORDS[intent].test(message) ? 0.82 : 0.2,
      })).sort((a, b) => b.score - a.score);
      const accepted = intents.filter((s) => s.score >= 0.6).map((s) => s.intent);

      const base = { original: message, lang, english: `[mock EN] ${message}`, swahili: `[mock SW] ${message}`, intents };
      if (lang === 'unknown') return { ...base, accepted: [], status: 'not_sure', reason: 'unsupported_language' };
      if (accepted.length === 0) return { ...base, accepted, status: 'not_sure', reason: 'low_confidence' };
      if (accepted.length > 2) return { ...base, accepted: [], status: 'not_sure', reason: 'mixed_intents' };
      return { ...base, accepted, status: 'confident' };
    },

    async translateFromSwahili(text, to) {
      return to === 'en' ? `[mock EN] ${text}` : null;
    },
    async speak() {
      // Short silent WAV header so the audio player path can be exercised.
      return new Blob([new Uint8Array(44)], { type: 'audio/wav' });
    },
    async transcribe() {
      await delay(500);
      return 'Bei ni shilingi elfu hamsini';
    },
  };
}
