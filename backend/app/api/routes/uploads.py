"""Video file upload routes with chunked upload and FFprobe metadata."""
import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.core.config import UPLOAD_DIR, ALLOWED_VIDEO_EXTENSIONS
from app.models.models import Upload, Project
from app.services.ffprobe import probe_video

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


# ── Schemas ─────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    id: int
    project_id: int
    original_filename: str
    file_size: int
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    codec: Optional[str] = None
    thumbnail_path: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class ProbeResponse(BaseModel):
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    audio_codec: Optional[str] = None
    file_size: int


# ── Routes ──────────────────────────────────────────────────────────────

@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}"
        )

    # Create upload directory for project
    project_upload_dir = UPLOAD_DIR / str(project_id)
    project_upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    filepath = project_upload_dir / stored_filename

    # Save file
    file_size = 0
    with open(filepath, "wb") as buffer:
        while chunk := await file.read(8192 * 1024):  # 8MB chunks
            buffer.write(chunk)
            file_size += len(chunk)

    # Probe video metadata
    metadata = {}
    try:
        metadata = await probe_video(str(filepath))
    except Exception as e:
        print(f"FFprobe failed for {filepath}: {e}")

    # Create DB record
    upload = Upload(
        project_id=project_id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        filepath=str(filepath),
        file_size=file_size,
        duration=metadata.get("duration"),
        width=metadata.get("width"),
        height=metadata.get("height"),
        fps=metadata.get("fps"),
        codec=metadata.get("codec"),
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)

    return UploadResponse(
        id=upload.id,
        project_id=upload.project_id,
        original_filename=upload.original_filename,
        file_size=upload.file_size,
        duration=upload.duration,
        width=upload.width,
        height=upload.height,
        fps=upload.fps,
        codec=upload.codec,
        thumbnail_path=upload.thumbnail_path,
        created_at=str(upload.created_at),
    )


@router.get("", response_model=List[UploadResponse])
async def list_uploads(
    project_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Upload).where(Upload.project_id == project_id).order_by(Upload.created_at.desc())
    )
    uploads = result.scalars().all()

    return [
        UploadResponse(
            id=u.id,
            project_id=u.project_id,
            original_filename=u.original_filename,
            file_size=u.file_size,
            duration=u.duration,
            width=u.width,
            height=u.height,
            fps=u.fps,
            codec=u.codec,
            thumbnail_path=u.thumbnail_path,
            created_at=str(u.created_at),
        )
        for u in uploads
    ]


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(
    upload_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Upload)
        .join(Project, Upload.project_id == Project.id)
        .where(Upload.id == upload_id, Project.user_id == user_id)
    )
    upload = result.scalars().first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Remove file from disk
    try:
        if os.path.exists(upload.filepath):
            os.remove(upload.filepath)
    except OSError:
        pass

    await db.delete(upload)
    await db.commit()
