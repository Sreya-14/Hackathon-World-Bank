"""Read-back voice: Malayalam text → WAV with MMS-TTS (facebook/mms-tts-mal, CC-BY-NC-4.0).

Words it says wrongly are respelled (RESPELL) or played from a human recording (RECORDED).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from .ml_numbers import speakable
from .models import tts_dir

VOICE_DIR = Path(__file__).parent / 'voice'

# Words the voice says wrongly, respelled for speech only (the text the host reads is unchanged).
# Chosen by ear by a native speaker from candidate clips.
RESPELL = {
    'നന്ദി': 'നന്ദീ',           # "thanks": the short ി came out clipped
    'നമസ്കാരം': 'നമഃസ്കാരം',    # "hello": closest of 16 spellings to a native speaker's recording
    'ഭക്ഷണം': 'ഭക്ഷണ്ണം',       # "food" (standalone; ഉച്ചഭക്ഷണം already sounds right)
}

# English words said the English way. The Malayalam voice has no Latin letters and would skip
# them, so each is written as it sounds (matched to a native speaker's recording of "ഫുഡ്").
ENGLISH_WORDS = {
    'food': 'ഫുഡ്ഡ്',
}

# Words replaced by a human recording in voice/ (16 kHz mono WAV, trimmed; see save_recording).
RECORDED: dict[str, str] = {}

_ML_LETTER = '[\u0d00-\u0d7f]'


def respell(text: str) -> str:
    for word, spoken in RESPELL.items():
        text = re.sub(f'(?<!{_ML_LETTER}){word}(?!{_ML_LETTER})', spoken, text)
    for word, spoken in ENGLISH_WORDS.items():
        text = re.sub(rf'\b{word}\b', spoken, text, flags=re.I)
    return text


def voice_tag() -> str:
    """Changes whenever a respelling or recording changes, for caches keyed on the text."""
    files = [f'{w}:{(VOICE_DIR / f).stat().st_mtime_ns}' for w, f in RECORDED.items() if (VOICE_DIR / f).exists()]
    return '|'.join([*(f'{w}>{s}' for w, s in {**RESPELL, **ENGLISH_WORDS}.items()), *files])


@lru_cache(maxsize=None)
def _recording(file: str, rate: int) -> np.ndarray:
    import soundfile as sf
    data, file_rate = sf.read(str(VOICE_DIR / file), dtype='float32')
    return data if file_rate == rate else _resample(data, file_rate, rate)


def _resample(data: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Plain-numpy resampling: low-pass (windowed sinc) then linear interpolation."""
    if dst < src:
        taps = np.arange(-50, 51)
        cutoff = 0.45 * dst / src
        fir = 2 * cutoff * np.sinc(2 * cutoff * taps) * np.hamming(len(taps))
        data = np.convolve(data, fir / fir.sum(), mode='same')
    n = int(round(len(data) * dst / src))
    return np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data).astype(np.float32)


def save_recording(src_path: str, file: str, target_rms: float = 0.2) -> str:
    """Import a human recording of one word (any format soundfile reads, e.g. a WhatsApp .ogg):
    mono, 16 kHz, silence trimmed, level matched to the synthetic voice, short fades."""
    import soundfile as sf
    data, rate = sf.read(src_path, dtype='float32')
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = _resample(data, rate, 16000)
    frame = 320  # 20 ms
    energy = np.array([np.sqrt(np.mean(data[i:i + frame] ** 2)) for i in range(0, len(data) - frame, frame)])
    voiced = np.where(energy > max(energy.max() * 0.08, 1e-4))[0]
    start, end = max(voiced[0] * frame - 960, 0), min((voiced[-1] + 1) * frame + 960, len(data))  # ±60 ms
    clip = data[start:end]
    clip *= target_rms / max(np.sqrt(np.mean(clip ** 2)), 1e-6)
    clip = np.clip(clip, -0.99, 0.99)
    fade = np.linspace(0, 1, 160, dtype=np.float32)  # 10 ms
    clip[:160] *= fade
    clip[-160:] *= fade[::-1]
    VOICE_DIR.mkdir(exist_ok=True)
    sf.write(str(VOICE_DIR / file), clip, 16000)
    return str(VOICE_DIR / file)


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
    recorded = {w: f for w, f in RECORDED.items() if (VOICE_DIR / f).exists()}
    split = re.compile(f"({'|'.join(map(re.escape, recorded))})") if recorded else None
    chunks = []
    for sentence in [s for s in re.split(r'(?<=[.!?])\s+|\n+', respell(speakable(text))) if s.strip()]:
        # A word with a human recording is played from the recording; the rest is synthesised.
        for part in (split.split(sentence) if split else [sentence]):
            if part in recorded:
                chunks.append(_recording(recorded[part], rate))
                continue
            inputs = tok(part, return_tensors='pt')
            if not part.strip() or inputs['input_ids'].shape[1] == 0:
                continue
            with torch.no_grad():
                chunks.append(model(**inputs).waveform[0].numpy())
        chunks.append(pause)
    sf.write(out_path, np.concatenate(chunks) if chunks else pause, rate)
    return out_path
