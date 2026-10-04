"""End-to-end bot flow against the mock pipeline (same PipelineResult contract as ml/pipeline)."""
import json

from fastapi.testclient import TestClient

from app import db
from app.bot import Inbound, handle, snap_to_grid
from app.main import app

PHONE = "web:+919800000001"


def send(**kw) -> dict:
    handle(Inbound(phone=PHONE, **kw))
    return db.get_or_create_vendor(PHONE)


def texts() -> list[str]:
    return [m["text"] or "" for m in db.web_messages(PHONE)]


def begin(lang: str = "മലയാളം") -> dict:
    """First contact: the bot asks for a language, the host picks one and gets the welcome."""
    send(text="hi")
    return send(text=lang)


def submit(photo: str, audio: str) -> dict:
    if not db.get_or_create_vendor(PHONE)["voice_lang"]:
        begin()
    return send(media=[(photo, "image/jpeg"), (audio, "audio/ogg")])


def go_live(photo, audio, privacy="1"):
    submit(photo, audio)
    send(text="👍")
    send(lat=11.60851, lon=76.08302)
    return send(text=privacy)


def test_voice_note_to_live_listing_with_area_privacy(sharp_photo, voice_note):
    v = submit(sharp_photo, voice_note)
    assert v["state"] == "AWAITING_APPROVAL"
    first = db.web_messages(PHONE)[0]
    assert "Which language" in first["text"] and first["media_url"] is None  # language first, no audio yet
    assert "Welcome to Lantern" in texts()[1]  # then consent
    assert any("preparing your listing" in t for t in texts())
    draft = json.loads(v["draft_json"])
    assert draft["category"] == "tour" and draft["text"]["en"]["price"] == "500 rupees per person"
    assert v["readback_audio"].endswith(".ogg")  # WhatsApp-playable
    assert not v["live"]  # nothing is public before approval

    assert send(text="👍🏽")["state"] == "AWAITING_LOCATION"
    assert send(lat=11.60851, lon=76.08302)["state"] == "AWAITING_PRIVACY"
    v = send(text="2️⃣")
    assert v["state"] == "LIVE" and v["privacy"] == "area"
    assert (v["lat"], v["lon"]) == snap_to_grid(11.60851, 76.08302, 200) and v["pending_lat"] is None

    client = TestClient(app)
    [feat] = client.get("/api/listings").json()["features"]
    p = feat["properties"]
    assert p["title"]["en"] and p["title"]["de"] and p["price"] == "500 rupees per person"
    assert p["machine_translated"] == ["de"] and p["radius_m"] == 200
    assert "whatsapp_url" not in p
    [b] = client.get("/api/bundle").json()["features"]
    assert b["properties"]["whatsapp_url"].startswith("https://wa.me/919800000001?text=")
    links = client.post(f"/api/listings/{v['id']}/contact").json()
    assert links["whatsapp_url"].startswith("https://wa.me/919800000001?text=")
    assert links["sms_url"].startswith("sms:+919800000001?&body=")  # SMS works without mobile data
    assert b["properties"]["sms_url"] == links["sms_url"]  # the offline bundle carries both


def test_typed_malayalam_fallback(sharp_photo):
    begin()
    send(media=[(sharp_photo, "image/jpeg")])
    assert "voice note" in texts()[-1]
    v = send(typed_text="ഞാൻ ഒരു മുള കരകൗശല ക്ലാസ് നടത്തുന്നു, ഒരാൾക്ക് 300 രൂപ")
    assert v["state"] == "AWAITING_APPROVAL" and json.loads(v["draft_json"])["category"] == "craft"


def test_blurry_photo_is_rejected_before_the_pipeline(blurry_photo, voice_note):
    v = submit(blurry_photo, voice_note)
    assert v["state"] == "NEW" and v["photo_path"] is None
    assert "isn't clear" in texts()[-1]
    assert db.metric_summary() == []  # the pipeline never ran


def test_needs_review_publishes_nothing(sharp_photo):
    begin()
    send(media=[(sharp_photo, "image/jpeg")])
    v = send(typed_text="unclear")
    assert v["state"] == "NEEDS_REVIEW" and not v["live"] and v["review_reasons"] == "unclear_audio"
    assert "not sure" in texts()[-1]


def test_meeting_point_checkin_and_hide(sharp_photo, voice_note):
    submit(sharp_photo, voice_note)
    send(text="👍")
    send(lat=11.6, lon=76.08)
    assert send(text="3")["state"] == "AWAITING_MEETING_POINT"
    v = send(lat=11.61, lon=76.09)
    assert v["privacy"] == "meeting" and (v["lat"], v["lon"]) == (11.61, 76.09)
    assert send(text="📍")["lat"] == 11.61  # check-in doesn't move the pin
    client = TestClient(app)
    assert send(text="❌")["hidden"] and client.get("/api/listings").json()["features"] == []
    assert send(text="👍")["hidden"] == 0


def test_three_reports_hide_a_listing(sharp_photo, voice_note):
    v = go_live(sharp_photo, voice_note)
    client = TestClient(app)
    for _ in range(3):
        client.post(f"/api/listings/{v['id']}/report")
    assert client.get("/api/listings").json()["features"] == []


def test_host_page_endpoints(sharp_photo):
    client = TestClient(app)
    assert client.get("/host").status_code == 200
    assert client.post("/host/api/send", data={"number": "12"}).status_code == 400
    r = client.post("/host/api/send", data={"number": "+91 98000 00001", "text": "hi"})
    assert r.status_code == 200
    msgs = client.get("/host/api/messages", params={"number": "+919800000001"}).json()
    assert msgs["vendor"]["state"] == "NEW" and "Which language" in msgs["messages"][0]["text"]
    client.post("/host/api/send", data={"number": "+91 98000 00001", "text": "English"})
    msgs = client.get("/host/api/messages", params={"number": "+919800000001"}).json()
    assert msgs["vendor"]["voice_lang"] == "en" and msgs["messages"][-1]["text"].startswith("🔊 Hello! Welcome to Lantern")


def test_metrics_logged_per_stage(sharp_photo, voice_note):
    submit(sharp_photo, voice_note)
    stages = {s["stage"] for s in TestClient(app).get("/api/metrics").json()["stages"]}
    assert {"asr", "to_english", "listing", "readback", "total"} <= stages


def test_language_choice_drives_text_voice_and_readback(sharp_photo, voice_note):
    send(text="hi")
    assert db.get_or_create_vendor(PHONE)["voice_lang"] is None
    send(text="something else")  # anything but a language: asked again
    assert "Which language" in texts()[-1]
    begin("English")
    welcome = db.web_messages(PHONE)[-1]
    assert welcome["text"].startswith("🔊 Hello! Welcome to Lantern") and welcome["media_url"].endswith(".ogg")

    v = submit(sharp_photo, voice_note)
    assert v["state"] == "AWAITING_APPROVAL"
    assert v["readback_text"].startswith("This is what tourists will see.")  # English read-back, not Malayalam
    assert "500 rupees per person" in v["readback_text"] and v["readback_audio"].endswith(".ogg")

    send(text="language")
    send(text="മലയാളം")
    assert db.get_or_create_vendor(PHONE)["voice_lang"] == "ml" and db.get_or_create_vendor(PHONE)["state"] == "AWAITING_APPROVAL"
    assert texts()[-1].startswith("🔊 ശരിയാണെങ്കിൽ")  # back to the approve hint, now in Malayalam

    send(text="restart")
    v = db.get_or_create_vendor(PHONE)
    assert v["voice_lang"] is None and v["state"] == "NEW" and "Which language" in texts()[-1]


def test_voice_notes_and_photo_metadata_are_not_kept(sharp_photo, voice_note):
    """The retention rule in the welcome message: voice deleted once transcribed, photo kept without EXIF."""
    from pathlib import Path

    from PIL import Image

    from app import channels, retention

    # A phone photo whose EXIF carries a GPS position, uploaded the way Telegram/WhatsApp/web save it.
    gps_photo = Path(sharp_photo).with_name("gps.jpg")
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (11.0, 36.0, 30.6), 3: "E", 4: (76.0, 4.0, 58.9)}  # GPSInfo
    Image.open(sharp_photo).save(gps_photo, exif=exif)
    assert Image.open(gps_photo).getexif().get_ifd(0x8825)
    photo = str(channels.save_upload(gps_photo.read_bytes(), "image/jpeg", PHONE))
    audio = str(channels.save_upload(Path(voice_note).read_bytes(), "audio/ogg", PHONE))

    v = submit(photo, audio)
    assert v["state"] == "AWAITING_APPROVAL"
    assert not Path(audio).exists() and v["audio_path"] is None  # transcribed, then deleted
    assert not Path(photo).exists()  # the original upload is gone
    kept = Path(v["photo_path"])
    assert kept.parent == retention.PHOTOS and not Image.open(kept).getexif()  # no GPS, no camera, no time
    readback = Path(v["readback_audio"])
    assert readback.exists()

    v = send(text="👍")
    assert not readback.exists() and v["readback_audio"] is None  # deleted once approved
    assert channels.media_url(kept).endswith(f"/media/photos/{kept.name}")
    assert channels.media_url(photo) is None  # uploads are never public

    # A photo the bot doesn't use (here: sent while it waits for a location) isn't kept either.
    stray = str(channels.save_upload(Path(sharp_photo).read_bytes(), "image/jpeg", PHONE))
    send(media=[(stray, "image/jpeg")])
    assert not Path(stray).exists() and kept.exists()
    v = send(text="restart")  # starting over removes the listing photo too
    assert v["photo_path"] is None and not kept.exists() and not any(retention.UPLOADS.rglob("*.*"))
