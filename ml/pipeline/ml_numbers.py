"""Digits → Malayalam words, for the read-back voice.

MMS-TTS Malayalam has only 0–6 in its alphabet (7, 8, 9 are missing) and no Latin
letters, so "1500 രൂപ" or "9am" would be read wrongly or skipped. Prices and times are
exactly what Noor checks in the read-back, so spell them out first.
Joined forms follow common usage; have a native speaker check before the demo.
"""
from __future__ import annotations

import re

ONES = ['പൂജ്യം', 'ഒന്ന്', 'രണ്ട്', 'മൂന്ന്', 'നാല്', 'അഞ്ച്', 'ആറ്', 'ഏഴ്', 'എട്ട്', 'ഒമ്പത്',
        'പത്ത്', 'പതിനൊന്ന്', 'പന്ത്രണ്ട്', 'പതിമൂന്ന്', 'പതിനാല്', 'പതിനഞ്ച്', 'പതിനാറ്', 'പതിനേഴ്',
        'പതിനെട്ട്', 'പത്തൊമ്പത്']
TENS = {2: 'ഇരുപത്', 3: 'മുപ്പത്', 4: 'നാൽപ്പത്', 5: 'അമ്പത്', 6: 'അറുപത്', 7: 'എഴുപത്', 8: 'എൺപത്',
        9: 'തൊണ്ണൂറ്'}
HUNDREDS = {1: 'നൂറ്', 2: 'ഇരുനൂറ്', 3: 'മുന്നൂറ്', 4: 'നാനൂറ്', 5: 'അഞ്ഞൂറ്', 6: 'അറുനൂറ്', 7: 'എഴുനൂറ്',
            8: 'എണ്ണൂറ്', 9: 'തൊള്ളായിരം'}
# "N thousand" for N < 10 has its own fused forms.
THOUSANDS = {1: 'ആയിരം', 2: 'രണ്ടായിരം', 3: 'മൂവായിരം', 4: 'നാലായിരം', 5: 'അയ്യായിരം', 6: 'ആറായിരം',
             7: 'ഏഴായിരം', 8: 'എണ്ണായിരം', 9: 'ഒമ്പതിനായിരം', 10: 'പതിനായിരം'}


def _joining(word: str) -> str:
    """Form used when more follows: ഇരുപത് → ഇരുപത്തി, നൂറ് → നൂറ്റി, ആയിരം → ആയിരത്തി."""
    if word.endswith('ം'):
        return word[:-1] + 'ത്തി'
    if word.endswith('ത്'):
        return word[:-1] + '്തി'
    if word.endswith('റ്'):
        return word[:-1] + '്റി'
    return word


def _thousands(k: int) -> str:
    """k × 1000 for k < 100, fused the way it is spoken: പന്ത്രണ്ടായിരം, അമ്പതിനായിരം."""
    if k in THOUSANDS:
        return THOUSANDS[k]
    if k < 20:
        return ONES[k][:-1] + 'ായിരം'          # പന്ത്രണ്ട് → പന്ത്രണ്ടായിരം
    tens, unit = divmod(k, 10)
    if unit == 0:
        word = TENS[tens]
        return word[:-1] + ('ിനായിരം' if word.endswith('ത്') else 'ായിരം')  # അമ്പതിനായിരം, തൊണ്ണൂറായിരം
    return f'{_joining(TENS[tens])} {THOUSANDS[unit]}'  # ഇരുപത്തി അയ്യായിരം


def to_words(n: int) -> str:
    if n < 20:
        return ONES[n]
    if n < 100:
        tens, rest = divmod(n, 10)
        return TENS[tens] if rest == 0 else f'{_joining(TENS[tens])} {ONES[rest]}'
    if n < 1000:
        h, rest = divmod(n, 100)
        return HUNDREDS[h] if rest == 0 else f'{_joining(HUNDREDS[h])} {to_words(rest)}'
    if n < 100_000:
        k, rest = divmod(n, 1000)
        head = _thousands(k)
        return head if rest == 0 else f'{_joining(head)} {to_words(rest)}'
    if n < 10_000_000:
        lakh, rest = divmod(n, 100_000)
        head = 'ഒരു ലക്ഷം' if lakh == 1 else f'{to_words(lakh)} ലക്ഷം'
        return head if rest == 0 else f'{_joining(head)} {to_words(rest)}'
    return ' '.join(ONES[int(d)] for d in str(n))  # very large: read digit by digit


_TIME = re.compile(r'\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?\b', re.I)


def _time(m: re.Match) -> str:
    hour, minute, ap = int(m.group(1)), m.group(2), m.group(3).lower()
    part = 'രാവിലെ' if ap == 'a' else ('ഉച്ചയ്ക്ക്' if hour == 12 or hour < 4 else 'വൈകുന്നേരം')
    spoken = f'{part} {"ഒരു" if hour == 1 else to_words(hour)} മണി'
    if minute and int(minute):
        spoken += f' {to_words(int(minute))} മിനിറ്റ്'
    return spoken


def speakable(text: str) -> str:
    """Times and numbers to words; leftover Latin letters dropped (the voice can't say them)."""
    text = _TIME.sub(_time, text)
    text = re.sub(r'(\d),(\d{3})', r'\1\2', text)  # 1,500 → 1500
    text = re.sub(r'\d+', lambda m: to_words(int(m.group())), text)
    text = re.sub(r'[A-Za-z]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()
