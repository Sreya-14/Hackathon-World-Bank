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
    if not re.search(r'(?<![\d.,])1(?!\d|[.,]\d)', text):
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


def ungrounded(claimed: str, source: str) -> set[float]:
    """Numbers in `claimed` that do not appear in `source`."""
    return numbers(claimed) - numbers(source)
