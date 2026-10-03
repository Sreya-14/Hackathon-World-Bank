"""Where bot replies go: Twilio WhatsApp for "whatsapp:" numbers, the /host web page for "web:" numbers."""
from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

import httpx

from . import db, engine
from .config import settings
from .prompts import en, ml

_twilio = None


def _client():
    global _twilio
    if _twilio is None:
        from twilio.rest import Client

        _twilio = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _twilio


def media_url(path: str | Path | None) -> str | None:
    """Public URL for a file under MEDIA_DIR; None for anything else (never serve arbitrary paths)."""
    if not path:
        return None
    try:
        rel = Path(path).resolve().relative_to(settings.media_dir.resolve())
    except ValueError:
        return None
    return f"{settings.public_base_url}/media/{rel.as_posix()}"


def send(phone: str, text: str, audio: str | Path | None = None) -> None:
    url = media_url(audio)
    if not phone.startswith("whatsapp:") or not settings.twilio_enabled:
        db.add_web_message(phone, text, url)
        return
    client = _client()
    client.messages.create(from_=settings.twilio_whatsapp_from, to=phone, body=text)
    if url:
        # WhatsApp audio can't carry a caption, so the clip goes as its own message.
        client.messages.create(from_=settings.twilio_whatsapp_from, to=phone, media_url=[url])


def send_prompt(phone: str, key: str) -> None:
    """A fixed prompt: Malayalam text + English gloss, plus its Malayalam audio clip."""
    send(phone, f"🔊 {ml(key)}\n\n_{en(key)}_", engine.speak(ml(key)))


def save_upload(data: bytes, content_type: str, phone: str) -> Path:
    ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or ".bin"
    ext = {".oga": ".ogg", ".weba": ".webm"}.get(ext, ext)
    folder = settings.media_dir / "uploads" / uuid.uuid5(uuid.NAMESPACE_URL, phone).hex[:12]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)
    return path


def download_twilio_media(url: str, content_type: str, phone: str) -> Path:
    resp = httpx.get(url, auth=(settings.twilio_account_sid, settings.twilio_auth_token), follow_redirects=True, timeout=30)
    resp.raise_for_status()
    return save_upload(resp.content, content_type or resp.headers.get("content-type", ""), phone)
