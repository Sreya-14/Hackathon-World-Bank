"""Translation with NLLB-200 (CTranslate2 int8): ml → en for the LLM, en → de for tourists, en → ml for read-back."""
from __future__ import annotations

import re
from functools import lru_cache

from . import config
from .models import nllb_dir


@lru_cache(maxsize=None)
def _translator():
    import ctranslate2
    return ctranslate2.Translator(str(nllb_dir()), device='cpu', compute_type='int8', inter_threads=1,
                                  intra_threads=config.CPU_THREADS)


@lru_cache(maxsize=None)
def _tokenizer(src: str):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(nllb_dir()), src_lang=config.NLLB_CODES[src])


def _sentences(text: str) -> list[str]:
    # Whisper often leaves Malayalam unpunctuated; long chunks are still fine for NLLB up to ~200 tokens.
    return [s.strip() for s in re.split(r'(?<=[.!?।])\s+|\n+', text) if s.strip()]


def translate(text: str, src: str, tgt: str) -> str:
    """Sentence by sentence, so one bad sentence can't derail the rest."""
    if not text.strip():
        return ''
    tok = _tokenizer(src)
    parts = _sentences(text)
    batch = [tok.convert_ids_to_tokens(tok.encode(p)) for p in parts]
    results = _translator().translate_batch(
        batch, target_prefix=[[config.NLLB_CODES[tgt]]] * len(batch),
        beam_size=4, max_decoding_length=256, repetition_penalty=1.1,
    )
    out = []
    for r in results:
        ids = tok.convert_tokens_to_ids(r.hypotheses[0][1:])  # drop the target-language token
        out.append(tok.decode(ids, skip_special_tokens=True).strip())
    return ' '.join(out)
