// Owned by the Engine track. Main-thread proxy that talks to worker.ts.
import type { Engine } from './types';

export function createRealEngine(): Engine {
  const notYet = () => Promise.reject(new Error('real engine not implemented yet'));
  return {
    loadCore: notYet,
    loadVoice: notYet,
    ready: () => ({ core: false, voice: false }),
    understand: notYet,
    translateFromEnglish: notYet,
    speak: notYet,
    transcribe: notYet,
  };
}
