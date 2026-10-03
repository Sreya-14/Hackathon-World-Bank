// Owned by the App track. A fake engine so the UI can be built with no models.
// Keyword rules only; it covers the confident, mixed-intent and not-sure paths.
import { INTENTS, type Engine, type IntentId, type Lang, type Understanding } from './types';

const KEYWORDS: Record<IntentId, RegExp> = {
  price: /price|cost|how much|preis|kostet|വില|എത്ര|விலை|எவ்வளவு/i,
  availability: /\bopen\b|available|geöffnet|verfügbar|തുറന്ന|ലഭ്യ|திறந்|கிடைக்கு/i,
  booking: /book|reserve|of us|people|come\b|buchen|reservieren|personen|kommen|zu (zweit|dritt|viert)|ബുക്ക്|പേർ|வர|முன்பதிவு|பேர்/i,
  directions: /find you|where|directions|finden|\bwo\b|എവിടെ|വഴി|எங்கே|வழி/i,
  included: /included|lunch|how long|inklusive|mittagessen|ഉച്ചഭക്ഷണ|ഉൾപ്പെ|மதிய உணவு|சேர்க்க/i,
  dietary_kids_access: /vegetarian|vegan|child|kids|wheelchair|vegetarisch|kinder|rollstuhl|വെജിറ്റേറിയൻ|കുട്ടി|വീൽചെയർ|சைவ|குழந்தை|சக்கர நாற்காலி/i,
  payment: /card|cash|pay|karte|bezahlen|bar\b|കാർഡ്|പണം|UPI|கார்டு|பணம்/i,
};

function detectLang(text: string): Lang | 'unknown' {
  if (/[ഀ-ൿ]/.test(text)) return 'ml';
  if (/[஀-௿]/.test(text)) return 'ta';
  if (/[äöüß]|\b(und|wir|ist|kostet|können|haben)\b/i.test(text)) return 'de';
  if (/\b(the|we|is|how|you|can|are)\b/i.test(text)) return 'en';
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

      const base = {
        original: message,
        lang,
        english: lang === 'en' ? message : `[mock EN] ${message}`,
        intents,
      };
      if (lang === 'unknown') return { ...base, accepted: [], status: 'not_sure', reason: 'unsupported_language' };
      if (accepted.length === 0) return { ...base, accepted, status: 'not_sure', reason: 'low_confidence' };
      if (accepted.length > 2) return { ...base, accepted: [], status: 'not_sure', reason: 'mixed_intents' };
      return { ...base, accepted, status: 'confident' };
    },

    async translateFromEnglish(text, to) {
      if (to === 'en') return text;
      return to === 'de' ? `[mock DE] ${text}` : null;
    },
    async speak() {
      // Short silent WAV header so the audio player path can be exercised.
      return new Blob([new Uint8Array(44)], { type: 'audio/wav' });
    },
    async transcribe() {
      await delay(500);
      return 'We are open every day except Sunday.';
    },
  };
}
