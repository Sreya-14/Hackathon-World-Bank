// Owned by the Engine track. Web Worker that runs transformers.js models.
// Offline notes:
// - Serve models from /models/ (env.localModelPath, env.allowRemoteModels = false).
// - ORT wasm comes from /ort/ (copied by ml/export_models.py); by default it is fetched
//   from a CDN, which breaks airplane mode.
import {
  env,
  pipeline,
  type FeatureExtractionPipeline,
  type ProgressInfo,
  type TranslationPipeline,
} from '@huggingface/transformers';
import { MODELS, TARGET_TOKEN, TRANSLATE_OPTIONS } from './config';
import { decide, segments, type ExampleLabel, type ExampleSet } from './intent';
import { detectLang } from './langdetect';
import type { Request, Response, Results } from './protocol';
import type { LoadProgress, OperatorLang, Understanding } from './types';

env.allowRemoteModels = false;
env.allowLocalModels = true;
env.localModelPath = '/models/';
env.useBrowserCache = true;
const wasm = env.backends.onnx.wasm!;
const ortFile = (name: string) => new URL(`/ort/${name}`, self.location.href).href;
let ortReady: Promise<void> | undefined;

/**
 * ORT dynamically imports its JS loader. Vite's dev server rewrites that import to
 * `?import` and then refuses files from /public, so import it from a blob: URL instead
 * (same bytes, still from the precached /ort/ file).
 */
function prepareOrt(): Promise<void> {
  ortReady ??= (async () => {
    const res = await fetch(ortFile('ort-wasm-simd-threaded.jsep.js'));
    if (!res.ok) throw new Error('ORT runtime missing in /ort/; run ml/export_models.py');
    const loader = URL.createObjectURL(new Blob([await res.text()], { type: 'text/javascript' }));
    wasm.wasmPaths = { mjs: loader, wasm: ortFile('ort-wasm-simd-threaded.jsep.wasm') };
  })();
  return ortReady;
}
// No COOP/COEP headers → no SharedArrayBuffer; say so instead of letting ORT probe.
wasm.numThreads = self.crossOriginIsolated ? Math.min(4, navigator.hardwareConcurrency || 1) : 1;

let toEnglish: TranslationPipeline | undefined;
let toLocal: TranslationPipeline | undefined;
let embedder: FeatureExtractionPipeline | undefined;
let examples: ExampleSet = { labels: [], vectors: [] };

const post = (msg: Response) => self.postMessage(msg);

/** Turns transformers.js per-file progress events into one 0..1 value per model. */
function progressFor(pack: LoadProgress['pack'], model: string) {
  const files = new Map<string, { loaded: number; total: number }>();
  return (p: ProgressInfo) => {
    if (p.status !== 'progress') return;
    files.set(p.file, { loaded: p.loaded, total: p.total });
    let loaded = 0;
    let total = 0;
    for (const f of files.values()) {
      loaded += f.loaded;
      total += f.total;
    }
    post({ progress: { pack, model, progress: total ? loaded / total : 0 } });
  };
}

async function load<T>(task: 'translation' | 'feature-extraction', model: string): Promise<T> {
  const p = (await pipeline(task, model, {
    dtype: 'q8',
    device: 'wasm',
    progress_callback: progressFor('core', model),
  })) as T;
  post({ progress: { pack: 'core', model, progress: 1 } });
  return p;
}

async function embed(texts: string[]): Promise<Float32Array[]> {
  const out: Float32Array[] = [];
  for (let i = 0; i < texts.length; i += 32) {
    const t = await embedder!(texts.slice(i, i + 32), { pooling: 'mean', normalize: true });
    const [n, dim] = t.dims;
    const data = t.data as Float32Array;
    for (let j = 0; j < n; j++) out.push(data.slice(j * dim, (j + 1) * dim));
  }
  return out;
}

async function loadExamples(): Promise<ExampleSet> {
  const res = await fetch('/intent-examples.json').catch(() => undefined);
  // The dev server answers a missing file with index.html and a 200.
  if (!res?.ok || !res.headers.get('content-type')?.includes('json')) {
    console.warn('[engine] no /intent-examples.json yet; every enquiry will be "not sure"');
    return { labels: [], vectors: [] };
  }
  const data = (await res.json()) as { examples: { text: string; intent: ExampleLabel }[] };
  return { labels: data.examples.map((e) => e.intent), vectors: await embed(data.examples.map((e) => e.text)) };
}

async function loadCore(): Promise<void> {
  await prepareOrt();
  // One model at a time keeps peak memory down on the phone.
  embedder ??= await load<FeatureExtractionPipeline>('feature-extraction', MODELS.embed);
  toEnglish ??= await load<TranslationPipeline>('translation', MODELS.toEnglish);
  toLocal ??= await load<TranslationPipeline>('translation', MODELS.toLocal);
  if (examples.labels.length === 0) examples = await loadExamples();
}

function sentences(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Sentence by sentence: Marian drifts or repeats itself on long inputs.
 * `prefix` is the target token multi-target models need (en-dra: >>mal<< / >>tam<<).
 */
async function translate(p: TranslationPipeline, text: string, prefix = ''): Promise<string> {
  const parts = sentences(text).map((s) => (prefix ? `${prefix} ${s}` : s));
  if (parts.length === 0) return '';
  // The typings demand a full GenerationConfig; only overrides are needed at runtime.
  const run = p as unknown as (t: string[], o: object) => Promise<{ translation_text: string }[]>;
  // One at a time: batched generation pads the shorter sentences and they end in junk ("?.!ா?").
  const out: string[] = [];
  for (const part of parts) {
    const [{ translation_text }] = await run([part], TRANSLATE_OPTIONS);
    out.push(translation_text.trim());
  }
  return out.join(' ');
}

async function understand(text: string, to: OperatorLang): Promise<Understanding> {
  if (!embedder || !toEnglish || !toLocal) throw new Error('loadCore() first');
  const original = text.trim();
  const { lang } = detectLang(original);
  if (lang === 'unknown') {
    return {
      original, lang, english: '', local: '', localLang: to, intents: [], accepted: [],
      status: 'not_sure', reason: 'unsupported_language',
    };
  }
  const english = lang === 'en' ? original : await translate(toEnglish, original);
  const [local, vectors] = await Promise.all([translate(toLocal, english, TARGET_TOKEN[to]), embed(segments(english))]);
  return { original, lang, english, local, localLang: to, ...decide(vectors, examples) };
}

self.onmessage = async (e: MessageEvent<Request>) => {
  const req = e.data;
  try {
    let result: Results[typeof req.type];
    switch (req.type) {
      case 'loadCore':
        result = await loadCore();
        break;
      case 'understand':
        result = await understand(req.text, req.to);
        break;
      case 'translateFromLocal':
        result = null; // E12: opus-mt-dra-en → opus-mt-en-de
        break;
    }
    post({ id: req.id, ok: true, result });
  } catch (err) {
    post({ id: req.id, ok: false, error: err instanceof Error ? err.message : String(err) });
  }
};
