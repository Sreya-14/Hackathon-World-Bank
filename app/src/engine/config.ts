// Owned by the Engine track. Model ids and tuned thresholds.
// INTENT_THRESHOLD / INTENT_MARGIN are rough until E9 rewrites them from ml/eval.

import type { OperatorLang } from './types';

export const MODELS = {
  toEnglish: 'Xenova/opus-mt-de-en',
  /** One model for both operator languages, picked by a target token. */
  toLocal: 'Helsinki-NLP/opus-mt-en-dra',
  embed: 'Xenova/all-MiniLM-L6-v2',
} as const;

export const TARGET_TOKEN: Record<OperatorLang, string> = { ml: '>>mal<<', ta: '>>tam<<' };

/** Nearest-example cosine similarity a segment needs before its intent is accepted. */
export const INTENT_THRESHOLD = 0.6;
/** If the runner-up intent is this close to the top one, the segment is ambiguous. */
export const INTENT_MARGIN = 0.03;
/** More accepted intents than this → not sure (mixed_intents). */
export const MAX_ACCEPTED = 2;

export const TRANSLATE_OPTIONS = { num_beams: 1, max_new_tokens: 200, no_repeat_ngram_size: 4 } as const;
