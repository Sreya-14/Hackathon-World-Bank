"""Server settings from environment variables (and server/.env in development)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SERVER = Path(__file__).resolve().parent.parent
REPO = SERVER.parent
load_dotenv(SERVER / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # true = fake pipeline (no models needed; for UI work and tests). false = the real ML layer in ml/pipeline.
    mock_ai: bool = _bool("MOCK_AI", True)
    ml_dir: Path = Path(os.getenv("ML_DIR", str(REPO / "ml")))
    # Tests run pipeline jobs inline instead of on the background worker.
    sync_jobs: bool = _bool("SYNC_JOBS", False)

    # Public URL of this server; Twilio downloads read-back audio from here.
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,https://sreya-14.github.io").split(",") if o.strip()
    )

    # SQLite file by default; a postgres:// URL (e.g. Supabase) switches to Postgres.
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{SERVER / 'data' / 'lantern.db'}")
    media_dir: Path = Path(os.getenv("MEDIA_DIR", str(SERVER / "data" / "media")))

    # Twilio WhatsApp. Empty = WhatsApp off; vendors use the /host web page.
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    # Either the account's Auth Token, or an API key (SK…) + secret for sending and media.
    # Checking that webhooks really come from Twilio always needs the Auth Token.
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_api_key_sid: str = os.getenv("TWILIO_API_KEY_SID", "")
    twilio_api_key_secret: str = os.getenv("TWILIO_API_KEY_SECRET", "")
    twilio_whatsapp_from: str = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # sandbox number
    validate_twilio_signature: bool = _bool("VALIDATE_TWILIO_SIGNATURE", True)

    # Language for the bot's text and voice clips until a host picks one ("ml" or "en").
    # Each host chooses their own at the start; this is only the fallback.
    prompt_voice: str = os.getenv("PROMPT_VOICE", "ml")

    # Telegram bot for hosts (free; from @BotFather). Empty = off.
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Photo check (the ML pipeline handles voice; photos are checked here).
    blur_threshold: float = float(os.getenv("BLUR_THRESHOLD", "60"))  # Laplacian variance
    dark_threshold: float = float(os.getenv("DARK_THRESHOLD", "40"))  # mean brightness 0..255

    # Privacy: "area" listings are snapped to a grid of this size before storing.
    area_grid_m: float = float(os.getenv("AREA_GRID_M", "200"))
    # Trust: this many reports hide a listing.
    reports_to_hide: int = int(os.getenv("REPORTS_TO_HIDE", "3"))

    @property
    def twilio_enabled(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_credentials)

    @property
    def twilio_credentials(self) -> tuple[str, str] | None:
        """(username, password) for Twilio's REST API: the API key if set, else the account."""
        if self.twilio_api_key_sid and self.twilio_api_key_secret:
            return self.twilio_api_key_sid, self.twilio_api_key_secret
        if self.twilio_account_sid and self.twilio_auth_token:
            return self.twilio_account_sid, self.twilio_auth_token
        return None


settings = Settings()
for _sub in ("uploads", "photos", "prompts", "readback"):
    (settings.media_dir / _sub).mkdir(parents=True, exist_ok=True)
