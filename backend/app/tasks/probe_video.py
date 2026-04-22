"""Celery task: FFprobe video metadata extraction."""
from app.celery_app import celery_app
from app.services.ffprobe import probe_video_sync


@celery_app.task(name="app.tasks.probe_video.probe_video_task")
def probe_video_task(filepath: str) -> dict:
    """Probe a video file for metadata. Returns dict with duration, resolution, etc."""
    return probe_video_sync(filepath)
