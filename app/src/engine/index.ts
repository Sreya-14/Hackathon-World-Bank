// Frozen. The App imports the engine only from here; VITE_ENGINE picks the implementation.
import type { Engine } from './types';
import { createMockEngine } from './mock';
import { createRealEngine } from './real';

export * from './types';

let engine: Engine | undefined;

export function getEngine(): Engine {
  engine ??= import.meta.env.VITE_ENGINE === 'real' ? createRealEngine() : createMockEngine();
  return engine;
}
