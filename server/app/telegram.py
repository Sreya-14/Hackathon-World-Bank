"""Telegram channel for hosts: free, and the plan's backup for when WhatsApp isn't available.

Uses long polling (getUpdates), so the server needs no public URL for it. Hosts are "tg:<chat id>";
before anything else they share their own phone number (Telegram only allows sharing your own),
and tourists contact them on WhatsApp at that number.
"""
from __future__ import annotations

import logging
import queue
import re
import threading
import time
from pathlib import Path

import httpx

from . import db
from .config import settings

log = logging.getLogger("lantern.telegram")
API = "https://api.telegram.org"

# Telegram returns a file id for each upload; reuse it so fixed prompt clips are sent only once.
_voice_ids: dict[str, str] = {}


def enabled() -> bool:
    return bool(settings.telegram_bot_token)


def _url(method: str) -> str:
    return f"{API}/bot{settings.telegram_bot_token}/{method}"


def _call(method: str, timeout: float = 30, **kw) -> dict:
    resp = httpx.post(_url(method), timeout=timeout, **kw)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data.get('description')}")
    return data["result"]


# --- Outgoing ------------------------------------------------------------------------

def _keyboard(phone: str) -> dict:
    """Buttons for the host's current step, so they rarely need to type."""
    from .prompts import LANGUAGES

    v = db.db.one("SELECT state, hidden, contact_phone, voice_lang FROM vendors WHERE phone = ?", (phone,))
    if not v or not v["voice_lang"]:
        rows = [[{"text": label} for label, _ in LANGUAGES.values()]]
    elif not v["contact_phone"]:
        rows = [[{"text": "📱 ഫോൺ നമ്പർ പങ്കിടുക · Share my phone number", "request_contact": True}]]
    elif v["state"] == "AWAITING_APPROVAL":
        rows = [[{"text": "👍"}, {"text": "🔁"}]]
    elif v["state"] in ("AWAITING_LOCATION", "AWAITING_MEETING_POINT"):
        rows = [[{"text": "📍 ലൊക്കേഷൻ അയയ്ക്കുക · Send location", "request_location": True}]]
    elif v["state"] == "AWAITING_PRIVACY":
        rows = [[{"text": "1"}, {"text": "2"}, {"text": "3"}]]
    elif v["state"] == "LIVE":
        rows = [[{"text": "👍" if v["hidden"] else "📍"}, {"text": "❌"}]]
    else:
        return {"remove_keyboard": True}
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


def _plain(text: str) -> str:
    # The bot's texts use WhatsApp-style *bold* and _italic_; Telegram gets them as plain text.
    return re.sub(r"(?<!\w)[*_]([^*_\n]+)[*_](?!\w)", r"\1", text)


def send(phone: str, text: str, audio: str | Path | None = None) -> None:
    chat_id = phone.removeprefix("tg:")
    markup = _keyboard(phone)
    try:
        _call("sendMessage", json={"chat_id": chat_id, "text": _plain(text), "reply_markup": markup})
        if audio:
            key = str(audio)
            if key in _voice_ids:
                _call("sendVoice", json={"chat_id": chat_id, "voice": _voice_ids[key]})
            else:
                with open(audio, "rb") as f:
                    result = _call("sendVoice", data={"chat_id": chat_id}, files={"voice": ("voice.ogg", f, "audio/ogg")}, timeout=60)
                if "/prompts/" in key:  # fixed clips: same file every time
                    _voice_ids[key] = result["voice"]["file_id"]
    except Exception as e:
        log.error("Telegram send to %s failed: %s", phone, e)


# --- Incoming ------------------------------------------------------------------------

def _download(file_id: str, content_type: str, phone: str) -> str:
    from .channels import save_upload

    info = _call("getFile", json={"file_id": file_id})
    resp = httpx.get(f"{API}/file/bot{settings.telegram_bot_token}/{info['file_path']}", timeout=60)
    resp.raise_for_status()
    return str(save_upload(resp.content, content_type, phone))


def to_inbound(update: dict):
    """A Telegram update → the bot's Inbound message (None for updates the bot ignores)."""
    from .bot import Inbound

    m = update.get("message")
    if not m or m.get("chat", {}).get("type") != "private":
        return None
    phone = f"tg:{m['chat']['id']}"
    text = m.get("text") or m.get("caption") or ""
    if text.startswith("/start"):
        text = "hi"
    elif text.startswith("/restart"):
        text = "restart"
    msg = Inbound(phone=phone, text=text)

    if m.get("photo"):  # sizes, smallest first
        msg.media.append((_download(m["photo"][-1]["file_id"], "image/jpeg", phone), "image/jpeg"))
    elif m.get("document", {}).get("mime_type", "").startswith("image/"):
        doc = m["document"]
        msg.media.append((_download(doc["file_id"], doc["mime_type"], phone), doc["mime_type"]))
    voice = m.get("voice") or m.get("audio")
    if voice:
        ct = voice.get("mime_type", "audio/ogg")
        msg.media.append((_download(voice["file_id"], ct, phone), ct))
    if m.get("location"):
        msg.lat, msg.lon = m["location"]["latitude"], m["location"]["longitude"]
    contact = m.get("contact")
    # Only the sender's own number counts (a forwarded contact card is someone else's).
    if contact and contact.get("user_id") == m.get("from", {}).get("id"):
        msg.contact_phone = "+" + re.sub(r"\D", "", contact["phone_number"])
    return msg


_inbox: "queue.Queue" = queue.Queue()


def _dispatch() -> None:
    """Handle updates one at a time, in the order Telegram delivered them."""
    from .bot import handle

    while True:
        update = _inbox.get()
        try:
            msg = to_inbound(update)
            if msg:
                handle(msg)
        except Exception:
            log.exception("could not handle Telegram update")


def _poll() -> None:
    offset = 0
    try:
        _call("deleteWebhook")  # polling and a webhook can't both be active
        me = _call("getMe")
        log.info("Telegram bot @%s is polling for messages", me.get("username"))
    except Exception as e:
        log.error("Telegram start failed (check TELEGRAM_BOT_TOKEN): %s", e)
        return
    while True:
        try:
            updates = _call("getUpdates", timeout=60, json={"offset": offset, "timeout": 50,
                                                            "allowed_updates": ["message"]})
        except Exception as e:
            log.warning("Telegram polling error: %s; retrying", e)
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            _inbox.put(u)


def start() -> None:
    if enabled():
        threading.Thread(target=_dispatch, name="telegram-dispatch", daemon=True).start()
        threading.Thread(target=_poll, name="telegram-poll", daemon=True).start()
