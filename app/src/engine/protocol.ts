// Owned by the Engine track. Messages between real.ts (main thread) and worker.ts.
import type { LoadProgress, OperatorLang, TouristLang, Understanding } from './types';

export type Request =
  | { id: number; type: 'loadCore' }
  | { id: number; type: 'understand'; text: string; to: OperatorLang }
  | { id: number; type: 'translateFromLocal'; text: string; from: OperatorLang; to: TouristLang };

export interface Results {
  loadCore: void;
  understand: Understanding;
  translateFromLocal: string | null;
}

export type Response =
  | { id: number; ok: true; result: unknown }
  | { id: number; ok: false; error: string }
  | { id?: undefined; progress: LoadProgress };
