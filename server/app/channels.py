"""Where bot replies go: WhatsApp (Twilio) for "whatsapp:", Telegram for "tg:", the /host web page for "web:"."""
from __future__ import annotations

import logging
import mimetypes
import uuid
from pathlib import Path

import httpx

from . import db, engine
from .config import settings
from .prompts import en, ml

log = logging.getLogger("lantern.channels")

_twilio = None


def _client():
    global _twilio
    if _twilio is None:
        from twilio.rest import Client

        user, password = settings.twilio_credentials
        _twilio = Client(user, password, settings.twilio_account_sid)
    return _twilio


# Served at /media. Not uploads/: hosts' original voice notes and photos are never public.
PUBLIC_MEDIA = ("photos", "prompts", "readback")


def media_url(path: str | Path | None) -> str | None:
    """Public URL for a file in a PUBLIC_MEDIA folder; None for anything else (never serve arbitrary paths)."""
    if not path:
        return None
    try:
        rel = Path(path).resolve().relative_to(settings.media_dir.resolve())
    except ValueError:
        return None
    if rel.parts[0] not in PUBLIC_MEDIA:
        return None
    return f"{settings.public_base_url}/media/{rel.as_posix()}"


def send(phone: str, text: str, audio: str | Path | None = None) -> None:
    from . import telegram

    if phone.startswith("tg:") and telegram.enabled():
        telegram.send(phone, text, audio)
        return
    url = media_url(audio)
    if not phone.startswith("whatsapp:") or not settings.twilio_enabled:
        db.add_web_message(phone, text, url)
        return
    from twilio.base.exceptions import TwilioRestException

    client = _client()
    try:
        client.messages.create(from_=settings.twilio_whatsapp_from, to=phone, body=text)
        if url:
            # WhatsApp audio can't carry a caption, so the clip goes as its own message.
            client.messages.create(from_=settings.twilio_whatsapp_from, to=phone, media_url=[url])
    except TwilioRestException as e:
        # E.g. the number hasn't joined the sandbox, or the 24 h session window has closed.
        # Log it; a failed reply must not break the bot's state handling.
        log.error("WhatsApp send to %s failed: %s %s", phone, e.code, e.msg)


def host_language(phone: str) -> str:
    row = db.db.one("SELECT voice_lang FROM vendors WHERE phone = ?", (phone,))
    return (row and row["voice_lang"]) or settings.prompt_voice


def send_prompt(phone: str, key: str) -> None:
    """A fixed prompt as text plus a voice clip, in the language the host chose."""
    from .prompts import say

    lang = host_language(phone)
    clip = engine.speak(en(key), "en") if lang == "en" else engine.speak(ml(key))
    send(phone, say(key, lang), clip)


def send_language_choice(phone: str) -> None:
    """Asked before anything else: the question in both languages, text only.
    Voice clips start once the host has picked a language."""
    send(phone, f"🌐 {ml('choose_language')}\n\n{en('choose_language')}")


def save_upload(data: bytes, content_type: str, phone: str) -> Path:
    ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or ".bin"
    ext = {".oga": ".ogg", ".weba": ".webm"}.get(ext, ext)
    folder = settings.media_dir / "uploads" / uuid.uuid5(uuid.NAMESPACE_URL, phone).hex[:12]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)
    return path


def download_twilio_media(url: str, content_type: str, phone: str) -> Path:
    resp = httpx.get(url, auth=settings.twilio_credentials, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    return save_upload(resp.content, content_type or resp.headers.get("content-type", ""), phone)
