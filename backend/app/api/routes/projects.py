"""Project management routes."""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.models.models import Project, ProjectStatus, Upload, Job, JobStatus

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ── Schemas ─────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    status: str
    upload_count: int = 0
    job_count: int = 0
    active_jobs: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Routes ──────────────────────────────────────────────────────────────

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    project = Project(user_id=user_id, name=req.name, description=req.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.updated_at.desc())
    )
    projects = result.scalars().all()

    responses = []
    for p in projects:
        # Count uploads
        ucount = await db.execute(
            select(func.count(Upload.id)).where(Upload.project_id == p.id)
        )
        # Count jobs
        jcount = await db.execute(
            select(func.count(Job.id)).where(Job.project_id == p.id)
        )
        # Active jobs
        acount = await db.execute(
            select(func.count(Job.id)).where(
                Job.project_id == p.id,
                Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value])
            )
        )
        responses.append(ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            status=p.status,
            upload_count=ucount.scalar() or 0,
            job_count=jcount.scalar() or 0,
            active_jobs=acount.scalar() or 0,
            created_at=p.created_at,
            updated_at=p.updated_at,
        ))

    return responses


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ucount = await db.execute(
        select(func.count(Upload.id)).where(Upload.project_id == project.id)
    )
    jcount = await db.execute(
        select(func.count(Job.id)).where(Job.project_id == project.id)
    )
    acount = await db.execute(
        select(func.count(Job.id)).where(
            Job.project_id == project.id,
            Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value])
        )
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        upload_count=ucount.scalar() or 0,
        job_count=jcount.scalar() or 0,
        active_jobs=acount.scalar() or 0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    req: ProjectUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if req.name is not None:
        project.name = req.name
    if req.description is not None:
        project.description = req.description
    project.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(project)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
    await db.commit()
