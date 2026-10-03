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
from .models import llm_path
from .schema import Category, ListingText


# Field order matters for a small model: it fills the facts first, then writes from them.
class LlmListing(BaseModel):
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
- Use ONLY facts stated in the transcript. Never add prices, times, durations, places or claims she did not say.
- Fill price, days_and_times (which days, what time it starts), duration (how long it lasts), includes and
  meeting_point whenever she states them; use null (or []) only if she did not.
- category is one of: food, craft, textile, tour, experience, other.
- title: at most 8 words, naming what she offers.
- description: 2 short sentences in your own words, written for a tourist, only about what she said. Do not quote her.
Reply with JSON only."""

# One worked example (synthetic, a different business so it can't be copied into her listing).
EXAMPLE_IN = ('My name is Lakshmi. I make banana chips and halwa at home in Thrissur. You can watch and taste. '
              'It takes one hour. 300 rupees for each person. Every day except Sunday, 3 in the afternoon.')
EXAMPLE_OUT = {
    'category': 'food', 'price': '300 rupees per person', 'days_and_times': 'Every day except Sunday, 3 pm',
    'duration': 'One hour', 'includes': ['Tasting'], 'meeting_point': None,
    'title': 'Home Kitchen Snack Making in Thrissur',
    'description': 'Watch banana chips and halwa being made in a family kitchen in Thrissur. '
                   'Taste them fresh at the end.',
}


@lru_cache(maxsize=None)
def _llm():
    from llama_cpp import Llama
    return Llama(model_path=str(llm_path()), n_ctx=2048, n_threads=config.CPU_THREADS, verbose=False)


def _ask(transcript_en: str, temperature: float) -> str:
    out = _llm().create_chat_completion(
        messages=[
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': f'Transcript:\n"""{EXAMPLE_IN}"""'},
            {'role': 'assistant', 'content': json.dumps(EXAMPLE_OUT)},
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


def write_listing(transcript_en: str) -> Optional[tuple[Category, ListingText]]:
    """None when the model fails to give valid JSON twice (→ invalid_listing)."""
    for temperature in (0.0, 0.3):  # deterministic first (same note → same listing); retry varies it
        try:
            raw = LlmListing.model_validate(json.loads(_ask(transcript_en, temperature)))
        except (json.JSONDecodeError, ValidationError):
            continue
        clean = lambda s: (s or '').strip() or None  # noqa: E731
        return raw.category, ListingText(
            title=raw.title.strip(),
            description=raw.description.strip(),
            price=clean(raw.price) or price_in(transcript_en),
            hours=clean(raw.days_and_times),
            duration=clean(raw.duration),
            includes=[i.strip() for i in raw.includes if i.strip()],
            meeting_point=clean(raw.meeting_point),
        )
    return None
