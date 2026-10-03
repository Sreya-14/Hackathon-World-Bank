// THE CONTRACT between the Engine track (models) and the App track (UI).
// Frozen: change only by agreement, in a small commit on main that both rebase onto.

export type TouristLang = 'en' | 'fr' | 'de';

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
  /** Detected tourist language; 'unknown' always comes with status 'not_sure'. */
  lang: TouristLang | 'unknown';
  /** Pivot text the intent sorter ran on (equals `original` when lang is 'en'). */
  english: string;
  /** Machine translation for Noor. The UI must label it as machine-translated. */
  swahili: string;
  /** All intents, sorted by score descending. */
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
  /** Opus-MT + MiniLM. Must be ready before understand(). */
  loadCore(onProgress?: (p: LoadProgress) => void): Promise<void>;
  /** MMS-TTS + Whisper. Optional; the app works without it. */
  loadVoice(onProgress?: (p: LoadProgress) => void): Promise<void>;
  ready(): { core: boolean; voice: boolean };

  /** Detect language → translate → sort intent → decide confident / not sure. */
  understand(message: string): Promise<Understanding>;

  /**
   * Translate Noor's free-form Swahili answer into the guest's language.
   * Returns null when unsupported; the app then falls back to "Noor will call you".
   */
  translateFromSwahili(text: string, to: TouristLang): Promise<string | null>;

  /** Swahili text → audio (WAV) to play. Requires the voice pack. */
  speak(swahili: string): Promise<Blob>;
  /** Recorded audio → Swahili text. Requires the voice pack. */
  transcribe(audio: Blob): Promise<string>;
}
