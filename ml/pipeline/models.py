"""Where each model lives on disk, and `python -m pipeline.models` to download/convert them all.

Whisper and NLLB are converted to CTranslate2 int8; the LLM is a ready Q4 GGUF;
MMS-TTS runs as-is through transformers.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import config


def _slug(model_id: str) -> str:
    return model_id.replace('/', '--')


def asr_dir(model_id: str = config.ASR_MODEL) -> Path:
    return config.MODELS_DIR / 'asr' / _slug(model_id)


def nllb_dir() -> Path:
    return config.MODELS_DIR / 'nllb' / _slug(config.NLLB_MODEL)


def llm_path() -> Path:
    return config.MODELS_DIR / 'llm' / config.LLM_FILE


def tts_dir(model_id: str = config.TTS_MODEL) -> Path:
    return config.MODELS_DIR / 'tts' / _slug(model_id)


def _ct2_convert(model_id: str, out: Path, copy_files: list[str]) -> None:
    import ctranslate2
    from huggingface_hub import snapshot_download

    from huggingface_hub import list_repo_files

    # Many repos ship the same weights twice (.safetensors and .bin); fetch only one.
    top = [f for f in list_repo_files(model_id) if '/' not in f]  # skip checkpoints/ and runs/ folders
    weights = '*.safetensors' if any(f.endswith('.safetensors') for f in top) else '*.bin'
    src = snapshot_download(model_id, allow_patterns=['*.json', '*.txt', '*.model', weights],
                            ignore_patterns=['*/*'])
    ctranslate2.converters.TransformersConverter(src, copy_files=[f for f in copy_files if (Path(src) / f).exists()]) \
        .convert(str(out), quantization='int8', force=True)


def prepare_asr(model_id: str) -> None:
    out = asr_dir(model_id)
    if (out / 'model.bin').exists():
        return
    _ct2_convert(model_id, out, ['preprocessor_config.json', 'tokenizer.json'])
    if not (out / 'tokenizer.json').exists():
        # Many fine-tunes ship only the slow tokenizer; faster-whisper needs tokenizer.json.
        from transformers import WhisperTokenizerFast
        WhisperTokenizerFast.from_pretrained(model_id).backend_tokenizer.save(str(out / 'tokenizer.json'))


def prepare_nllb() -> None:
    out = nllb_dir()
    if (out / 'model.bin').exists():
        return
    _ct2_convert(config.NLLB_MODEL, out, ['tokenizer.json', 'tokenizer_config.json',
                                          'sentencepiece.bpe.model', 'special_tokens_map.json'])


def prepare_llm() -> None:
    from huggingface_hub import hf_hub_download
    if not llm_path().exists():
        hf_hub_download(config.LLM_REPO, config.LLM_FILE, local_dir=llm_path().parent)


def prepare_tts() -> None:
    from huggingface_hub import snapshot_download
    # Both voices, so the server never downloads one at run time (it must work offline).
    for model_id in (config.TTS_MODEL, config.TTS_MODEL_EN):
        snapshot_download(model_id, local_dir=tts_dir(model_id), allow_patterns=['*.json', '*.safetensors'])


def mb(path: Path) -> float:
    files = [path] if path.is_file() else [f for f in path.rglob('*') if f.is_file()]
    return sum(f.stat().st_size for f in files) / 1e6


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--asr-candidates', action='store_true', help='also prepare every ASR candidate for the eval')
    args = ap.parse_args()

    for model_id in config.ASR_CANDIDATES if args.asr_candidates else [config.ASR_MODEL]:
        print(f'--> ASR {model_id}', flush=True)
        prepare_asr(model_id)
    for name, step in [('NLLB', prepare_nllb), ('LLM', prepare_llm), ('TTS', prepare_tts)]:
        print(f'--> {name}', flush=True)
        step()

    rows = [(f'asr  {config.ASR_MODEL}', asr_dir()), (f'nllb {config.NLLB_MODEL}', nllb_dir()),
            (f'llm  {config.LLM_FILE}', llm_path()), (f'tts  {config.TTS_MODEL}', tts_dir()),
            (f'tts  {config.TTS_MODEL_EN}', tts_dir(config.TTS_MODEL_EN))]
    print(f'\n{"model":<58}{"MB":>8}')
    for name, path in rows:
        print(f'{name:<58}{mb(path):>8.1f}')
    print(f'{"TOTAL":<58}{sum(mb(p) for _, p in rows):>8.1f}')


if __name__ == '__main__':
    main()
