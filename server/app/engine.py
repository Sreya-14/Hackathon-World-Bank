"""Adapter around the ML layer in ml/pipeline (docs/ENGINE_API.md).

- Real mode calls pipeline.process_voice_note / process_transcript.
- Mock mode returns the same PipelineResult shape without any models.
- Jobs run one at a time on a background worker: the models use every CPU core.
"""
from __future__ import annotations

import hashlib
import logging
import queue
import re
import sys
import threading
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from .config import settings

sys.path.insert(0, str(settings.ml_dir))
from pipeline.schema import Listing, ListingText, PipelineResult, StageTiming  # noqa: E402

log = logging.getLogger("lantern.engine")

# Voice for English prompt clips (PROMPT_VOICE=en). Same family and licence as the Malayalam read-back.
ENGLISH_VOICE = "facebook/mms-tts-eng"

# --- Job queue -------------------------------------------------------------------------

_jobs: "queue.Queue[Callable[[], None]]" = queue.Queue()
_worker: threading.Thread | None = None


def _work() -> None:
    while True:
        job = _jobs.get()
        try:
            job()
        except Exception:
            log.exception("pipeline job failed")
        finally:
            _jobs.task_done()


def submit(job: Callable[[], None]) -> None:
    """Queue a job (or run it now in tests)."""
    global _worker
    if settings.sync_jobs:
        job()
        return
    if _worker is None:
        _worker = threading.Thread(target=_work, name="pipeline-worker", daemon=True)
        _worker.start()
    _jobs.put(job)


def queue_length() -> int:
    return _jobs.qsize()


def warm_up() -> None:
    if not settings.mock_ai:
        import pipeline

        try:
            pipeline.warm_up()
        except Exception:
            log.exception("model warm-up failed; models will load on first use")
        # Render every prompt's audio now (cached on disk by text): made on first send, the
        # long welcome takes ~20 s on CPU, past Twilio's 15 s webhook timeout.
        from .prompts import PROMPTS

        for ml_text, en_text in PROMPTS.values():
            try:
                speak(ml_text)
                speak(en_text, "en")
            except Exception:
                log.exception("could not pre-render a prompt clip")


# --- Running the pipeline ---------------------------------------------------------------

def process(audio_path: str | None = None, typed_text: str | None = None) -> PipelineResult:
    out_dir = settings.media_dir / "readback"
    out_dir.mkdir(parents=True, exist_ok=True)
    if settings.mock_ai:
        return _mock(audio_path, typed_text, out_dir)
    import pipeline

    if typed_text:
        return pipeline.process_transcript(typed_text, out_dir=str(out_dir))
    return pipeline.process_voice_note(audio_path, out_dir=str(out_dir))


# --- Audio for WhatsApp -------------------------------------------------------------------

def to_ogg(wav_path: str | Path) -> Path:
    """WhatsApp plays voice notes as OGG/Opus; the pipeline writes WAV."""
    data, rate = sf.read(str(wav_path), dtype="float32")
    if rate not in (8000, 12000, 16000, 24000, 48000):  # Opus sample rates
        idx = np.linspace(0, len(data) - 1, int(len(data) * 16000 / rate))
        data, rate = np.interp(idx, np.arange(len(data)), data).astype(np.float32), 16000
    out = Path(wav_path).with_suffix(".ogg")
    sf.write(str(out), data, rate, format="OGG", subtype="OPUS")
    return out


_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿️⃣]")


def speak(text: str, lang: str = "ml") -> Path:
    """A clip for a fixed bot prompt (cached by text), as OGG/Opus. lang: "ml" or "en"."""
    spoken = " ".join(_EMOJI.sub(" ", text).split())
    voice = ""
    if lang == "ml" and not settings.mock_ai:
        from pipeline import tts

        voice = tts.voice_tag()  # a new respelling or recording re-records the clip
    key = hashlib.sha1(f"{settings.mock_ai}|{lang}|{voice}|{spoken}".encode()).hexdigest()[:16]
    ogg = settings.media_dir / "prompts" / f"{key}.ogg"
    if ogg.exists():
        return ogg
    ogg.parent.mkdir(parents=True, exist_ok=True)
    wav = ogg.with_suffix(".wav")
    if settings.mock_ai:
        _tone(wav)
    elif lang == "en":
        _speak_english(spoken, wav)
    else:
        from pipeline import tts

        tts.speak(spoken, str(wav))
    return to_ogg(wav)


@lru_cache(maxsize=None)
def _english_voice():
    from transformers import AutoTokenizer, VitsModel

    # From the side-loaded model folder (cd ml && python -m pipeline.models), so it works offline.
    from pipeline.models import tts_dir

    local = tts_dir(ENGLISH_VOICE)
    path = str(local) if (local / "config.json").exists() else ENGLISH_VOICE
    return VitsModel.from_pretrained(path).eval(), AutoTokenizer.from_pretrained(path)


def _speak_english(text: str, wav: Path) -> None:
    """English prompt clips (demo setting), sentence by sentence like the Malayalam read-back."""
    import torch

    model, tok = _english_voice()
    rate = model.config.sampling_rate
    pause = np.zeros(int(rate * 0.3), dtype=np.float32)
    torch.manual_seed(0)
    chunks = []
    for sentence in [x for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]:
        inputs = tok(sentence, return_tensors="pt")
        if inputs["input_ids"].shape[1]:
            with torch.no_grad():
                chunks += [model(**inputs).waveform[0].numpy(), pause]
    sf.write(str(wav), np.concatenate(chunks) if chunks else pause, rate)


def _tone(path: Path, seconds: float = 0.5) -> None:
    sr = 16000
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    sf.write(str(path), (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32), sr)


# --- Mock pipeline (same contract, no models) ----------------------------------------------

_DEFAULT_ML = (
    "ഞാൻ കൽപ്പറ്റയ്ക്കടുത്ത് ഒരു കാപ്പിത്തോട്ടം നടത്തം നടത്തുന്നു. കാപ്പിയും കുരുമുളകും എങ്ങനെ വളരുന്നു എന്ന് "
    "കാണിച്ചുതരും, പിന്നെ ഒരുമിച്ച് കാപ്പി കുടിക്കാം. ഒരാൾക്ക് 500 രൂപ. രാവിലെ 9 മുതൽ 12 വരെ."
)
_DEFAULT_EN = (
    "I run a coffee plantation walk near Kalpetta. I show how coffee and pepper grow, then we drink coffee "
    "together. 500 rupees per person. From 9 to 12 in the morning."
)
_CATEGORIES = {
    "tour": ("tour", "walk", "trek", "plantation", "ടൂർ", "നടത്തം"),
    "food": ("lunch", "food", "meal", "cook", "ഭക്ഷണ", "ഊണ്"),
    "craft": ("bamboo", "basket", "craft", "pottery", "മുള", "കരകൗശല"),
    "textile": ("weave", "weaving", "saree", "textile", "നെയ്ത്ത"),
    "experience": ("class", "workshop", "homestay", "ക്ലാസ്"),
}
_DE = {"tour": "Tour", "food": "Essen", "craft": "Handwerk", "textile": "Textilien", "experience": "Erlebnis", "other": "Angebot"}


def _mock(audio_path: str | None, typed_text: str | None, out_dir: Path) -> PipelineResult:
    transcript = (typed_text or "").strip() or _DEFAULT_ML
    english = _DEFAULT_EN if transcript == _DEFAULT_ML else transcript
    timings = [StageTiming(stage="asr", seconds=0.1), StageTiming(stage="to_english", seconds=0.1)]
    if len(transcript) < 15 or "unclear" in english.lower():
        return PipelineResult(status="needs_review", reasons=["unclear_audio"], transcript=transcript,
                              transcript_en=english, asr_confidence=0.3, timings=timings)

    low = english.lower()
    category = next((c for c, words in _CATEGORIES.items() if any(w in low for w in words)), "other")
    price = re.search(r"(\d+)\s*(rupees|rs\.?|₹|രൂപ)", low)
    hours = re.search(r"(?:from )?(\d{1,2}) (?:to|മുതൽ) (\d{1,2})", low)
    first = re.split(r"(?<=[.!?])\s", english)[0][:300]
    en = ListingText(
        location="Kalpetta" if "kalpetta" in low else None,
        title=f"Local {category} near Kalpetta" if category != "other" else "Local experience in Wayanad",
        description=first if len(first) >= 10 else f"A local {category} in Wayanad.",
        price=f"{price.group(1)} rupees per person" if price else None,
        hours=f"{hours.group(1)} to {hours.group(2)}" if hours else None,
    )
    de = ListingText(
        location="Kalpetta" if "kalpetta" in low else None,
        title=f"Lokales Angebot ({_DE[category]}) bei Kalpetta",
        description="Ein lokales Angebot in Wayanad, beschrieben von der Gastgeberin. (Mock-Übersetzung)",
        price=f"{price.group(1)} Rupien pro Person" if price else None,
        hours=f"{hours.group(1)} bis {hours.group(2)} Uhr" if hours else None,
    )
    wav = out_dir / f"readback-mock-{uuid.uuid4().hex[:8]}.wav"
    _tone(wav, 1.0)
    return PipelineResult(
        status="ready_for_approval", transcript=transcript, transcript_en=english, asr_confidence=0.85,
        listing=Listing(category=category, text={"en": en, "de": de}, machine_translated=["de"]),
        readback_text=f"ടൂറിസ്റ്റുകൾ കാണുന്നത് ഇതാണ്. (മോക്ക്) {transcript} ഇത് ശരിയാണെങ്കിൽ തംബ്സ് അപ്പ് അയയ്ക്കുക.",
        readback_wav=str(wav),
        timings=timings + [StageTiming(stage="listing", seconds=0.1), StageTiming(stage="readback", seconds=0.1)],
    )
