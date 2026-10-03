// THE CONTRACT between the Engine track (models) and the App track (UI).
// Frozen: change only by agreement, in a small commit on main that both rebase onto.

/** Languages guests write in. */
export type TouristLang = 'en' | 'de';
/** Languages the operator reads and hears. Chosen once in setup and passed to each call. */
export type OperatorLang = 'ml' | 'ta';

export const INTENTS = [
  'price',
  'availability',
  'booking',
  'directions',
  'included',
  'dietary_kids_access',
  'payment',
] as const;
export type IntentId = (typeof INTENTS)[number];

export interface IntentScore {
  intent: IntentId;
  /** Cosine similarity to the nearest labelled example, 0..1. */
  score: number;
}

export type NotSureReason = 'low_confidence' | 'mixed_intents' | 'unsupported_language';

export interface Understanding {
  original: string;
  /** Detected guest language; 'unknown' always comes with status 'not_sure'. */
  lang: TouristLang | 'unknown';
  /** Pivot text the intent sorter ran on (equals `original` when lang is 'en'; '' when 'unknown'). */
  english: string;
  /** Machine translation for the operator in `localLang`. The UI must label it as machine-translated. '' when lang is 'unknown'. */
  local: string;
  localLang: OperatorLang;
  /** All intents, sorted by score descending. Empty when lang is 'unknown'. */
  intents: IntentScore[];
  /** Intents above the confidence threshold (zero, one or two). */
  accepted: IntentId[];
  status: 'confident' | 'not_sure';
  reason?: NotSureReason;
}

export interface LoadProgress {
  pack: 'core' | 'voice';
  model: string;
  /** 0..1 */
  progress: number;
}

export interface Engine {
  /** Opus-MT + MiniLM. Must be ready before understand(). Covers both operator languages. */
  loadCore(onProgress?: (p: LoadProgress) => void): Promise<void>;
  /** MMS-TTS + Whisper for one operator language. Optional; the app works without it. */
  loadVoice(lang: OperatorLang, onProgress?: (p: LoadProgress) => void): Promise<void>;
  ready(): { core: boolean; voice: OperatorLang[] };

  /** Detect language → translate → sort intent → decide confident / not sure. */
  understand(message: string, to: OperatorLang): Promise<Understanding>;

  /**
   * Translate the operator's free-form answer into the guest's language.
   * Returns null when unsupported; the app then falls back to "We will call you".
   */
  translateFromLocal(text: string, from: OperatorLang, to: TouristLang): Promise<string | null>;

  /** Text in the operator's language → audio (WAV) to play. Requires that language's voice pack. */
  speak(text: string, lang: OperatorLang): Promise<Blob>;
  /** Recorded audio → text in the operator's language. Requires that language's voice pack. */
  transcribe(audio: Blob, lang: OperatorLang): Promise<string>;
}
