"""THE CONTRACT between the ML pipeline (engine) and the backend/bot.

The backend calls `process_voice_note()` (see pipeline/__init__.py) and gets a
`PipelineResult`. Change these types only by agreement.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal['food', 'craft', 'textile', 'tour', 'experience', 'other']
ListingLang = Literal['en', 'de']

ReviewReason = Literal[
    'no_speech',          # silence or noise only
    'unclear_audio',      # low transcription confidence
    'wrong_language',     # not Malayalam
    'unclear_translation',  # the English is much shorter than what she said: content was lost
    'empty_listing',      # nothing usable to list (no category/description)
    'invalid_listing',    # the LLM did not return valid JSON, even after a retry
    'ungrounded_fact',    # price/hours/number in the listing that she never said
]


class ListingText(BaseModel):
    """One language's version. Facts are only filled if Noor said them; otherwise None. Never guessed."""
    title: str
    description: str
    price: Optional[str] = Field(None, description='As she said it, e.g. "1500 rupees per person"')
    hours: Optional[str] = Field(None, description='Days and times, e.g. "Monday to Saturday, 9am to 1pm"')
    duration: Optional[str] = None
    includes: list[str] = Field(default_factory=list)
    meeting_point: Optional[str] = None


class Listing(BaseModel):
    category: Category
    text: dict[ListingLang, ListingText]
    machine_translated: list[ListingLang] = Field(
        default_factory=list, description='Languages produced by translation, to label in the UI')


class StageTiming(BaseModel):
    stage: Literal['asr', 'to_english', 'listing', 'to_listing_langs', 'readback']
    seconds: float


class PipelineResult(BaseModel):
    status: Literal['ready_for_approval', 'needs_review']
    reasons: list[ReviewReason] = Field(default_factory=list)
    transcript: str = Field('', description="What Noor said, in Malayalam")
    transcript_en: str = ''
    asr_confidence: float = Field(0.0, description='0..1, mean token probability')
    listing: Optional[Listing] = None
    readback_text: str = Field('', description='Malayalam text that was spoken back to Noor')
    readback_wav: Optional[str] = Field(None, description='Path to the WAV file to send her')
    timings: list[StageTiming] = Field(default_factory=list)
