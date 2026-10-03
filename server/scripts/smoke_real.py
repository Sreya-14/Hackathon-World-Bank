"""Run the REAL ML layer through the server's adapter once: typed Malayalam, then a voice note.

    MOCK_AI=false .venv/bin/python -m scripts.smoke_real

The voice note is synthetic (MMS-TTS speaking Malayalam), so this proves the pieces connect;
it is not an accuracy measurement (see ml/eval for FLEURS).
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["MOCK_AI"] = "false"
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="lantern-smoke-"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import engine  # noqa: E402

SAY = "ഞാൻ കൽപ്പറ്റയിൽ ഒരു കാപ്പിത്തോട്ടം ടൂർ നടത്തുന്നു. ഒരാൾക്ക് അഞ്ഞൂറ് രൂപയാണ്. രാവിലെ ഒമ്പത് മണി മുതൽ പന്ത്രണ്ട് മണി വരെ."


def show(label: str, result, seconds: float) -> None:
    print(f"\n=== {label}  ({seconds:.1f}s)")
    print(f"status: {result.status}  reasons: {result.reasons}  asr_confidence: {result.asr_confidence}")
    print(f"transcript   : {result.transcript}")
    print(f"transcript_en: {result.transcript_en}")
    if result.listing:
        for lang, t in result.listing.text.items():
            print(f"[{lang}] {t.title} | {t.description} | price={t.price} hours={t.hours}")
    print(f"readback: {result.readback_text[:160]}…  wav={result.readback_wav}")
    print("timings:", {t.stage: t.seconds for t in result.timings})


def main() -> None:
    t0 = time.perf_counter()
    engine.warm_up()
    print(f"models loaded in {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    typed = engine.process(typed_text=SAY)
    show("typed Malayalam", typed, time.perf_counter() - t0)

    note = engine.speak(SAY)  # MMS-TTS → OGG/Opus, like a WhatsApp voice note
    t0 = time.perf_counter()
    voice = engine.process(audio_path=str(note))
    show(f"voice note ({note.name})", voice, time.perf_counter() - t0)
    if voice.readback_wav:
        print("read-back for WhatsApp:", engine.to_ogg(voice.readback_wav))


if __name__ == "__main__":
    main()
