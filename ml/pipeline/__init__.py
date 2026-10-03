"""ML pipeline: Noor's Malayalam voice note → listing (en, de) + Malayalam read-back.

The backend calls `process_voice_note(path)`; see schema.py for the result. If anything
looks unsure, the result is `needs_review` with reasons and nothing should be published.
"""
from __future__ import annotations

import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from . import config
from .grounding import drop_ungrounded_sentences, ungrounded, with_digits
from .places import protect
from .schema import Listing, ListingText, PipelineResult, ReviewReason, StageTiming

__all__ = ['process_voice_note', 'process_transcript', 'warm_up', 'PipelineResult']

# Fixed Malayalam framing for the read-back, so the parts Noor relies on are never machine-translated.
# TODO: have a native speaker check these before the demo.
READBACK_INTRO = 'ടൂറിസ്റ്റുകൾ കാണുന്നത് ഇതാണ്.'
READBACK_OUTRO = 'ഇത് ശരിയാണെങ്കിൽ തംബ്സ് അപ്പ് അയയ്ക്കുക. തിരുത്താൻ, വീണ്ടും ഒരു വോയ്സ് നോട്ട് അയയ്ക്കുക.'


def warm_up() -> None:
    """Load every model once at server start, so the first voice note isn't slow."""
    from . import asr, listing, translate, tts
    asr._model()
    translate._translator()
    listing._llm()
    tts._model()


def _all_text(t: ListingText) -> str:
    return ' '.join(filter(None, [t.title, t.description, t.price, t.hours, t.duration, t.meeting_point, *t.includes]))


def _translate_listing(t: ListingText, tgt: str) -> ListingText:
    from .translate import translate
    tr = lambda s: translate(s, 'en', tgt) if s else None  # noqa: E731
    return ListingText(
        title=tr(t.title) or '', description=tr(t.description) or '', price=tr(t.price), hours=tr(t.hours),
        duration=tr(t.duration), includes=[tr(i) for i in t.includes], meeting_point=tr(t.meeting_point),
    )


def _readback_english(t: ListingText) -> str:
    parts = [f'{t.title}.', t.description]
    for label, value in [('Price', t.price), ('Hours', t.hours), ('Duration', t.duration),
                         ('Meeting point', t.meeting_point)]:
        if value:
            parts.append(f'{label}: {value}.')
    if t.includes:
        parts.append(f'Included: {", ".join(t.includes)}.')
    return ' '.join(parts)


class _Run:
    """One pipeline run: collects timings and review reasons into the result."""

    def __init__(self) -> None:
        self.result = PipelineResult(status='needs_review')
        self.reasons: list[ReviewReason] = []

    @contextmanager
    def stage(self, name):
        start = time.perf_counter()
        yield
        self.result.timings.append(StageTiming(stage=name, seconds=round(time.perf_counter() - start, 2)))

    def done(self) -> PipelineResult:
        self.result.reasons = list(dict.fromkeys(self.reasons))
        self.result.status = 'needs_review' if self.reasons else 'ready_for_approval'
        return self.result


def process_voice_note(audio_path: str, out_dir: str | None = None) -> PipelineResult:
    from . import asr

    run = _Run()
    # 1. Speech to text, and whether we should trust it.
    with run.stage('asr'):
        tr = asr.transcribe(audio_path)
    run.result.transcript, run.result.asr_confidence = tr.text, round(tr.confidence, 3)
    if not tr.text or tr.no_speech_prob > config.MAX_NO_SPEECH_PROB:
        run.reasons.append('no_speech')
    elif tr.malayalam_share < config.MIN_MALAYALAM_SHARE:
        run.reasons.append('wrong_language')
    elif tr.confidence < config.MIN_ASR_CONFIDENCE:
        run.reasons.append('unclear_audio')
    if run.reasons:
        return run.done()
    return _from_transcript(run, tr.segments, out_dir)


def process_transcript(malayalam: str, out_dir: str | None = None) -> PipelineResult:
    """Same pipeline from Malayalam text, skipping speech to text (eval, typed fallback)."""
    run = _Run()
    run.result.transcript, run.result.asr_confidence = malayalam.strip(), 1.0
    return _from_transcript(run, [line for line in malayalam.splitlines() if line.strip()], out_dir)


def _from_transcript(run: _Run, segments: list[str], out_dir: str | None) -> PipelineResult:
    from . import listing as writer, translate, tts

    result, reasons, transcript = run.result, run.reasons, run.result.transcript
    if len(transcript) < config.MIN_TRANSCRIPT_CHARS:
        reasons.append('empty_listing')
        return run.done()

    # 2. Into English, which the small LLM handles best.
    with run.stage('to_english'):
        # Segment by segment: NLLB drops or invents content on one long unpunctuated blob.
        # Place names go in as English, or മൂന്നാറിൽ ("in Munnar") comes out as "three".
        result.transcript_en = translate.translate('\n'.join(protect(s) for s in segments), 'ml', 'en')
    if len(result.transcript_en.split()) < config.MIN_EN_TO_ML_WORD_RATIO * len(transcript.split()):
        reasons.append('unclear_translation')
        return run.done()

    # 3. Listing JSON, then the no-invented-facts check against what she said.
    with run.stage('listing'):
        written = writer.write_listing(with_digits(result.transcript_en))
    if written is None:
        reasons.append('invalid_listing')
        return run.done()
    if written == writer.NOT_AN_OFFER:  # small talk, news, a greeting: nothing to list
        reasons.append('empty_listing')
        return run.done()
    category, en = written
    source = f'{result.transcript_en} {transcript}'
    # Free text: drop just the sentence with an invented number ("Duration: 3 hours").
    # Fact fields (price, hours...) are not trimmed: an invented one still holds the listing.
    en.title = drop_ungrounded_sentences(en.title, source)
    en.description = drop_ungrounded_sentences(en.description, source)
    result.listing = Listing(category=category, text={'en': en})
    if not en.title or not en.description:
        reasons.append('empty_listing')
    if ungrounded(_all_text(en), source):
        reasons.append('ungrounded_fact')
    if reasons:
        return run.done()

    # 4. Tourist languages by translation; numbers must survive it.
    with run.stage('to_listing_langs'):
        de = _translate_listing(en, 'de')
    result.listing.text['de'] = de
    result.listing.machine_translated = ['de']
    if ungrounded(_all_text(de), _all_text(en)):
        reasons.append('ungrounded_fact')
        return run.done()

    # 5. Read the English listing back to her in Malayalam.
    with run.stage('readback'):
        body = translate.translate(_readback_english(en), 'en', 'ml')
        result.readback_text = f'{READBACK_INTRO} {body} {READBACK_OUTRO}'
        out = Path(out_dir or tempfile.gettempdir()) / f'readback-{uuid.uuid4().hex[:8]}.wav'
        result.readback_wav = tts.speak(result.readback_text, str(out))
    return run.done()
