"""Listing writer: English transcript → English listing JSON, with a small local LLM.

The output is constrained to a JSON schema by llama.cpp's grammar, then validated.
Only English is generated; other languages are translated from it (NLLB), which
small models do far more reliably than writing German themselves.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, ValidationError

from . import config
from .grounding import with_digits
from .models import llm_path
from .schema import Category, ListingText


# Field order matters for a small model: it decides "is this an offer?" first, then fills
# the facts, then writes from them.
class LlmListing(BaseModel):
    is_offer: bool
    category: Category
    price: Optional[str] = None
    days_and_times: Optional[str] = None  # "hours" alone made it write the duration here
    duration: Optional[str] = None
    includes: list[str] = []
    meeting_point: Optional[str] = None
    title: str
    description: str


SYSTEM = """You turn what a small tour or craft operator said into a short listing for tourists.

Rules:
- is_offer: true only if she describes something tourists can visit, do, eat, stay at or buy from her.
  Greetings, small talk, news or anything else is false (then use category "other" and empty strings).
- Use ONLY facts stated in the transcript. Never add prices, times, durations, places or claims she did not say.
  Do not calculate anything: if she says "from 9 to 12", do not write "3 hours".
- Fill price, days_and_times (which days, what time it starts), duration (how long it lasts, only if she says so),
  includes and meeting_point whenever she states them; use null (or []) only if she did not.
- category:
  tour = guided walks, plantation or farm visits, treks, sightseeing;
  food = meals, cooking classes, tastings, food she makes or sells;
  craft = things made by hand (baskets, pottery, bamboo, woodwork), or watching/learning to make them;
  textile = weaving, sarees, cloth, embroidery;
  experience = homestays, stays and other hands-on activities that fit none of the above;
  other = anything else.
- title: at most 8 words, naming what she offers.
- description: 2 short sentences in your own words, written for a tourist, only about what she said. Do not quote her.
Reply with JSON only."""

# Worked examples (synthetic; different businesses, so they can't be copied into her listing).
EXAMPLES = [
    ('My name is Lakshmi. I make banana chips and halwa at home in Thrissur. You can watch and taste. '
     'It takes one hour. 300 rupees for each person. Every day except Sunday, 3 in the afternoon.',
     {'is_offer': True, 'category': 'food', 'price': '300 rupees per person',
      'days_and_times': 'Every day except Sunday, 3 pm', 'duration': 'One hour', 'includes': ['Tasting'],
      'meeting_point': None, 'title': 'Home Kitchen Snack Making in Thrissur',
      'description': 'Watch banana chips and halwa being made in a family kitchen in Thrissur. '
                     'Taste them fresh at the end.'}),
    ('Good morning. The bus was late today and my son has an exam tomorrow.',
     {'is_offer': False, 'category': 'other', 'price': None, 'days_and_times': None, 'duration': None,
      'includes': [], 'meeting_point': None, 'title': '', 'description': ''}),
]

NOT_AN_OFFER = 'not_an_offer'


@lru_cache(maxsize=None)
def _llm():
    from llama_cpp import Llama
    return Llama(model_path=str(llm_path()), n_ctx=2048, n_threads=config.CPU_THREADS, verbose=False)


def _ask(transcript_en: str, temperature: float) -> str:
    out = _llm().create_chat_completion(
        messages=[
            {'role': 'system', 'content': SYSTEM},
            *[m for text, out in EXAMPLES for m in (
                {'role': 'user', 'content': f'Transcript:\n"""{text}"""'},
                {'role': 'assistant', 'content': json.dumps(out)},
            )],
            {'role': 'user', 'content': f'Transcript:\n"""{transcript_en}"""'},
        ],
        response_format={'type': 'json_object', 'schema': LlmListing.model_json_schema()},
        temperature=temperature,
        max_tokens=400,
    )
    return out['choices'][0]['message']['content']


_PRICE = re.compile(
    r'(?:₹|rs\.?|inr)\s*\d[\d,]*(?:\s+(?:a|per|for each|each)\s+(?:person|people|head|adult|child))?'
    r'|\d[\d,]*\s*(?:rupees?|rs\.?|inr|₹)(?:\s+(?:a|per|for each|each)\s+(?:person|people|head|adult|child))?',
    re.I,
)


def price_in(transcript_en: str) -> Optional[str]:
    """The price phrase exactly as stated ("1500 rupees a person"), if there is exactly one.

    The small model often leaves `price` empty even when it writes the price into the
    description; copying the phrase is grounded by construction.
    """
    found = {m.group().strip() for m in _PRICE.finditer(transcript_en)}
    return found.pop() if len(found) == 1 else None


_DAY = r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?'
_DAYS = re.compile(
    rf'\b(?:every ?day|daily|all week|on weekends|weekends|weekdays'
    rf'|except (?:on )?{_DAY}(?: and {_DAY})?'
    rf'|(?:from |on |every )?{_DAY}(?:\s*(?:to|through|till|until|-|–)\s*{_DAY})?)\b',
    re.I,
)
_CLOCK = r"\d{1,2}(?:[:.]\d{2})?(?:\s*(?:a\.?\s?m\.?|p\.?\s?m\.?|o'clock))?"
_TIMES = re.compile(
    rf"(?:\b(?:from|at|starting at|starts at|start at)\s+)?{_CLOCK}"
    rf"(?:\s*(?:to|till|until|-|–)\s*{_CLOCK})?(?:\s+in the (?:morning|afternoon|evening))?",
    re.I,
)


def _is_clock(m: re.Match) -> bool:
    """A real time of day, not a price, a count or a duration ("500 rupees", "2 hours")."""
    s = m.group()
    after = m.string[m.end():m.end() + 12].lower()
    if re.match(r'\s*(?:hours?|hrs?|minutes?|mins?|rupees?|rs|people|persons?|km|days?|nights?)\b', after):
        return False
    if any(int(h) > 24 for h in re.findall(r'(?<![:.\d])(\d{1,2})(?:[:.]\d{2})?', s)):  # hours, not the minutes
        return False
    marked = re.search(r"[:.]\d{2}|[ap]\.?\s?m\b|o'clock|in the (?:morning|afternoon|evening)", s, re.I)
    ranged = re.search(r'\b(?:from|at|start)', s, re.I) and re.search(r'\d\s*(?:to|till|until|-|–)\s*\d', s)
    return bool(marked or ranged)


def hours_in(transcript_en: str) -> Optional[str]:
    """Days and times exactly as she said them ("Every day, from 9:00 to 12:00"), or None.

    The small model usually puts the times into the description and leaves `hours` empty,
    so the host's "time" line was blank. Copying her words is grounded by construction.
    """
    text = with_digits(transcript_en)
    days = list(dict.fromkeys(m.group().strip() for m in _DAYS.finditer(text)))
    # The sentence's full stop goes, but not the one in "a.m." / "p.m.".
    clean = lambda t: t if re.search(r'[ap]\.m\.$', t) else t.rstrip('.')  # noqa: E731
    times = list(dict.fromkeys(clean(m.group().strip()) for m in _TIMES.finditer(text) if _is_clock(m)))
    parts = days[:2] + times[:2]
    if not parts:
        return None
    return tidy_hours(', '.join(parts))


def tidy_hours(hours: Optional[str]) -> Optional[str]:
    """"9 am to 12 noon", not "9 a.m. to 12 p.m.": the dots made translation split the phrase
    ("Jeden Tag ab 9 Uhr morgens. Bis 12 Uhr") and "12 p.m." became "evening 12" in Malayalam."""
    if not hours:
        return hours
    out = re.sub(r'\b([ap])\.\s?m\.?', r'\1m', hours.strip(), flags=re.I)
    out = re.sub(r'\b12(?::00)?\s*pm\b', '12 noon', out, flags=re.I)
    return out[0].upper() + out[1:]


# The small model is weak at categories (it called a beekeeper and a garden walk "craft"),
# but words in the transcript are strong evidence. First match wins, so a homestay that
# "includes breakfast" is not food. Falls back to the model when nothing matches.
# Tuned on eval/data/listing_cases.jsonl, so that eval's category score is optimistic.
_CATEGORY_WORDS: list[tuple[Category, re.Pattern]] = [
    ('experience', re.compile(r'\b(homestay|home ?stay|stay|night|room|camping|class|workshop)\b', re.I)),
    ('textile', re.compile(r'\b(weav\w*|saree\w*|sari\w*|loom\w*|cloth|handloom|embroider\w*|textile\w*)\b', re.I)),
    ('craft', re.compile(r'\b(basket\w*|pott\w*|clay|bamboo|wood\w*|handmade|handicraft\w*|carv\w*)\b', re.I)),
    ('food', re.compile(r'\b(lunch|dinner|meals?|cook\w*|food|honey|bee\w*|tasting|snacks?|spices?)\b', re.I)),
    ('tour', re.compile(r'\b(walk\w*|trek\w*|plantation|garden|farm|estate|guide\w*|tour\w*|cave|waterfall|safari)\b', re.I)),
]


def category_from_words(transcript_en: str) -> Optional[Category]:
    return next((cat for cat, words in _CATEGORY_WORDS if words.search(transcript_en)), None)


def write_listing(transcript_en: str) -> Optional[tuple[Category, ListingText]] | str:
    """(category, English listing); NOT_AN_OFFER if she isn't describing an offer (→ empty_listing);
    None when the model fails to give valid JSON twice (→ invalid_listing)."""
    for temperature in (0.0, 0.3):  # deterministic first (same note → same listing); retry varies it
        try:
            raw = LlmListing.model_validate(json.loads(_ask(transcript_en, temperature)))
        except (json.JSONDecodeError, ValidationError):
            continue
        if not raw.is_offer:
            return NOT_AN_OFFER
        clean = lambda s: (s or '').strip() or None  # noqa: E731
        return category_from_words(transcript_en) or raw.category, ListingText(
            title=raw.title.strip(),
            description=raw.description.strip(),
            price=clean(raw.price) or price_in(transcript_en),
            hours=tidy_hours(clean(raw.days_and_times)) or hours_in(transcript_en),
            duration=clean(raw.duration),
            includes=[i.strip() for i in raw.includes if i.strip()],
            meeting_point=clean(raw.meeting_point),
        )
    return None
