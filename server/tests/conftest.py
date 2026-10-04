import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

# Settings are read at import time: point everything at a temp dir and run jobs inline.
_TMP = Path(tempfile.mkdtemp(prefix="lantern-test-"))
os.environ.update(
    MOCK_AI="true",
    SYNC_JOBS="true",
    DATABASE_URL=f"sqlite:///{_TMP / 'test.db'}",
    MEDIA_DIR=str(_TMP / "media"),
    # Never use the real credentials in server/.env (load_dotenv doesn't override these).
    TWILIO_ACCOUNT_SID="",
    TWILIO_AUTH_TOKEN="",
    TWILIO_API_KEY_SID="",
    TWILIO_API_KEY_SECRET="",
    TELEGRAM_BOT_TOKEN="",
    PROMPT_VOICE="ml",
    PUBLIC_BASE_URL="http://localhost:8000",
)

from app import db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    db.db.init()
    for table in ("vendors", "pipeline_metrics", "web_outbox"):
        db.db.query(f"DELETE FROM {table}")


def _img(name: str, arr: np.ndarray) -> str:
    path = _TMP / name
    Image.fromarray(arr).save(path, quality=95)
    return str(path)


@pytest.fixture
def sharp_photo() -> str:
    return _img("sharp.jpg", np.random.default_rng(0).integers(0, 255, (600, 800, 3), dtype=np.uint8))


@pytest.fixture
def blurry_photo() -> str:
    return _img("blurry.jpg", np.full((600, 800, 3), 128, dtype=np.uint8))


@pytest.fixture
def voice_note() -> str:
    """Any audio file: the mock pipeline uses its canned Malayalam transcript."""
    import soundfile as sf

    path = _TMP / "note.wav"
    sf.write(str(path), np.zeros(16000, dtype=np.float32), 16000)
    return str(path)
