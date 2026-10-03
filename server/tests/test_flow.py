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


def submit(photo: str, audio: str) -> dict:
    return send(media=[(photo, "image/jpeg"), (audio, "audio/ogg")])


def go_live(photo, audio, privacy="1"):
    submit(photo, audio)
    send(text="👍")
    send(lat=11.60851, lon=76.08302)
    return send(text=privacy)


def test_voice_note_to_live_listing_with_area_privacy(sharp_photo, voice_note):
    v = submit(sharp_photo, voice_note)
    assert v["state"] == "AWAITING_APPROVAL"
    assert "Welcome to Lantern" in texts()[0]  # consent explained first
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
    assert client.post(f"/api/listings/{v['id']}/contact").json()["whatsapp_url"].startswith("https://wa.me/")


def test_typed_malayalam_fallback(sharp_photo):
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
    assert msgs["vendor"]["state"] == "NEW" and "Welcome to Lantern" in msgs["messages"][0]["text"]


def test_metrics_logged_per_stage(sharp_photo, voice_note):
    submit(sharp_photo, voice_note)
    stages = {s["stage"] for s in TestClient(app).get("/api/metrics").json()["stages"]}
    assert {"asr", "to_english", "listing", "readback", "total"} <= stages
