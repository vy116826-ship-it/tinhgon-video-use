"""Transcription service — real API integrations for word-level transcription.

Supports:
  - ElevenLabs Scribe (high quality, needs API key)
  - Google Cloud Speech-to-Text (needs API key)
  - Whisper (local, requires `openai-whisper` installed)
  - Fallback: FFmpeg silencedetect (no API needed, coarse results)
"""
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

import requests

from app.core.config import (
    ELEVENLABS_API_KEY, GOOGLE_TTS_API_KEY,
    FFMPEG_PATH, FFPROBE_PATH,
)
from app.services.ffprobe import probe_video_sync


def transcribe(filepath: str, backend: str = "elevenlabs", work_dir: Optional[Path] = None) -> dict:
    """Transcribe a video/audio file and return word-level data.

    Returns: {"words": [{"text", "start", "end", "speaker"}], "duration": float}
    """
    if backend == "elevenlabs" and ELEVENLABS_API_KEY:
        return _transcribe_elevenlabs(filepath)
    elif backend == "google" and GOOGLE_TTS_API_KEY:
        return _transcribe_google(filepath, work_dir)
    elif backend == "whisper":
        return _transcribe_whisper(filepath, work_dir)
    else:
        # Auto-select best available
        if ELEVENLABS_API_KEY:
            return _transcribe_elevenlabs(filepath)
        if GOOGLE_TTS_API_KEY:
            return _transcribe_google(filepath, work_dir)
        # Final fallback
        return _transcribe_ffmpeg_fallback(filepath, work_dir)


def _extract_audio(filepath: str, work_dir: Optional[Path] = None) -> str:
    """Extract audio to WAV for API upload."""
    out_dir = work_dir or Path(filepath).parent
    audio_path = str(out_dir / "temp_audio.wav")
    subprocess.run([
        FFMPEG_PATH, "-y", "-i", filepath,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        audio_path,
    ], capture_output=True, timeout=120)
    return audio_path


# ── ElevenLabs Scribe ───────────────────────────────────────────────────

def _transcribe_elevenlabs(filepath: str) -> dict:
    """Use ElevenLabs Scribe API for word-level transcription."""
    url = "https://api.elevenlabs.io/v1/speech-to-text"

    # Determine file to send (video or extracted audio)
    ext = Path(filepath).suffix.lower()
    if ext in (".wav", ".mp3", ".m4a", ".flac", ".ogg"):
        audio_file = filepath
    else:
        audio_file = filepath  # ElevenLabs accepts video files too

    with open(audio_file, "rb") as f:
        response = requests.post(
            url,
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            files={"file": (Path(filepath).name, f)},
            data={
                "model_id": "scribe_v1",
                "timestamps_granularity": "word",
                "tag_audio_events": False,
                "diarize": True,
            },
            timeout=600,
        )

    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs API error {response.status_code}: {response.text}")

    data = response.json()

    # Parse ElevenLabs response into our format
    words = []
    for word_info in data.get("words", []):
        words.append({
            "text": word_info.get("text", "").strip(),
            "start": word_info.get("start", 0),
            "end": word_info.get("end", 0),
            "speaker": word_info.get("speaker_id", "S0"),
            "type": word_info.get("type", "word"),  # "word" or "spacing" or "punctuation"
        })

    # Filter to only actual words (not spacing/punctuation)
    words = [w for w in words if w.get("type", "word") == "word" and w["text"].strip()]

    # Get duration from probe
    probe = probe_video_sync(filepath)
    duration = probe.get("duration", 0)

    return {"words": words, "duration": duration, "backend": "elevenlabs"}


# ── Google Cloud Speech-to-Text ─────────────────────────────────────────

def _transcribe_google(filepath: str, work_dir: Optional[Path] = None) -> dict:
    """Use Google Cloud Speech-to-Text API."""
    import base64

    audio_path = _extract_audio(filepath, work_dir)

    with open(audio_path, "rb") as f:
        audio_content = base64.b64encode(f.read()).decode("utf-8")

    url = f"https://speech.googleapis.com/v1/speech:recognize?key={GOOGLE_TTS_API_KEY}"
    body = {
        "config": {
            "encoding": "LINEAR16",
            "sampleRateHertz": 16000,
            "languageCode": "en-US",
            "enableWordTimeOffsets": True,
            "enableAutomaticPunctuation": True,
            "model": "latest_long",
        },
        "audio": {"content": audio_content},
    }

    response = requests.post(url, json=body, timeout=600)
    if response.status_code != 200:
        raise RuntimeError(f"Google API error {response.status_code}: {response.text}")

    data = response.json()
    words = []

    for result in data.get("results", []):
        alt = result.get("alternatives", [{}])[0]
        for w in alt.get("words", []):
            start = float(w.get("startTime", "0s").rstrip("s"))
            end = float(w.get("endTime", "0s").rstrip("s"))
            words.append({
                "text": w.get("word", ""),
                "start": start,
                "end": end,
                "speaker": "S0",
            })

    # Cleanup
    if os.path.exists(audio_path):
        os.unlink(audio_path)

    probe = probe_video_sync(filepath)
    duration = probe.get("duration", 0)

    return {"words": words, "duration": duration, "backend": "google"}


# ── Whisper (local) ─────────────────────────────────────────────────────

def _transcribe_whisper(filepath: str, work_dir: Optional[Path] = None) -> dict:
    """Use OpenAI Whisper locally for transcription."""
    try:
        import whisper
    except ImportError:
        # Whisper not installed, try faster-whisper
        try:
            return _transcribe_faster_whisper(filepath)
        except ImportError:
            return _transcribe_ffmpeg_fallback(filepath, work_dir)

    model = whisper.load_model("base")
    result = model.transcribe(filepath, word_timestamps=True)

    words = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words.append({
                "text": w.get("word", "").strip(),
                "start": w.get("start", 0),
                "end": w.get("end", 0),
                "speaker": "S0",
            })

    probe = probe_video_sync(filepath)
    duration = probe.get("duration", 0)

    return {"words": words, "duration": duration, "backend": "whisper"}


def _transcribe_faster_whisper(filepath: str) -> dict:
    """Use faster-whisper for GPU-accelerated transcription."""
    from faster_whisper import WhisperModel

    model = WhisperModel("base", compute_type="int8")
    segments, info = model.transcribe(filepath, word_timestamps=True)

    words = []
    for segment in segments:
        for w in segment.words:
            words.append({
                "text": w.word.strip(),
                "start": w.start,
                "end": w.end,
                "speaker": "S0",
            })

    return {"words": words, "duration": info.duration, "backend": "faster-whisper"}


# ── FFmpeg fallback ─────────────────────────────────────────────────────

def _transcribe_ffmpeg_fallback(filepath: str, work_dir: Optional[Path] = None) -> dict:
    """Fallback: FFmpeg silence detection for coarse speech boundaries.

    This creates pseudo-word segments from audio analysis when no API is available.
    """
    out_dir = work_dir or Path(filepath).parent
    audio_out = str(out_dir / "temp_audio.wav")

    subprocess.run([
        FFMPEG_PATH, "-y", "-i", filepath,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        audio_out,
    ], capture_output=True, timeout=120)

    # Use FFmpeg's silencedetect filter
    result = subprocess.run([
        FFMPEG_PATH, "-i", audio_out,
        "-af", "silencedetect=noise=-30dB:d=0.3",
        "-f", "null", "-",
    ], capture_output=True, text=True, timeout=120)

    # Parse silence boundaries
    silence_starts = []
    silence_ends = []
    for line in result.stderr.split("\n"):
        if "silence_start:" in line:
            match = re.search(r"silence_start:\s*([\d.]+)", line)
            if match:
                silence_starts.append(float(match.group(1)))
        elif "silence_end:" in line:
            match = re.search(r"silence_end:\s*([\d.]+)", line)
            if match:
                silence_ends.append(float(match.group(1)))

    probe = probe_video_sync(filepath)
    duration = probe.get("duration", 0)

    # Create speech segments from inverse of silence
    words = []
    prev_end = 0.0
    for i in range(len(silence_starts)):
        if silence_starts[i] > prev_end + 0.1:
            words.append({
                "text": "[speech]",
                "start": prev_end,
                "end": silence_starts[i],
                "speaker": "S0",
            })
        if i < len(silence_ends):
            prev_end = silence_ends[i]
    if prev_end < duration - 0.1:
        words.append({"text": "[speech]", "start": prev_end, "end": duration, "speaker": "S0"})

    # Cleanup
    if os.path.exists(audio_out):
        os.unlink(audio_out)

    return {"words": words, "duration": duration, "backend": "ffmpeg-fallback"}
