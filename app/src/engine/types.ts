// THE CONTRACT between the Engine track (models) and the App track (UI).
// Frozen: change only by agreement, in a small commit on main that both rebase onto.

/** Guest languages. The vendor's interface is always English. */
export const LANGS = ['en', 'de', 'ml', 'ta'] as const;
export type Lang = (typeof LANGS)[number];

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
  lang: Lang | 'unknown';
  /**
   * The message in English: what the vendor reads and what the intent sorter ran on.
   * Equals `original` when lang is 'en'; otherwise machine-translated and labelled as such in the UI.
   */
  english: string;
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
  /** Translation + MiniLM. Must be ready before understand(). */
  loadCore(onProgress?: (p: LoadProgress) => void): Promise<void>;
  /** TTS + Whisper. Optional; the app works without it. */
  loadVoice(onProgress?: (p: LoadProgress) => void): Promise<void>;
  ready(): { core: boolean; voice: boolean };

  /** Detect language → translate → sort intent → decide confident / not sure. */
  understand(message: string): Promise<Understanding>;

  /**
   * Translate the vendor's free-form English answer into the guest's language.
   * Returns null when unsupported; the app then falls back to "I will call you".
   */
  translateFromEnglish(text: string, to: Lang): Promise<string | null>;

  /** English text → audio (WAV) to play. Requires the voice pack. */
  speak(text: string): Promise<Blob>;
  /** Recorded English audio → text. Requires the voice pack. */
  transcribe(audio: Blob): Promise<string>;
}
