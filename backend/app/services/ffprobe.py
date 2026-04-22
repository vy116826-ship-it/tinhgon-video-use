"""FFprobe service — extract video metadata."""
import asyncio
import json
import subprocess

from app.core.config import FFPROBE_PATH


async def probe_video(filepath: str) -> dict:
    """Run ffprobe on a video file and return metadata dict."""
    cmd = [
        FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filepath,
    ]
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: subprocess.run(
        cmd, capture_output=True, text=True, timeout=30
    ))

    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed: {result.stderr}")

    data = json.loads(result.stdout)

    # Extract video stream info
    video_stream = None
    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and not video_stream:
            video_stream = stream
        elif stream.get("codec_type") == "audio" and not audio_stream:
            audio_stream = stream

    metadata = {
        "duration": float(data.get("format", {}).get("duration", 0)),
        "file_size": int(data.get("format", {}).get("size", 0)),
    }

    if video_stream:
        metadata["width"] = int(video_stream.get("width", 0))
        metadata["height"] = int(video_stream.get("height", 0))
        metadata["codec"] = video_stream.get("codec_name", "unknown")

        # Parse FPS from r_frame_rate (e.g., "30000/1001")
        fps_str = video_stream.get("r_frame_rate", "0/1")
        try:
            num, den = fps_str.split("/")
            metadata["fps"] = round(int(num) / max(int(den), 1), 2)
        except (ValueError, ZeroDivisionError):
            metadata["fps"] = 0.0

    if audio_stream:
        metadata["audio_codec"] = audio_stream.get("codec_name", "unknown")

    return metadata


def probe_video_sync(filepath: str) -> dict:
    """Synchronous version for use in Celery workers."""
    cmd = [
        FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed: {result.stderr}")

    data = json.loads(result.stdout)

    video_stream = None
    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and not video_stream:
            video_stream = stream
        elif stream.get("codec_type") == "audio" and not audio_stream:
            audio_stream = stream

    metadata = {
        "duration": float(data.get("format", {}).get("duration", 0)),
        "file_size": int(data.get("format", {}).get("size", 0)),
    }

    if video_stream:
        metadata["width"] = int(video_stream.get("width", 0))
        metadata["height"] = int(video_stream.get("height", 0))
        metadata["codec"] = video_stream.get("codec_name", "unknown")
        fps_str = video_stream.get("r_frame_rate", "0/1")
        try:
            num, den = fps_str.split("/")
            metadata["fps"] = round(int(num) / max(int(den), 1), 2)
        except (ValueError, ZeroDivisionError):
            metadata["fps"] = 0.0

    if audio_stream:
        metadata["audio_codec"] = audio_stream.get("codec_name", "unknown")

    return metadata
