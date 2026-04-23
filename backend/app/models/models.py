"""Database models for Video-Use platform."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# ── Enums ───────────────────────────────────────────────────────────────

class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EditPreset(str, enum.Enum):
    QUICK_CLEAN = "quick_clean"          # Remove silences + fillers
    FULL_EDIT = "full_edit"              # Full pipeline
    SUBTITLES_ONLY = "subtitles_only"    # Transcribe + burn subtitles
    CUSTOM = "custom"                    # User-defined config


# ── Models ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(String(20), default=ProjectStatus.ACTIVE.value)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    user = relationship("User", back_populates="projects")
    uploads = relationship("Upload", back_populates="project", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=False)
    filepath = Column(Text, nullable=False)
    file_size = Column(Integer, default=0)  # bytes
    duration = Column(Float, nullable=True)  # seconds
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    codec = Column(String(50), nullable=True)
    thumbnail_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    project = relationship("Project", back_populates="uploads")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    celery_task_id = Column(String(255), nullable=True, index=True)
    preset = Column(String(50), default=EditPreset.QUICK_CLEAN.value)
    config = Column(JSON, default=dict)
    status = Column(String(20), default=JobStatus.PENDING.value, index=True)
    progress = Column(Float, default=0.0)  # 0-100
    current_step = Column(String(100), default="")
    output_path = Column(Text, nullable=True)
    output_size = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    project = relationship("Project", back_populates="jobs")
    steps = relationship("JobStep", back_populates="job", cascade="all, delete-orphan",
                         order_by="JobStep.order")

    # Upload IDs stored as JSON array in config["upload_ids"]


class JobStep(Base):
    __tablename__ = "job_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    order = Column(Integer, default=0)
    step_name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    status = Column(String(20), default=JobStepStatus.PENDING.value)
    progress = Column(Float, default=0.0)
    log_output = Column(Text, default="")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    job = relationship("Job", back_populates="steps")


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text, default="")

    __table_args__ = (
        # Composite unique on user_id + key
    )


class TemplateCategory(Base):
    __tablename__ = "template_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    icon = Column(String(10), default="🎬")
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    templates = relationship("Template", back_populates="category", cascade="all, delete-orphan")


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("template_categories.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    thumbnail_url = Column(Text, default="")
    preview_video_url = Column(Text, default="")
    tags = Column(JSON, default=list)                 # ["trending", "cinematic"]
    config = Column(JSON, default=dict)               # Edit config preset
    # Popularity
    use_count = Column(Integer, default=0)
    view_count = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    # Metadata
    duration_hint = Column(String(50), default="")    # "30s", "60s", "3min"
    aspect_ratio = Column(String(20), default="16:9") # "16:9", "9:16", "1:1"
    difficulty = Column(String(20), default="easy")   # "easy", "medium", "advanced"
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    category = relationship("TemplateCategory", back_populates="templates")

