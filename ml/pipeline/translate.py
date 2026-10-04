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


# Malayalam clause endings: future (തരും), ought (പറയണം, ചെയ്യണം, നോക്കണം, വരണം), present
# (നടത്തുന്നു), copula (ആണ്). Not any word ending in ണം: ഉച്ചഭക്ഷണം (lunch) is a noun.
# A price also closes a clause (ഒരാൾക്ക് മുന്നൂറ്റമ്പത് രൂപ | ഒരു ദിവസം മുമ്പ് വിളിക്കണം), or NLLB merges
# the two into "call me three hundred and fifty rupees a day before".
# So does a time ("ഉച്ചയ്ക്ക് ഒരു മണിക്ക്" | "ഒരു ദിവസം മുമ്പ് വിളിക്കണം"), or it became "call me one o'clock".
_CLAUSE_END = re.compile(r'(?:ും|(?:യ|ക്ക|ര)ണം|ുന്നു|ാണ്|ില്ല|രൂപ(?:യാണ്|യ്ക്ക്|യും)?|മണിക്ക്)$')
MAX_CHUNK_WORDS = 12


def _chunks(sentence: str) -> list[str]:
    """Split a long unpunctuated Malayalam stretch after clause-ending verbs.

    NLLB stops early on a long unpunctuated line: a 30-word voice note came back as its first
    clause only, losing "350 rupees per person, 1 pm, call a day before". Short sentences and
    other languages pass through unchanged.
    """
    words = sentence.split()
    if len(words) <= MAX_CHUNK_WORDS or not re.search('[\u0d00-\u0d7f]', sentence):
        return [sentence]
    chunks, current = [], []
    for w in words:
        current.append(w)
        if (len(current) >= 3 and _CLAUSE_END.search(w)) or len(current) >= MAX_CHUNK_WORDS:
            chunks.append(' '.join(current))
            current = []
    if current:
        chunks.append(' '.join(current))
    return chunks


def _sentences(text: str) -> list[str]:
    # Whisper often leaves Malayalam unpunctuated: split long stretches into clauses (see _chunks).
    parts = [s.strip() for s in re.split(r'(?<=[.!?।])\s+|\n+', text) if s.strip()]
    return [c for p in parts for c in _chunks(p)]


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
        part = tok.decode(ids, skip_special_tokens=True).strip()
        if part and len(parts) > 1:
            # Clauses split from unpunctuated speech come back without a full stop or capital.
            # (A single phrase, like a title or price, is left as it is.)
            part = part[0].upper() + part[1:]
            part = part if part[-1] in '.!?' else part + '.'
        if part:
            out.append(part)
    return ' '.join(out)
