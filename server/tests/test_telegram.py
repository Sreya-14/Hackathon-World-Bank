"""Telegram channel: reading updates, the share-your-number gate, and step buttons."""
import json

from fastapi.testclient import TestClient

from app import db, telegram
from app.bot import Inbound, handle
from app.main import app

CHAT = "tg:555001"


def update(**message) -> dict:
    return {"update_id": 1, "message": {"chat": {"id": 555001, "type": "private"}, "from": {"id": 555001}, **message}}


def texts() -> list[str]:
    return [m["text"] or "" for m in db.web_messages(CHAT)]  # without a token, tg: replies land in the web outbox


def test_reads_text_commands_location_and_own_contact():
    assert telegram.to_inbound(update(text="/start")).text == "hi"
    loc = telegram.to_inbound(update(location={"latitude": 11.6, "longitude": 76.08}))
    assert (loc.lat, loc.lon) == (11.6, 76.08)
    own = telegram.to_inbound(update(contact={"phone_number": "447833000000", "user_id": 555001}))
    assert own.contact_phone == "+447833000000"
    # A forwarded contact card is someone else's number: ignored.
    other = telegram.to_inbound(update(contact={"phone_number": "447800000001", "user_id": 999}))
    assert other.contact_phone == ""
    # Group chats are ignored.
    assert telegram.to_inbound({"update_id": 2, "message": {"chat": {"id": 1, "type": "group"}, "text": "hi"}}) is None


def test_host_must_share_own_number_first(sharp_photo, voice_note):
    handle(Inbound(phone=CHAT, text="hi"))
    assert "Which language" in texts()[-1]
    handle(Inbound(phone=CHAT, text="മലയാളം"))
    assert "Welcome to Lantern" in texts()[-2] and "share your phone number" in texts()[-1]
    handle(Inbound(phone=CHAT, media=[(sharp_photo, "image/jpeg")]))
    assert "share your phone number" in texts()[-1]  # nothing else until the number is shared
    assert db.get_or_create_vendor(CHAT)["photo_path"] is None

    handle(Inbound(phone=CHAT, contact_phone="+447833000000"))
    assert "send a photo" in texts()[-1]
    handle(Inbound(phone=CHAT, media=[(sharp_photo, "image/jpeg"), (voice_note, "audio/ogg")]))
    assert db.get_or_create_vendor(CHAT)["state"] == "AWAITING_APPROVAL"
    for step in (dict(text="👍"), dict(lat=11.6, lon=76.08), dict(text="1")):
        handle(Inbound(phone=CHAT, **step))
    assert db.get_or_create_vendor(CHAT)["state"] == "LIVE"

    # Tourists reach the host on WhatsApp at the number they shared, not the chat id.
    [feat] = TestClient(app).get("/api/bundle").json()["features"]
    assert feat["properties"]["whatsapp_url"].startswith("https://wa.me/447833000000?text=")


def test_buttons_follow_the_step(sharp_photo, voice_note):
    handle(Inbound(phone=CHAT, text="hi"))
    assert [b["text"] for b in telegram._keyboard(CHAT)["keyboard"][0]] == ["മലയാളം", "English"]
    handle(Inbound(phone=CHAT, text="English"))
    assert telegram._keyboard(CHAT)["keyboard"][0][0]["request_contact"] is True
    handle(Inbound(phone=CHAT, contact_phone="+447833000000"))
    handle(Inbound(phone=CHAT, media=[(sharp_photo, "image/jpeg"), (voice_note, "audio/ogg")]))
    assert [b["text"] for b in telegram._keyboard(CHAT)["keyboard"][0]] == ["👍", "🔁"]
    handle(Inbound(phone=CHAT, text="👍"))
    assert telegram._keyboard(CHAT)["keyboard"][0][0]["request_location"] is True
    handle(Inbound(phone=CHAT, lat=11.6, lon=76.08))
    assert [b["text"] for b in telegram._keyboard(CHAT)["keyboard"][0]] == ["1", "2", "3"]


def test_plain_text_for_telegram():
    assert telegram._plain("*Coffee walk*\n_If it's right, send 👍._") == "Coffee walk\nIf it's right, send 👍."
    assert json.dumps(telegram._plain("snake_case_name stays")) == json.dumps("snake_case_name stays")
