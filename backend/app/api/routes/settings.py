"""Settings routes — manage server API keys and configuration."""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.config import ELEVENLABS_API_KEY, GOOGLE_TTS_API_KEY

router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_FILE = Path("/app/.env")
if not ENV_FILE.exists():
    # Try local dev path
    ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class APIKeysUpdate(BaseModel):
    elevenlabs_api_key: str = ""
    google_tts_api_key: str = ""


class APIKeysResponse(BaseModel):
    elevenlabs_configured: bool
    google_configured: bool
    elevenlabs_key_masked: str
    google_key_masked: str


def _mask_key(key: str) -> str:
    """Mask API key for display: show first 4 and last 4 chars."""
    if not key or len(key) < 8:
        return "••••" if key else ""
    return key[:4] + "•" * (len(key) - 8) + key[-4:]


@router.get("/api-keys", response_model=APIKeysResponse)
async def get_api_keys(user_id: int = Depends(get_current_user_id)):
    """Get current API key status (masked)."""
    el_key = os.environ.get("ELEVENLABS_API_KEY", "") or ELEVENLABS_API_KEY
    g_key = os.environ.get("GOOGLE_TTS_API_KEY", "") or GOOGLE_TTS_API_KEY

    return APIKeysResponse(
        elevenlabs_configured=bool(el_key),
        google_configured=bool(g_key),
        elevenlabs_key_masked=_mask_key(el_key),
        google_key_masked=_mask_key(g_key),
    )


@router.put("/api-keys")
async def update_api_keys(
    keys: APIKeysUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Update API keys — saves to environment and .env file."""
    updated = {}

    if keys.elevenlabs_api_key:
        os.environ["ELEVENLABS_API_KEY"] = keys.elevenlabs_api_key
        updated["elevenlabs"] = True

    if keys.google_tts_api_key:
        os.environ["GOOGLE_TTS_API_KEY"] = keys.google_tts_api_key
        updated["google"] = True

    # Persist to .env file
    _update_env_file(keys)

    return {
        "message": "API keys updated",
        "updated": updated,
        "elevenlabs_configured": bool(os.environ.get("ELEVENLABS_API_KEY")),
        "google_configured": bool(os.environ.get("GOOGLE_TTS_API_KEY")),
    }


def _update_env_file(keys: APIKeysUpdate):
    """Update .env file with new API keys."""
    if not ENV_FILE.exists():
        return

    lines = ENV_FILE.read_text().splitlines()
    new_lines = []
    found_el = False
    found_g = False

    for line in lines:
        if line.startswith("ELEVENLABS_API_KEY=") and keys.elevenlabs_api_key:
            new_lines.append(f"ELEVENLABS_API_KEY={keys.elevenlabs_api_key}")
            found_el = True
        elif line.startswith("GOOGLE_TTS_API_KEY=") and keys.google_tts_api_key:
            new_lines.append(f"GOOGLE_TTS_API_KEY={keys.google_tts_api_key}")
            found_g = True
        else:
            new_lines.append(line)

    if keys.elevenlabs_api_key and not found_el:
        new_lines.append(f"ELEVENLABS_API_KEY={keys.elevenlabs_api_key}")
    if keys.google_tts_api_key and not found_g:
        new_lines.append(f"GOOGLE_TTS_API_KEY={keys.google_tts_api_key}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n")
