"""Read-back voice: Malayalam text → WAV with MMS-TTS (facebook/mms-tts-mal, CC-BY-NC-4.0)."""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np

from .ml_numbers import speakable
from .models import tts_dir


@lru_cache(maxsize=None)
def _model():
    from transformers import AutoTokenizer, VitsModel
    path = str(tts_dir())
    return VitsModel.from_pretrained(path).eval(), AutoTokenizer.from_pretrained(path)


def speak(text: str, out_path: str) -> str:
    """Sentence by sentence with short pauses; VITS drifts on long inputs."""
    import soundfile as sf
    import torch

    model, tok = _model()
    rate = model.config.sampling_rate
    pause = np.zeros(int(rate * 0.35), dtype=np.float32)
    torch.manual_seed(0)  # VITS samples durations; keep the read-back reproducible
    chunks = []
    for sentence in [s for s in re.split(r'(?<=[.!?])\s+|\n+', speakable(text)) if s.strip()]:
        inputs = tok(sentence, return_tensors='pt')
        if inputs['input_ids'].shape[1] == 0:
            continue
        with torch.no_grad():
            chunks += [model(**inputs).waveform[0].numpy(), pause]
    sf.write(out_path, np.concatenate(chunks) if chunks else pause, rate)
    return out_path
