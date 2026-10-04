"""No invented facts: every number in the listing must come from what Noor said.

Prices, times, durations and group sizes are where a small LLM (or MT) is most
likely to make something up, and where a made-up value does the most harm.
Numbers in the English listing must appear in the English transcript; numbers in
a translated listing must appear in the English listing (catches MT corrupting them).
"""
from __future__ import annotations

import re

_UNITS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
    'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'half': 0.5,
}
_TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90}
_SCALES = {'hundred': 100, 'thousand': 1000, 'lakh': 100_000, 'lakhs': 100_000}
# German number words MT is likely to produce for small values. Not ein/eine/einen:
# they are also the article "a" ("einen Teegarten") and flagged every German listing.
_DE = {
    'null': 0, 'eins': 1, 'zwei': 2, 'drei': 3, 'vier': 4, 'fünf': 5,
    'sechs': 6, 'sieben': 7, 'acht': 8, 'neun': 9, 'zehn': 10, 'elf': 11, 'zwölf': 12, 'halb': 0.5,
    'halbe': 0.5, 'halben': 0.5, 'hundert': 100, 'tausend': 1000,
}

_NUM = re.compile(r'\d+(?:[.,]\d+)*')
_ONE_AS_NUMBER = re.compile(r"\bone\s+(?:o'?clock|am|pm|a\.m\.|p\.m\.|hours?|persons?|people|days?|nights?|kilos?)\b|\bone\s+in\s+the\s+(?:morning|afternoon|evening)", re.I)


def _parse_digits(tok: str) -> float:
    # "1,500" / "1.500" (thousands) vs "2.5" (decimal): a 3-digit group after the separator is thousands.
    if re.fullmatch(r'\d{1,3}([.,]\d{3})+', tok):
        return float(re.sub(r'[.,]', '', tok))
    return float(tok.replace(',', '.'))


def numbers(text: str) -> set[float]:
    """Every number in `text`, from digits or English/German number words."""
    text = text.lower()
    found = {_parse_digits(t) for t in _NUM.findall(text)}

    # Number words: accumulate runs like "one thousand five hundred".
    total, current, in_run = 0.0, 0.0, False
    for word in re.findall(r"[a-zäöüß]+", text) + ['']:
        if word in _UNITS or word in _DE and _DE[word] < 100:
            current += _UNITS.get(word, _DE.get(word, 0))
            in_run = True
        elif word in _TENS:
            current += _TENS[word]
            in_run = True
        elif word in _SCALES or word in ('hundert', 'tausend'):
            scale = _SCALES.get(word) or _DE[word]
            current = (current or 1) * scale
            if scale >= 1000:
                total, current = total + current, 0.0
            in_run = True
        elif word == 'and' and in_run:
            continue
        else:
            if in_run:
                found.add(total + current)
            total, current, in_run = 0.0, 0.0, False
    # "one" alone is mostly "one of", "the one", not a fact; keep 1 only if written as a
    # digit on its own (not the "1" in "1.500").
    # "one o'clock", "one person", "one night" are facts, though: the model writes them as "1".
    if not re.search(r'(?<![\d.,])1(?!\d|[.,]\d)', text) and not _ONE_AS_NUMBER.search(text):
        found.discard(1.0)
    return found


_EN_NUMBER_WORDS = set(_UNITS) | set(_TENS) | set(_SCALES)
_EN_RUN = re.compile(
    rf"\b(?:{'|'.join(sorted(_EN_NUMBER_WORDS, key=len, reverse=True))})"
    rf"(?:(?:[\s-]+(?:and\s+)?)(?:{'|'.join(sorted(_EN_NUMBER_WORDS, key=len, reverse=True))}))*\b",
    re.I,
)


def with_digits(text: str) -> str:
    """English number words → digits ("One thousand five hundred rupees" → "1500 rupees").

    MT spells prices out in words, and the small LLM copies digits far more reliably.
    """
    def value(m: re.Match) -> str:
        if m.group().lower() == 'half':
            return m.group()
        n = max(numbers(m.group()) | {0.0}) if m.group().lower() != 'one' else 1.0
        return str(int(n)) if n == int(n) else str(n)
    return _EN_RUN.sub(value, text)


def drop_ungrounded_sentences(text: str, source: str) -> str:
    """Remove sentences whose numbers are not in `source`.

    The small model adds things like "Duration: 3 hours" when she said "from 9 to 12",
    despite being told not to calculate. Removing that sentence keeps the rest of an
    otherwise good description; the invented number never reaches a tourist.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return ' '.join(s for s in sentences if not ungrounded(s, source)).strip()


# Words that carry no content: a sentence is judged on the rest.
_STOP = set('''a an the and or but if of to in on at by for with from as is are was were be been it its this that
these those you your we our us i me my she her he his they them their there here can will would could should
do does did have has had not no so than then just also very more most all any some each every about into over
up out come enjoy experience visit see join learn explore discover take get make our'''.split())


def _stem(word: str) -> str:
    for suffix in ('ings', 'ing', 'ies', 'ied', 'es', 'ed', 's', 'ly'):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _content_words(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and len(w) > 2}


def drop_unsaid_sentences(text: str, source: str, min_said: float = 0.5) -> str:
    """Remove sentences where most content words are not in `source` (what she said, translated).

    The listing writer turns a garbled translation into fluent text, but also adds things she
    never said ("freshly roasted coffee made from our own beans"). A sentence stays only if at
    least half of its content words appear in the transcript; the numbers check is separate.
    """
    said = _content_words(source)
    kept = []
    for s in re.split(r'(?<=[.!?])\s+', text.strip()):
        words = _content_words(s)
        if words and len(words & said) / len(words) >= min_said:
            kept.append(s)
    return ' '.join(kept).strip()


def ungrounded(claimed: str, source: str) -> set[float]:
    """Numbers in `claimed` that do not appear in `source`."""
    return numbers(claimed) - numbers(source)


# No host charges less than this; a lower figure means speech to text misheard the number
# ("മുന്നൂറ്റമ്പത്" (350) heard as "മുന്നൂറ്റം ഉപതു", translated "three and a half rupees").
MIN_PLAUSIBLE_PRICE = 10
# The amount attached to the currency: "3 and a half rupees", "250 rupees", "Rs. 800", "₹1500".
_AMOUNT_THEN_CURRENCY = re.compile(r"(\d+(?:[.,]\d+)?)(\s+and\s+a\s+half)?\s*(?:rupees?|rupien|rupie|rs\.?|inr)\b", re.I)
_CURRENCY_THEN_AMOUNT = re.compile(r"(?:₹|\brs\.?|\binr)\s*(\d+(?:[.,]\d+)?)", re.I)


def implausible_prices(text: str) -> set[float]:
    """Rupee amounts in `text` below MIN_PLAUSIBLE_PRICE. Only the number attached to the
    currency counts, so a time or duration in the same sentence ("1 to 3 pm") is ignored."""
    text = with_digits(text)
    amounts = {_parse_digits(m.group(1)) + (0.5 if m.group(2) else 0) for m in _AMOUNT_THEN_CURRENCY.finditer(text)}
    amounts |= {_parse_digits(m.group(1)) for m in _CURRENCY_THEN_AMOUNT.finditer(text)}
    return {a for a in amounts if 0 < a < MIN_PLAUSIBLE_PRICE}
