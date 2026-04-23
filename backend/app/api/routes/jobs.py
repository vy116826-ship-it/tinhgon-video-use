"""Job management routes — create, list, cancel, download."""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.models.models import Project, Job, JobStep, JobStatus, EditPreset
from app.celery_app import celery_app

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ── Schemas ─────────────────────────────────────────────────────────────

class JobConfig(BaseModel):
    upload_ids: List[int]
    preset: str = "quick_clean"
    # Silence detection
    silence_threshold_ms: int = 400
    silence_remove: bool = True
    # Filler words
    filler_remove: bool = True
    filler_words: List[str] = ["umm", "uh", "um", "ah", "like", "you know", "so"]
    # Color grade
    grade_preset: str = "none"      # none | warm_cinematic | neutral_punch | custom
    grade_custom_filter: str = ""
    # Subtitles
    subtitles_enabled: bool = True
    subtitle_style: str = "bold-overlay"  # bold-overlay | natural-sentence | custom
    # Output
    output_resolution: str = "1080p"  # 720p | 1080p | 4k
    output_format: str = "mp4"
    # Transcription
    transcription_backend: str = "elevenlabs"  # elevenlabs | google


class JobCreate(BaseModel):
    project_id: int
    config: JobConfig


class JobStepResponse(BaseModel):
    id: int
    order: int
    step_name: str
    display_name: str
    status: str
    progress: float
    log_output: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    id: int
    project_id: int
    celery_task_id: Optional[str] = None
    preset: str
    config: dict
    status: str
    progress: float
    current_step: str
    output_path: Optional[str] = None
    output_size: Optional[int] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    steps: List[JobStepResponse] = []

    class Config:
        from_attributes = True


# ── Pipeline Steps Definition ───────────────────────────────────────────

PIPELINE_STEPS = [
    ("transcribe", "🎙️ Transcribing Audio"),
    ("pack", "📦 Packing Transcripts"),
    ("analyze", "🔍 Analyzing Content"),
    ("cut", "✂️ Auto-Cutting"),
    ("render", "🎬 Rendering Video"),
    ("grade", "🎨 Color Grading"),
    ("subtitles", "📝 Burning Subtitles"),
    ("finalize", "✅ Finalizing Output"),
]


# ── Routes ──────────────────────────────────────────────────────────────

@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    req: JobCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == req.project_id, Project.user_id == user_id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Create job
    job = Job(
        project_id=req.project_id,
        preset=req.config.preset,
        config=req.config.model_dump(),
        status=JobStatus.PENDING.value,
    )
    db.add(job)
    await db.flush()

    # Create pipeline steps
    steps_to_create = PIPELINE_STEPS.copy()
    if not req.config.subtitles_enabled:
        steps_to_create = [s for s in steps_to_create if s[0] != "subtitles"]
    if req.config.grade_preset == "none":
        steps_to_create = [s for s in steps_to_create if s[0] != "grade"]

    for i, (name, display) in enumerate(steps_to_create):
        step = JobStep(
            job_id=job.id,
            order=i,
            step_name=name,
            display_name=display,
        )
        db.add(step)

    await db.commit()
    await db.refresh(job)

    # Dispatch Celery task
    task = celery_app.send_task(
        "app.tasks.process_video.process_video_pipeline",
        args=[job.id],
    )

    # Save celery task ID
    job.celery_task_id = task.id
    await db.commit()

    # Reload with steps
    result = await db.execute(
        select(Job).where(Job.id == job.id).options(selectinload(Job.steps))
    )
    job = result.scalars().first()

    return _job_to_response(job)


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    project_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Job)
        .join(Project, Job.project_id == Project.id)
        .where(Project.user_id == user_id)
        .options(selectinload(Job.steps))
        .order_by(Job.created_at.desc())
    )
    if project_id:
        query = query.where(Job.project_id == project_id)
    if status_filter:
        query = query.where(Job.status == status_filter)

    result = await db.execute(query)
    jobs = result.scalars().all()
    return [_job_to_response(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job)
        .join(Project, Job.project_id == Project.id)
        .where(Job.id == job_id, Project.user_id == user_id)
        .options(selectinload(Job.steps))
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.post("/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_job(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job)
        .join(Project, Job.project_id == Project.id)
        .where(Job.id == job_id, Project.user_id == user_id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in (JobStatus.PENDING.value, JobStatus.RUNNING.value):
        raise HTTPException(status_code=400, detail="Job is not running")

    # Revoke celery task
    if job.celery_task_id:
        celery_app.control.revoke(job.celery_task_id, terminate=True)

    job.status = JobStatus.CANCELLED.value
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Job cancelled"}


@router.get("/{job_id}/download")
async def download_output(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job)
        .join(Project, Job.project_id == Project.id)
        .where(Job.id == job_id, Project.user_id == user_id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED.value or not job.output_path:
        raise HTTPException(status_code=400, detail="Output not ready")

    import os
    if not os.path.exists(job.output_path):
        raise HTTPException(status_code=404, detail="Output file not found on disk")

    return FileResponse(
        path=job.output_path,
        filename=f"video_use_output_{job_id}.mp4",
        media_type="video/mp4",
    )


# ── Helpers ─────────────────────────────────────────────────────────────

def _job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        project_id=job.project_id,
        celery_task_id=job.celery_task_id,
        preset=job.preset,
        config=job.config or {},
        status=job.status,
        progress=job.progress,
        current_step=job.current_step or "",
        output_path=job.output_path,
        output_size=job.output_size,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        steps=[
            JobStepResponse(
                id=s.id,
                order=s.order,
                step_name=s.step_name,
                display_name=s.display_name,
                status=s.status,
                progress=s.progress,
                log_output=s.log_output or "",
                started_at=s.started_at,
                completed_at=s.completed_at,
            )
            for s in sorted(job.steps, key=lambda x: x.order)
        ],
    )
