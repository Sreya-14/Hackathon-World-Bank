"""Lantern server: the vendor bot (WhatsApp + /host web page) around the ML layer, and the listings API."""
from __future__ import annotations

import logging
import re
import threading
import urllib.parse
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import bot, channels, db, engine, retention, telegram
from .config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("lantern")
logging.getLogger("twilio.http_client").setLevel(logging.WARNING)  # it logs every request and its headers
logging.getLogger("httpx").setLevel(logging.WARNING)  # its request lines include the Telegram bot token

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.db.init()
    retention.sweep()
    log.info("ML: %s | WhatsApp: %s | DB: %s", "MOCK" if settings.mock_ai else f"real ({settings.ml_dir})",
             "on" if settings.twilio_enabled else "off (vendors use /host)", "postgres" if db.db.is_pg else "sqlite")
    if not settings.mock_ai:
        # Import the model libraries here, once, before any thread: transformers loads lazily, and
        # two threads importing it at the same time can fail half-way ("cannot import name ...").
        import transformers  # noqa: F401
        from transformers import AutoTokenizer, VitsModel  # noqa: F401
    telegram.start()
    if not settings.mock_ai:
        # Load models in the background (~20 s) so the server answers right away.
        threading.Thread(target=engine.warm_up, name="warm-up", daemon=True).start()
    yield


app = FastAPI(title="Lantern", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"])
for _folder in channels.PUBLIC_MEDIA:  # not uploads/: originals are never served
    app.mount(f"/media/{_folder}", StaticFiles(directory=settings.media_dir / _folder), name=f"media-{_folder}")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "mock_ai": settings.mock_ai, "whatsapp": settings.twilio_enabled, "telegram": telegram.enabled(), "queue": engine.queue_length()}


# --- WhatsApp (Twilio) -----------------------------------------------------------------

@app.post("/twilio/whatsapp")
async def twilio_webhook(request: Request, background: BackgroundTasks) -> Response:
    form = dict(await request.form())
    if settings.twilio_enabled and settings.validate_twilio_signature:
        # Without this check anyone could post as any phone number. It needs the Auth Token
        # (an API key can't verify signatures); VALIDATE_TWILIO_SIGNATURE=false turns it off.
        if not settings.twilio_auth_token:
            log.error("TWILIO_AUTH_TOKEN is not set, so webhooks can't be verified; rejecting")
            raise HTTPException(503, "webhook verification not configured")
        from twilio.request_validator import RequestValidator

        url = f"{settings.public_base_url}{request.url.path}"
        if not RequestValidator(settings.twilio_auth_token).validate(url, form, request.headers.get("X-Twilio-Signature", "")):
            raise HTTPException(403, "bad Twilio signature")
    # Reply to Twilio at once (it times out after 15 s); the bot answers with its own messages.
    background.add_task(_handle_twilio, form)
    return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml")


def _handle_twilio(form: dict[str, str]) -> None:
    phone = form.get("From", "")
    media = []
    for i in range(int(form.get("NumMedia", "0") or 0)):
        ct = form.get(f"MediaContentType{i}", "")
        media.append((str(channels.download_twilio_media(form[f"MediaUrl{i}"], ct, phone)), ct))
    lat, lon = form.get("Latitude"), form.get("Longitude")
    bot.handle(bot.Inbound(phone=phone, text=form.get("Body", ""), media=media,
                           lat=float(lat) if lat else None, lon=float(lon) if lon else None))


# --- Web fallback for vendors (/host) ----------------------------------------------------

def _web_phone(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    if not 8 <= len(digits) <= 15:
        raise HTTPException(400, "enter your WhatsApp number with country code, e.g. +91 98765 43210")
    return f"web:+{digits}"


@app.get("/host")
def host_page() -> FileResponse:
    return FileResponse(STATIC / "host.html")


@app.post("/host/api/send")
async def host_send(
    background: BackgroundTasks,
    number: str = Form(...),
    text: str = Form(""),
    typed_text: str = Form(""),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    photo: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
) -> dict[str, Any]:
    phone = _web_phone(number)
    media: list[tuple[str, str]] = []
    for upload, default in ((photo, "image/jpeg"), (audio, "audio/webm")):
        if upload and upload.filename:
            ct = upload.content_type or default
            media.append((str(channels.save_upload(await upload.read(), ct, phone)), ct))
    background.add_task(bot.handle, bot.Inbound(phone=phone, text=text, typed_text=typed_text, media=media, lat=lat, lon=lon))
    return {"queued": True}


@app.get("/host/api/messages")
def host_messages(number: str, after: int = 0) -> dict[str, Any]:
    phone = _web_phone(number)
    v = db.db.one("SELECT state, live, hidden, privacy, voice_lang FROM vendors WHERE phone = ?", (phone,))
    return {"messages": db.web_messages(phone, after), "vendor": v, "queue": engine.queue_length()}


# --- Public API for the tourist app (docs/LISTINGS_API.md) --------------------------------

def _days_since(ts: str | None) -> float | None:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds() / 86400 if ts else None


def _contact_links(v: dict[str, Any], title_en: str) -> dict[str, str]:
    """WhatsApp and SMS links to the host, both opening with a greeting in Malayalam (plus English).
    SMS needs only mobile signal, no data, so it also works where WhatsApp doesn't."""
    number = re.sub(r"\D", "", v.get("contact_phone") or v["phone"].split(":")[-1])
    greeting = urllib.parse.quote(
        "നമസ്കാരം! ലാന്റേണിൽ നിങ്ങളുടെ ലിസ്റ്റിംഗ് കണ്ടു. എനിക്ക് താല്പര്യമുണ്ട്.\n"
        f'(Hello! I saw your listing "{title_en}" on Lantern and I\'m interested.)'
    )
    return {
        "whatsapp_url": f"https://wa.me/{number}?text={greeting}",
        # "?&body=" works on both Android and iOS.
        "sms_url": f"sms:+{number}?&body={greeting}",
    }


def _feature(v: dict[str, Any], with_contact: bool = False) -> dict[str, Any] | None:
    listing = db.listing_of(v)
    if not listing:
        return None
    text = listing["text"]
    en, de = text["en"], text.get("de") or text["en"]
    props = {
        "id": v["id"],
        "category": listing["category"],
        "title": {"en": en["title"], "de": de["title"]},
        "description": {"en": en["description"], "de": de["description"]},
        # Facts as the vendor said them (English); null when she didn't say them.
        "price": en.get("price"),
        "hours": en.get("hours"),
        "duration": en.get("duration"),
        "includes": {"en": en.get("includes") or [], "de": de.get("includes") or []},
        "meeting_point": {"en": en.get("meeting_point"), "de": de.get("meeting_point")},
        # The places the host named ("Meppadi"); the map pin's precision is in "privacy".
        "place": en.get("location"),
        "machine_translated": listing.get("machine_translated", []),
        "photo_url": channels.media_url(v.get("photo_path")),
        "privacy": v["privacy"],
        "radius_m": settings.area_grid_m if v["privacy"] == "area" else None,
        "verified": bool(v["verified"]),
        "met_count": v["met_count"],
        "days_since_checkin": _days_since(v["last_checkin"]),
        "seed": bool(v["seed"]),
        "updated_at": v["updated_at"],
    }
    if with_contact:
        props.update(_contact_links(v, en["title"]))
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [v["lon"], v["lat"]]}, "properties": props}


@app.get("/api/listings")
def listings() -> dict[str, Any]:
    """Live listings as GeoJSON. No phone numbers here; see /contact and /bundle."""
    return {"type": "FeatureCollection", "features": [f for v in db.live_listings() if (f := _feature(v))]}


@app.get("/api/bundle")
def bundle() -> dict[str, Any]:
    """The offline download: listings with contact links, so a tourist in airplane mode can still open WhatsApp."""
    feats = [f for v in db.live_listings() if (f := _feature(v, with_contact=True))]
    return {"type": "FeatureCollection", "features": feats, "generated_at": db.now()}


def _live_vendor(vendor_id: int) -> dict[str, Any]:
    v = db.get_vendor(vendor_id)
    if not v or not v["live"] or v["hidden"]:
        raise HTTPException(404)
    return v


@app.post("/api/listings/{vendor_id}/contact")
def contact(vendor_id: int) -> dict[str, str]:
    v = _live_vendor(vendor_id)
    db.increment(vendor_id, "interest_count")
    return _contact_links(v, db.listing_of(v)["text"]["en"]["title"])


@app.post("/api/listings/{vendor_id}/met")
def met(vendor_id: int) -> dict[str, int]:
    _live_vendor(vendor_id)
    return {"met_count": db.increment(vendor_id, "met_count")["met_count"]}


@app.post("/api/listings/{vendor_id}/report")
def report(vendor_id: int) -> dict[str, bool]:
    _live_vendor(vendor_id)
    if db.increment(vendor_id, "report_count")["report_count"] >= settings.reports_to_hide:
        db.update_vendor(vendor_id, hidden=1)
    return {"reported": True}


@app.get("/api/metrics")
def metrics() -> dict[str, Any]:
    """Seconds per pipeline stage, for the metrics slide."""
    return {"mode": "mock" if settings.mock_ai else "real", "stages": db.metric_summary()}
