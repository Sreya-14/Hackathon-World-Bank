"""ML pipeline: Noor's Malayalam voice note → listing (en, de) + Malayalam read-back.

The backend calls `process_voice_note(path)`; see schema.py for the result. If anything
looks unsure, the result is `needs_review` with reasons and nothing should be published.
"""
from __future__ import annotations

import re
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from . import config
from .grounding import drop_ungrounded_sentences, drop_unsaid_sentences, numbers, ungrounded, with_digits
from .places import places_in, protect
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
    tr = lambda s: translate(s, 'en', tgt).rstrip('.') if s else None  # noqa: E731  (short fields: no full stop)
    return ListingText(
        title=tr(t.title) or '', description=translate(t.description, 'en', tgt) if t.description else '', price=tr(t.price), hours=tr(t.hours),
        duration=tr(t.duration), includes=[tr(i) for i in t.includes], meeting_point=tr(t.meeting_point),
        location=t.location,  # place names stay as they are
    )


_PRICE_WORDS = set('''rupee rupees rs inr a an the per person people each head adult adults child children night
day only it is its costs cost price priced at for and just'''.split())


def _split_cost(description: str, price: str | None) -> tuple[str, str | None]:
    """(service text, cost). A short sentence that only states the price becomes the cost,
    as she said it ("Two thousand five hundred rupees a night" → "2500 rupees a night");
    sentences that say more than the price stay in the service text."""
    if not price:
        return description, None
    price_numbers = numbers(price)
    sentences = re.split(r'(?<=[.!?])\s+', description)

    def is_cost(s: str) -> bool:
        # Only the price: apart from its numbers, nothing but price words. "It takes an hour
        # and costs 300 rupees" says more (the duration), so it stays in the service text.
        words = re.findall(r'[a-z]+', with_digits(s).lower())
        return (bool(numbers(s)) and numbers(s) <= price_numbers and len(s.split()) <= 10
                and all(w in _PRICE_WORDS for w in words))
    costs = [s for s in sentences if is_cost(s)]
    service = ' '.join(s for s in sentences if not is_cost(s)).strip()
    cost = with_digits(costs[0]).rstrip('.').strip() if len(costs) == 1 else None
    if cost:
        cost = re.sub(r'^(?:price|cost)\s*:\s*', '', cost, flags=re.I)  # "Price: 500 rupees" → "500 rupees"
    return service, cost


def _readback_english(t: ListingText) -> str:
    parts = [f'{t.title}.', t.description]
    for label, value in [('Location', t.location), ('Price', t.price), ('Hours', t.hours),
                         ('Duration', t.duration), ('Meeting point', t.meeting_point)]:
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
    # Split into service / location / cost. The service is the listing writer's description,
    # keeping only sentences built from what she said (numbers and words, both checked against
    # the transcript): fluent, without its additions ("freshly roasted coffee") and without the
    # raw translation's garble ("I don't miss the week, day"). If nothing survives, the full
    # translation is used. Minus the sentence that only states the price; the cost is that
    # sentence ("2500 rupees a night"); the location is the places she named.
    service = drop_unsaid_sentences(drop_ungrounded_sentences(en.description, source), result.transcript_en)
    en.description, cost = _split_cost(service or result.transcript_en.strip(), en.price)
    en.price = cost or en.price
    en.location = ', '.join(places_in(transcript)) or en.meeting_point
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
