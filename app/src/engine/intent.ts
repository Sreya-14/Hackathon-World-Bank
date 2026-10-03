// Owned by the Engine track. E6: nearest-example intent sorting on English text.
// Pure functions: the worker supplies embeddings, this decides.
import { INTENTS, type IntentId, type IntentScore, type NotSureReason } from './types';
import { INTENT_MARGIN, INTENT_THRESHOLD, MAX_ACCEPTED } from './config';

/** Labels in the example set; 'other' marks negatives and never reaches the app. */
export type ExampleLabel = IntentId | 'other';

export interface ExampleSet {
  labels: ExampleLabel[];
  /** Unit-length embeddings, one per label. */
  vectors: Float32Array[];
}

/** Split into sentences so "How much is it? Can we pay by card?" yields two intents. */
export function segments(english: string): string[] {
  const parts = english
    .split(/(?<=[.!?;])\s+|\n+/)
    .map((s) => s.trim())
    .filter((s) => /\p{L}/u.test(s));
  // The whole message too: some intents only show up with full context.
  return parts.length > 1 ? [english.trim(), ...parts] : [english.trim()];
}

function dot(a: Float32Array, b: Float32Array): number {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i] * b[i];
  return s;
}

/** Best similarity per label for one segment. */
function bestPerLabel(vec: Float32Array, ex: ExampleSet): Map<ExampleLabel, number> {
  const best = new Map<ExampleLabel, number>();
  ex.vectors.forEach((v, i) => {
    const s = dot(vec, v);
    if (s > (best.get(ex.labels[i]) ?? -1)) best.set(ex.labels[i], s);
  });
  return best;
}

export interface IntentDecision {
  intents: IntentScore[];
  accepted: IntentId[];
  status: 'confident' | 'not_sure';
  reason?: NotSureReason;
}

export function decide(segmentVectors: Float32Array[], ex: ExampleSet): IntentDecision {
  const overall = new Map<IntentId, number>(INTENTS.map((i) => [i, 0]));
  const accepted = new Set<IntentId>();

  for (const vec of segmentVectors) {
    const ranked = [...bestPerLabel(vec, ex)].sort((a, b) => b[1] - a[1]);
    for (const [label, s] of ranked) {
      if (label !== 'other' && s > overall.get(label)!) overall.set(label, s);
    }
    const [top, second] = ranked;
    if (!top || top[0] === 'other' || top[1] < INTENT_THRESHOLD) continue;
    if (second && second[0] !== top[0] && top[1] - second[1] < INTENT_MARGIN) continue;
    accepted.add(top[0]);
  }

  const intents = [...overall]
    .map(([intent, score]) => ({ intent, score: Math.max(0, Math.min(1, score)) }))
    .sort((a, b) => b.score - a.score);
  const list = intents.filter((s) => accepted.has(s.intent)).map((s) => s.intent);

  if (list.length === 0) return { intents, accepted: [], status: 'not_sure', reason: 'low_confidence' };
  if (list.length > MAX_ACCEPTED) return { intents, accepted: [], status: 'not_sure', reason: 'mixed_intents' };
  return { intents, accepted: list, status: 'confident' };
}
