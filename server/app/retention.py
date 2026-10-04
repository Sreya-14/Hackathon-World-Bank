"""What the server keeps of what a host sends, and for how long.

- Voice notes: deleted as soon as the pipeline has transcribed them. Only the text is kept.
- Photos: the original is deleted on arrival. What's kept is a re-encoded copy with no
  metadata (no GPS position, camera or time) and at most 1600 px; that copy is the listing photo, and
  it's deleted when the host replaces it or restarts.
- Read-back audio (the listing read aloud, synthetic voice): deleted once the host approves,
  asks to redo, or restarts.
- Anything the bot received but didn't keep (a blurry photo, a voice note sent while busy) is
  deleted when the message has been handled.

Only files under uploads/, photos/ and readback/ are ever deleted; prompt clips are a shared cache.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from . import db
from .config import settings

log = logging.getLogger("lantern.retention")

UPLOADS = settings.media_dir / "uploads"
PHOTOS = settings.media_dir / "photos"
READBACK = settings.media_dir / "readback"
MAX_PHOTO_PX = 1600


def _deletable(path: Path) -> bool:
    p = path.resolve()
    return any(p.is_relative_to(d.resolve()) for d in (UPLOADS, PHOTOS, READBACK))


def discard(path: str | Path | None) -> None:
    """Delete a host's file. Paths outside the host-data folders are left alone."""
    if not path or not _deletable(Path(path)):
        return
    Path(path).unlink(missing_ok=True)


def discard_readback(path: str | Path | None) -> None:
    """The read-back clip and the WAV the pipeline wrote next to it."""
    if path:
        for suffix in (".ogg", ".wav"):
            discard(Path(path).with_suffix(suffix))


def clean_photo(path: str | Path) -> Path:
    """A metadata-free copy for the listing; the original upload is deleted."""
    PHOTOS.mkdir(parents=True, exist_ok=True)
    out = PHOTOS / f"{uuid.uuid4().hex}.jpg"
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")  # keep the orientation, drop the EXIF
        img.thumbnail((MAX_PHOTO_PX, MAX_PHOTO_PX))
        img.save(out, "JPEG", quality=85)  # no exif= argument, so nothing is carried over
    discard(path)
    return out


def sweep() -> None:
    """At startup: apply the rules to files left from before they existed (or from a crash)."""
    keep: set[Path] = set()
    for v in db.db.query("SELECT * FROM vendors"):
        updates = {}
        photo = v["photo_path"]
        if photo and Path(photo).exists() and Path(photo).resolve().is_relative_to(UPLOADS.resolve()):
            photo = str(clean_photo(photo))
            updates["photo_path"] = photo
        # A voice note is only needed while it waits for its photo (NEW). Jobs don't survive a restart.
        if v["audio_path"] and v["state"] != "NEW":
            updates["audio_path"] = None
        elif v["audio_path"]:
            keep.add(Path(v["audio_path"]).resolve())
        if v["readback_audio"] and v["state"] != "AWAITING_APPROVAL":
            updates["readback_audio"] = None
        elif v["readback_audio"]:
            keep.update(Path(v["readback_audio"]).with_suffix(s).resolve() for s in (".ogg", ".wav"))
        if photo:
            keep.add(Path(photo).resolve())
        if updates:
            db.update_vendor(v["id"], **updates)
    removed = 0
    for folder in (UPLOADS, PHOTOS, READBACK):
        for f in folder.rglob("*") if folder.exists() else []:
            if f.is_file() and f.resolve() not in keep:
                f.unlink()
                removed += 1
    if removed:
        log.info("retention: deleted %d host files no longer needed", removed)
