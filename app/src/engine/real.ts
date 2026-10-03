// Owned by the Engine track. Main-thread proxy that talks to worker.ts.
import type { Engine, LoadProgress, OperatorLang } from './types';
import type { Request, Response, Results } from './protocol';

type Pending = { resolve: (v: unknown) => void; reject: (e: Error) => void };
type Payload<K extends Request['type']> = Omit<Extract<Request, { type: K }>, 'id' | 'type'>;

export function createRealEngine(): Engine {
  let worker: Worker | undefined;
  let nextId = 1;
  const pending = new Map<number, Pending>();
  const state = { core: false, voice: [] as OperatorLang[] };
  let onProgress: ((p: LoadProgress) => void) | undefined;
  let coreLoading: Promise<void> | undefined;

  function getWorker(): Worker {
    if (worker) return worker;
    worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });
    worker.onmessage = (e: MessageEvent<Response>) => {
      const msg = e.data;
      if (msg.id === undefined) return onProgress?.(msg.progress);
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.ok) p?.resolve(msg.result);
      else p?.reject(new Error(msg.error));
    };
    worker.onerror = (e) => {
      for (const p of pending.values()) p.reject(new Error(e.message || 'engine worker crashed'));
      pending.clear();
    };
    return worker;
  }

  function call<K extends Request['type']>(type: K, payload: Payload<K>): Promise<Results[K]> {
    const id = nextId++;
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
      getWorker().postMessage({ id, type, ...payload });
    });
  }

  return {
    loadCore(cb) {
      onProgress = cb;
      coreLoading ??= call('loadCore', {}).then(
        () => void (state.core = true),
        (err) => {
          coreLoading = undefined; // allow a retry
          throw err;
        },
      );
      return coreLoading;
    },
    loadVoice: () => Promise.reject(new Error('voice pack not built yet')), // E7 / E11
    ready: () => ({ core: state.core, voice: [...state.voice] }),
    understand: (text, to) => call('understand', { text, to }),
    translateFromLocal: (text, from, to) => call('translateFromLocal', { text, from, to }),
    speak: () => Promise.reject(new Error('voice pack not built yet')), // E7
    transcribe: () => Promise.reject(new Error('voice pack not built yet')), // E11
  };
}
