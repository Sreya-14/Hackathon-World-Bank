"""Speech to text: Malayalam voice note → Malayalam transcript + confidence.

Findings that shaped this (FLEURS ml, see eval/asr_fleurs.py):
- Vanilla whisper-small writes romanised Malayalam; the Malayalam fine-tune is needed.
- Malayalam takes ~16 tokens per second of speech, and Whisper decodes at most 224
  tokens per window, so 30 s windows get cut off mid-sentence. 10 s windows (split at
  pauses by VAD) fit, and the batched pipeline decodes them in parallel.
- The fine-tune's language detection is broken (calls Malayalam Kannada), so
  "is this Malayalam?" is checked on the transcript's script instead.
"""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from . import config
from .models import asr_dir


@dataclass
class Transcript:
    text: str
    segments: list[str]  # one per ~10 s window; short, so they translate well
    confidence: float      # 0..1, length-weighted mean token probability
    no_speech_prob: float  # highest across segments
    malayalam_share: float  # share of letters in Malayalam script


@lru_cache(maxsize=None)
def _model(model_id: str = config.ASR_MODEL):
    from faster_whisper import BatchedInferencePipeline, WhisperModel
    model = WhisperModel(str(asr_dir(model_id)), device='cpu', compute_type='int8', cpu_threads=config.CPU_THREADS)
    return BatchedInferencePipeline(model)


def malayalam_share(text: str) -> float:
    letters = [c for c in text if unicodedata.category(c)[0] in 'LM']
    return sum('ഀ' <= c <= 'ൿ' for c in letters) / len(letters) if letters else 0.0


def transcribe(audio_path: str, model_id: str = config.ASR_MODEL) -> Transcript:
    """`audio_path` can be any format PyAV decodes, including WhatsApp .ogg/.opus voice notes."""
    segments, _ = _model(model_id).transcribe(
        audio_path, language=config.ASR_LANGUAGE, task='transcribe', beam_size=1,
        chunk_length=config.ASR_CHUNK_SECONDS, batch_size=8, without_timestamps=True,
    )
    segments = list(segments)
    # A window can end inside a multi-byte character; drop the broken remainder.
    pieces = [p for p in (s.text.replace('\ufffd', '').strip() for s in segments) if p]
    text = ' '.join(pieces)
    weights = [max(1, len(s.text)) for s in segments]
    confidence = (
        sum(math.exp(s.avg_logprob) * w for s, w in zip(segments, weights)) / sum(weights) if segments else 0.0
    )
    no_speech = max((s.no_speech_prob for s in segments), default=1.0)
    return Transcript(text=text, segments=pieces, confidence=confidence, no_speech_prob=no_speech,
                      malayalam_share=malayalam_share(text))
