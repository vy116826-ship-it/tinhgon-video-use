"""Celery task: Video processing pipeline with real-time progress."""
import json
import traceback
from datetime import datetime, timezone

from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.celery_app import celery_app
from app.core.config import DATABASE_URL, UPLOAD_DIR
from app.models.models import Job, JobStep, JobStatus, JobStepStatus, Upload
from app.services.pipeline import VideoPipeline

# Synchronous database engine for Celery workers
sync_db_url = DATABASE_URL.replace("+aiosqlite", "").replace("sqlite:///", "sqlite:///")
sync_engine = create_engine(sync_db_url, echo=False)
SyncSession = sessionmaker(sync_engine, class_=Session)


def _update_step(session: Session, job_id: int, step_name: str, **kwargs):
    """Update a job step's status and progress."""
    result = session.execute(
        select(JobStep).where(JobStep.job_id == job_id, JobStep.step_name == step_name)
    )
    step = result.scalars().first()
    if step:
        for key, val in kwargs.items():
            setattr(step, key, val)
        session.commit()


def _update_job(session: Session, job_id: int, **kwargs):
    """Update job status."""
    result = session.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()
    if job:
        for key, val in kwargs.items():
            setattr(job, key, val)
        session.commit()


class VideoTask(Task):
    """Base task class that auto-publishes progress to Redis for WebSocket relay."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        job_id = args[0] if args else None
        if job_id:
            with SyncSession() as session:
                _update_job(session, job_id,
                            status=JobStatus.FAILED.value,
                            error_message=str(exc),
                            completed_at=datetime.now(timezone.utc))


@celery_app.task(bind=True, base=VideoTask, name="app.tasks.process_video.process_video_pipeline")
def process_video_pipeline(self, job_id: int):
    """Main pipeline task — processes a video editing job."""

    with SyncSession() as session:
        # Load job
        result = session.execute(select(Job).where(Job.id == job_id))
        job = result.scalars().first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        config = job.config or {}
        upload_ids = config.get("upload_ids", [])

        # Load uploads
        uploads = []
        for uid in upload_ids:
            result = session.execute(select(Upload).where(Upload.id == uid))
            upload = result.scalars().first()
            if upload:
                uploads.append({
                    "id": upload.id,
                    "filepath": upload.filepath,
                    "original_filename": upload.original_filename,
                })

        if not uploads:
            _update_job(session, job_id,
                        status=JobStatus.FAILED.value,
                        error_message="No valid upload files found")
            return

        # Mark job as running
        _update_job(session, job_id,
                    status=JobStatus.RUNNING.value,
                    started_at=datetime.now(timezone.utc))

    # Progress callback
    current_step_name = [None]

    def on_progress(step_name: str, pct: float, log_line: str):
        with SyncSession() as sess:
            # Update step
            if step_name != current_step_name[0]:
                # Mark previous step as completed
                if current_step_name[0]:
                    _update_step(sess, job_id, current_step_name[0],
                                 status=JobStepStatus.COMPLETED.value,
                                 progress=100.0,
                                 completed_at=datetime.now(timezone.utc))
                # Mark new step as running
                _update_step(sess, job_id, step_name,
                             status=JobStepStatus.RUNNING.value,
                             started_at=datetime.now(timezone.utc))
                current_step_name[0] = step_name

            _update_step(sess, job_id, step_name,
                         progress=pct,
                         log_output=log_line)

            # Calculate overall progress from steps
            result = sess.execute(
                select(JobStep).where(JobStep.job_id == job_id)
            )
            steps = result.scalars().all()
            if steps:
                total_steps = len(steps)
                completed = sum(1 for s in steps if s.status == JobStepStatus.COMPLETED.value)
                current_pct = pct / 100.0 if pct > 0 else 0
                overall = ((completed + current_pct) / total_steps) * 100
            else:
                overall = 0

            _update_job(sess, job_id,
                        progress=round(overall, 1),
                        current_step=step_name)

        # Update Celery state for polling
        self.update_state(
            state="PROGRESS",
            meta={
                "step": step_name,
                "step_progress": pct,
                "overall_progress": overall if 'overall' in dir() else 0,
                "log": log_line,
            }
        )

    # Run pipeline
    try:
        pipeline = VideoPipeline(
            job_id=job_id,
            upload_files=uploads,
            config=config,
            on_progress=on_progress,
        )
        output_path = pipeline.run()

        # Mark complete
        with SyncSession() as session:
            import os
            output_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

            # Mark last step complete
            if current_step_name[0]:
                _update_step(session, job_id, current_step_name[0],
                             status=JobStepStatus.COMPLETED.value,
                             progress=100.0,
                             completed_at=datetime.now(timezone.utc))

            _update_job(session, job_id,
                        status=JobStatus.COMPLETED.value,
                        progress=100.0,
                        output_path=output_path,
                        output_size=output_size,
                        completed_at=datetime.now(timezone.utc))

        return {"status": "completed", "output_path": output_path}

    except Exception as e:
        with SyncSession() as session:
            _update_job(session, job_id,
                        status=JobStatus.FAILED.value,
                        error_message=f"{str(e)}\n{traceback.format_exc()}",
                        completed_at=datetime.now(timezone.utc))
        raise
