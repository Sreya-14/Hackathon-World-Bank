"""E1: put int8 ONNX models into app/public/models/ in the layout transformers.js expects.

Models with a ready Xenova build are downloaded; the rest are converted with the
transformers.js v3 conversion script (Optimum + its Marian/VITS/Whisper fixes).
Only the files the browser needs are copied, then sizes are printed per pack.

    python export_models.py                # core pack
    python export_models.py --pack voice   # voice pack (MMS-TTS mal/tam, Whisper)
    python export_models.py --pack compare # opus-mt-en-ml, for the E9 comparison
    python export_models.py --pack all
    python export_models.py --only Helsinki-NLP/opus-mt-en-dra

Run inside ml/.venv (see ml/README or requirements-export.txt).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from huggingface_hub import snapshot_download

ML = Path(__file__).resolve().parent
OUT = ML.parent / 'app' / 'public' / 'models'
CACHE = ML / '.cache'
TJS = CACHE / 'tjs'  # transformers.js conversion scripts
TJS_REF = 'v3'
TJS_FILES = ['convert.py', 'quantize.py'] + [
    f'extra/{n}.py'
    for n in ['clap', 'clip', 'esm', 'marian', 'openelm', 'siglip', 'speecht5', 'vits', 'wav2vec2', 'whisper']
]

MARIAN = [
    'config.json', 'generation_config.json', 'tokenizer.json', 'tokenizer_config.json',
    'onnx/encoder_model_quantized.onnx', 'onnx/decoder_model_merged_quantized.onnx',
]
MINILM = ['config.json', 'tokenizer.json', 'tokenizer_config.json', 'onnx/model_quantized.onnx']
# Whisper's encoder loses accuracy when quantized; keep fp32 too and decide in E11.
WHISPER = [
    'config.json', 'generation_config.json', 'preprocessor_config.json', 'tokenizer.json', 'tokenizer_config.json',
    'onnx/encoder_model.onnx', 'onnx/encoder_model_quantized.onnx', 'onnx/decoder_model_merged_quantized.onnx',
]
# VITS can sound worse quantized; keep both and decide by ear in E7.
VITS = ['config.json', 'tokenizer.json', 'tokenizer_config.json', 'onnx/model.onnx', 'onnx/model_quantized.onnx']

# id is also the path under /models/, which is what the worker passes to pipeline().
# Guests write English or German; the operator reads/hears Malayalam or Tamil.
# en-dra covers both (target token >>mal<< / >>tam<<); en-ml is the dedicated
# alternative to compare against in E9.
MODELS = [
    {'id': 'Xenova/opus-mt-de-en', 'pack': 'core', 'source': 'hub', 'files': MARIAN},
    {'id': 'Helsinki-NLP/opus-mt-en-dra', 'pack': 'core', 'source': 'export', 'files': MARIAN},
    {'id': 'Xenova/all-MiniLM-L6-v2', 'pack': 'core', 'source': 'hub', 'files': MINILM},
    {'id': 'Helsinki-NLP/opus-mt-en-ml', 'pack': 'compare', 'source': 'export', 'files': MARIAN},
    {'id': 'facebook/mms-tts-mal', 'pack': 'voice', 'source': 'export', 'files': VITS},
    {'id': 'facebook/mms-tts-tam', 'pack': 'voice', 'source': 'export', 'files': VITS},
    {'id': 'Xenova/whisper-tiny', 'pack': 'voice', 'source': 'hub', 'files': WHISPER},
]


def fetch_tjs_scripts() -> None:
    for name in TJS_FILES:
        dest = TJS / 'scripts' / name
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f'https://raw.githubusercontent.com/huggingface/transformers.js/{TJS_REF}/scripts/{name}'
        urllib.request.urlretrieve(url, dest)


def from_hub(model: dict, dest: Path) -> None:
    snapshot_download(model['id'], allow_patterns=model['files'], local_dir=dest)


def from_export(model: dict, dest: Path) -> None:
    fetch_tjs_scripts()
    work = CACHE / 'converted'
    built = work / model['id']
    if not (built / model['files'][-1]).exists():
        subprocess.run(
            [sys.executable, '-m', 'scripts.convert', '--model_id', model['id'], '--quantize', '--modes', 'q8',
             '--output_parent_dir', str(work)],
            cwd=TJS, check=True,
        )
    for rel in model['files']:
        src = built / rel
        if not src.exists():
            raise FileNotFoundError(f'{model["id"]}: conversion did not produce {rel}')
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith('_quantized.onnx'):
            drop_float_duplicates(src, dest / rel)
        else:
            shutil.copy2(src, dest / rel)


def drop_float_duplicates(src: Path, dest: Path) -> None:
    """Remove fp32 weights that the quantizer also stored as uint8/int8.

    In merged Marian decoders the quantizer rewires the shared embedding in one If
    branch but not the other, so the 129MB fp32 copy stays next to the 32MB uint8
    one. Point every remaining fp32 consumer at DequantizeLinear(<w>_quantized),
    as the rewired branch already does, then drop the fp32 initializer.
    """
    import onnx
    from onnx import helper

    m = onnx.load(str(src))
    inits = {i.name: i for i in m.graph.initializer}
    dupes = {
        n for n in inits
        if inits[n].data_type == onnx.TensorProto.FLOAT
        and all(f'{n}{s}' in inits for s in ('_quantized', '_scale', '_zero_point'))
    }

    def rewire(graph) -> None:
        added = []
        for node in graph.node:
            for k, name in enumerate(node.input):
                if name in dupes:
                    out = f'{name}_dq_{node.name}'
                    added.append(helper.make_node(
                        'DequantizeLinear', [f'{name}_quantized', f'{name}_scale', f'{name}_zero_point'], [out],
                        name=f'{out}_node',
                    ))
                    node.input[k] = out
            for a in node.attribute:
                if a.type == onnx.AttributeProto.GRAPH:
                    rewire(a.g)
        if added:  # DequantizeLinear has no graph inputs, so it can go first
            nodes = added + list(graph.node)
            del graph.node[:]
            graph.node.extend(nodes)

    rewire(m.graph)
    keep = [i for i in m.graph.initializer if i.name not in dupes]
    del m.graph.initializer[:]
    m.graph.initializer.extend(keep)
    onnx.checker.check_model(m)
    onnx.save(m, str(dest))
    if dupes:
        print(f'    dropped fp32 duplicates in {dest.name}: {sorted(dupes)}')


def copy_ort_runtime() -> None:
    """ORT fetches its wasm from a CDN by default, which breaks airplane mode.

    Copy the build transformers.js ships into public/ort/. The .mjs loader is renamed
    to .js so the Workbox precache pattern (js, wasm) picks it up; the worker points
    env.backends.onnx.wasm.wasmPaths at these two files.
    """
    src = ML.parent / 'app' / 'node_modules' / '@huggingface' / 'transformers' / 'dist'
    dest = ML.parent / 'app' / 'public' / 'ort'
    if not src.exists():
        sys.exit('run `npm install` in app/ first (needed for the ORT wasm runtime)')
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / 'ort-wasm-simd-threaded.jsep.wasm', dest / 'ort-wasm-simd-threaded.jsep.wasm')
    shutil.copy2(src / 'ort-wasm-simd-threaded.jsep.mjs', dest / 'ort-wasm-simd-threaded.jsep.js')


def mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob('*') if f.is_file()) / 1e6


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack', choices=['core', 'voice', 'compare', 'all'], default='core')
    ap.add_argument('--only', help='a single model id')
    args = ap.parse_args()

    if args.only:
        chosen = [m for m in MODELS if m['id'] == args.only]
    else:
        chosen = [m for m in MODELS if args.pack in ('all', m['pack'])]
    if not chosen:
        sys.exit(f'nothing matches --only {args.only}')

    copy_ort_runtime()
    for m in chosen:
        dest = OUT / m['id']
        print(f'--> {m["id"]} ({m["source"]})', flush=True)
        (from_hub if m['source'] == 'hub' else from_export)(m, dest)
        missing = [f for f in m['files'] if not (dest / f).exists()]
        if missing:
            sys.exit(f'{m["id"]}: missing {missing}')

    print(f'\n{"model":<36}{"pack":<7}{"MB":>8}')
    totals: dict[str, float] = {}
    for m in MODELS:
        dest = OUT / m['id']
        if not dest.exists():
            continue
        size = mb(dest)
        totals[m['pack']] = totals.get(m['pack'], 0) + size
        print(f'{m["id"]:<36}{m["pack"]:<7}{size:>8.1f}')
    for pack, size in totals.items():
        print(f'{"TOTAL " + pack:<43}{size:>8.1f}')


if __name__ == '__main__':
    main()
