"""The vendor's bot (WhatsApp or the /host web page): a small state machine stored on the vendor's row.

NEW → PROCESSING → AWAITING_APPROVAL → AWAITING_LOCATION → AWAITING_PRIVACY
    → (AWAITING_MEETING_POINT) → LIVE
PROCESSING can end in NEEDS_REVIEW ("not sure": nothing is published). A blurry or dark
photo is caught before the pipeline runs. Any state: ❌ hides the listing, "restart" starts over.
"""
from __future__ import annotations

import logging
import math
import threading
from collections import defaultdict
from dataclasses import dataclass, field

from . import channels, db, engine, retention
from .config import settings
from .photo import check_photo
from .prompts import LANGUAGE_COMMANDS, en, ml, parse_language

log = logging.getLogger("lantern.bot")


@dataclass
class Inbound:
    phone: str
    text: str = ""
    media: list[tuple[str, str]] = field(default_factory=list)  # (local path, content type)
    lat: float | None = None
    lon: float | None = None
    # Web page only: Malayalam typed instead of spoken (runs the pipeline from text).
    typed_text: str = ""
    # Telegram only: the sender's own number, shared with Telegram's "share phone number" button.
    contact_phone: str = ""

    @property
    def photo(self) -> str | None:
        return next((p for p, ct in self.media if ct.startswith("image/")), None)

    @property
    def audio(self) -> str | None:
        return next((p for p, ct in self.media if ct.startswith(("audio/", "video/webm"))), None)

    @property
    def has_voice(self) -> bool:
        return bool(self.audio or self.typed_text.strip())

    @property
    def has_location(self) -> bool:
        return self.lat is not None and self.lon is not None


def _norm(text: str) -> str:
    # Drop emoji variation selectors, keycap marks and skin tones so "👍🏽" == "👍" and "1️⃣" == "1".
    out = "".join(ch for ch in text if ch not in "️⃣" and not "\U0001f3fb" <= ch <= "\U0001f3ff")
    return out.strip().lower().translate(str.maketrans("൧൨൩", "123"))


APPROVE = {"👍", "yes", "ok", "okay", "ശരി", "അതെ"}
REDO = {"🔁", "🔄", "redo"}
HIDE = {"❌", "✖", "stop", "hide"}
CHECKIN = {"📍", "here", "ഇവിടെ"}
RESTART = {"restart", "start over"}


def needs_contact(v: dict) -> bool:
    """Telegram hosts must share their own number before anything else (WhatsApp/web already have it)."""
    return v["phone"].startswith("tg:") and not v.get("contact_phone")


def snap_to_grid(lat: float, lon: float, grid_m: float) -> tuple[float, float]:
    """Centre of the ~grid_m square containing the point; the exact spot is never stored."""
    lat_step = grid_m / 111_320
    lon_step = grid_m / (111_320 * max(math.cos(math.radians(lat)), 0.01))
    return (math.floor(lat / lat_step) + 0.5) * lat_step, (math.floor(lon / lon_step) + 0.5) * lon_step


# Re-entrant: when jobs run inline (tests), the job takes the same lock as the message that started it.
_locks: dict[str, threading.RLock] = defaultdict(threading.RLock)


def handle(msg: Inbound) -> None:
    """Process one inbound message. Messages from the same phone are handled in order."""
    with _locks[msg.phone]:
        try:
            _handle(msg)
        except Exception:
            log.exception("bot failed for %s", msg.phone)
            channels.send(msg.phone, "⚠️ Sorry, something went wrong on our side. Please try again.")
        finally:
            # Whatever the bot didn't keep (a rejected photo, a voice note sent while busy) is deleted now.
            v = db.get_or_create_vendor(msg.phone)
            for path, _ in msg.media:
                if path not in (v["photo_path"], v["audio_path"]):
                    retention.discard(path)


def _handle(msg: Inbound) -> None:
    v = db.get_or_create_vendor(msg.phone)
    say = lambda key: channels.send_prompt(msg.phone, key)  # noqa: E731
    cmd = _norm(msg.text)

    if cmd in RESTART:
        for path in (v["photo_path"], v["audio_path"]):
            retention.discard(path)
        retention.discard_readback(v["readback_audio"])
        db.update_vendor(v["id"], state="NEW", photo_path=None, audio_path=None, typed_text=None, draft_json=None,
                         readback_audio=None, review_reasons=None, voice_lang=None, consented=0)
        channels.send_language_choice(msg.phone)
        return
    if cmd in LANGUAGE_COMMANDS:
        db.update_vendor(v["id"], voice_lang=None)
        channels.send_language_choice(msg.phone)
        return
    if cmd in HIDE:
        if v["live"]:
            db.update_vendor(v["id"], hidden=1)
        say("hidden")
        return
    if not v["voice_lang"]:
        # Very first step: the host picks the language the bot writes and speaks in.
        lang = parse_language(cmd)
        if not lang:
            channels.send_language_choice(msg.phone)
            return
        v = db.update_vendor(v["id"], voice_lang=lang)
        if v["consented"]:  # just switching language
            say("approve_hint" if v["state"] == "AWAITING_APPROVAL" else "language_set")
            return
    if not v["consented"]:
        # Then explain what is shared publicly before anything else.
        v = db.update_vendor(v["id"], consented=1)
        say("welcome")
        if needs_contact(v):
            say("share_contact")
        return
    if needs_contact(v):
        # Telegram doesn't reveal the number tourists will message, so ask for it first.
        if msg.contact_phone:
            db.update_vendor(v["id"], contact_phone=msg.contact_phone)
            say("contact_thanks")
        else:
            say("share_contact")
        return

    state = v["state"]
    if state == "PROCESSING":
        say("still_processing")
        return
    if state in {"NEW", "NEEDS_REVIEW", "AWAITING_APPROVAL", "LIVE"} and (msg.photo or msg.has_voice):
        _collect(v, msg)
        return

    if state == "AWAITING_APPROVAL":
        if cmd in APPROVE:
            _approve(v)
        elif cmd in REDO:
            retention.discard_readback(v["readback_audio"])
            db.update_vendor(v["id"], state="NEW", audio_path=None, typed_text=None, readback_audio=None)
            say("rerecord")
        else:
            say("approve_hint")
    elif state == "AWAITING_LOCATION":
        if msg.has_location:
            db.update_vendor(v["id"], state="AWAITING_PRIVACY", pending_lat=msg.lat, pending_lon=msg.lon)
            say("privacy_choice")
        else:
            say("need_location")
    elif state == "AWAITING_PRIVACY":
        if cmd == "1":
            _go_live(v, v["pending_lat"], v["pending_lon"], "exact")
        elif cmd == "2":
            _go_live(v, *snap_to_grid(v["pending_lat"], v["pending_lon"], settings.area_grid_m), "area")
        elif cmd == "3":
            db.update_vendor(v["id"], state="AWAITING_MEETING_POINT", pending_lat=None, pending_lon=None)
            say("need_meeting_point")
        else:
            say("privacy_hint")
    elif state == "AWAITING_MEETING_POINT":
        if msg.has_location:
            _go_live(v, msg.lat, msg.lon, "meeting")
        else:
            say("need_meeting_point")
    elif state == "LIVE":
        if v["hidden"] and cmd in APPROVE:
            db.update_vendor(v["id"], hidden=0)
            say("shown_again")
        elif cmd in CHECKIN or msg.has_location:
            db.update_vendor(v["id"], last_checkin=db.now())  # a check-in never moves the pin
            say("checkin")
        else:
            say("live")
    elif state == "NEEDS_REVIEW":
        say("not_sure")
    else:  # NEW with nothing usable yet
        say("need_voice" if v["photo_path"] else "welcome")


def _collect(v: dict, msg: Inbound) -> None:
    """Store a photo and/or voice note; start the pipeline once both are present."""
    updates: dict = {}
    if msg.photo:
        check = check_photo(msg.photo)
        if not check.ok:
            retention.discard(v["photo_path"])
            db.update_vendor(v["id"], photo_path=None, state="LIVE" if v["state"] == "LIVE" else "NEW")
            channels.send_prompt(msg.phone, f"retake_{check.problem}")
            return
        # Kept without metadata (a phone photo's EXIF holds the exact GPS spot); the old one goes.
        retention.discard(v["photo_path"])
        updates["photo_path"] = str(retention.clean_photo(msg.photo))
    if msg.audio:
        updates.update(audio_path=msg.audio, typed_text=None)
    elif msg.typed_text.strip():
        updates.update(typed_text=msg.typed_text.strip(), audio_path=None)
    v = db.update_vendor(v["id"], **updates)

    has_voice = bool(v["audio_path"] or v["typed_text"])
    if not v["photo_path"]:
        channels.send_prompt(msg.phone, "need_photo")
    elif not has_voice or (v["state"] in {"AWAITING_APPROVAL", "LIVE"} and not msg.has_voice):
        # A new photo alone while approving or live waits for a fresh voice note.
        channels.send_prompt(msg.phone, "need_voice" if v["state"] == "NEW" else "rerecord")
    else:
        _start_pipeline(v)


def _start_pipeline(v: dict) -> None:
    was_live = v["state"] == "LIVE"
    db.update_vendor(v["id"], state="PROCESSING")
    channels.send_prompt(v["phone"], "update_received" if was_live else "processing")
    vid, phone, audio, typed = v["id"], v["phone"], v["audio_path"], v["typed_text"]

    def job() -> None:
        try:
            result = engine.process(audio_path=audio, typed_text=typed)
        except Exception:
            log.exception("pipeline crashed for vendor %s", vid)
            result = None
        finally:
            retention.discard(audio)  # the voice note is deleted once transcribed; the text is kept
        with _locks[phone]:
            _apply_result(vid, was_live, result)

    engine.submit(job)


def _apply_result(vendor_id: int, was_live: bool, result) -> None:
    v = db.get_vendor(vendor_id)
    if result is not None:
        for t in result.timings:
            db.add_metric(vendor_id, t.stage, t.seconds, "mock" if settings.mock_ai else "real")
        db.add_metric(vendor_id, "total", sum(t.seconds for t in result.timings))
    fields = {}
    if result is not None:
        fields = dict(transcript=result.transcript, transcript_en=result.transcript_en, asr_confidence=result.asr_confidence)

    if result is None or result.status == "needs_review" or not result.listing:
        # "Not sure, ask a person": nothing is published. A live listing stays as it was.
        reasons = ",".join(result.reasons) if result is not None else "pipeline_error"
        db.update_vendor(vendor_id, state="LIVE" if was_live else "NEEDS_REVIEW", review_reasons=reasons,
                         audio_path=None, typed_text=None, **fields)
        channels.send_prompt(v["phone"], "not_sure")
        return

    t = result.listing.text["en"]
    if v["voice_lang"] == "en":
        # The pipeline reads back in Malayalam; English hosts hear the English listing instead.
        readback = english_readback(t)
        audio = engine.speak(readback, "en")
        retention.discard_readback(result.readback_wav)  # the unused Malayalam one
    else:
        readback = result.readback_text
        audio = engine.to_ogg(result.readback_wav) if result.readback_wav else None
    retention.discard_readback(v["readback_audio"])  # an earlier draft's
    db.update_vendor(
        vendor_id, state="AWAITING_APPROVAL", draft_json=result.listing.model_dump_json(), audio_path=None, typed_text=None,
        readback_text=readback, readback_audio=str(audio) if audio else None, review_reasons=None, **fields,
    )
    summary = listing_summary(t)
    hint = en("approve_hint") if v["voice_lang"] != "en" else ml("approve_hint")
    channels.send(v["phone"], f"🔊 {readback}\n\n_{hint}_\n\n{summary}", audio)


def listing_summary(t) -> str:
    """The draft as the host sees it in the chat: service, location and cost on separate lines."""
    return "\n".join(filter(None, [
        f"*{t.title}*",
        f"🛎 Service: {t.description}",
        f"📍 Location: {t.location}" if getattr(t, "location", None) else None,
        f"💰 Cost: {t.price}" if t.price else "💰 Cost: not mentioned",
        f"🕘 Time: {t.hours}" if t.hours else None,
    ]))


def english_readback(t) -> str:
    """What an English-speaking host hears before approving: the listing tourists will see."""
    parts = ["This is what tourists will see.", f"{t.title}.", t.description]
    for label, value in (("Location", getattr(t, "location", None)), ("Cost", t.price), ("Hours", t.hours),
                         ("Duration", t.duration), ("Meeting point", t.meeting_point)):
        if value:
            parts.append(f"{label}: {value}.")
    if t.includes:
        parts.append(f"Included: {', '.join(t.includes)}.")
    parts.append(en("approve_hint"))
    return " ".join(parts)


def _approve(v: dict) -> None:
    retention.discard_readback(v["readback_audio"])
    v = db.update_vendor(v["id"], listing_json=v["draft_json"], draft_json=None, readback_audio=None)
    if v["lat"] is not None:
        # Updating an existing listing: keep the location and privacy she already chose.
        db.update_vendor(v["id"], state="LIVE", live=1, hidden=0)
        channels.send_prompt(v["phone"], "live")
    else:
        db.update_vendor(v["id"], state="AWAITING_LOCATION")
        channels.send_prompt(v["phone"], "approved_need_location")


def _go_live(v: dict, lat: float, lon: float, privacy: str) -> None:
    db.update_vendor(v["id"], state="LIVE", lat=lat, lon=lon, privacy=privacy, pending_lat=None, pending_lon=None,
                     live=1, hidden=0, last_checkin=db.now())
    channels.send_prompt(v["phone"], "live")
