"""Template library routes — browse, search, use templates."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.models.models import Template, TemplateCategory

router = APIRouter(prefix="/api/templates", tags=["templates"])


# ── Schemas ─────────────────────────────────────────────────────────────
class CategoryResponse(BaseModel):
    id: int; name: str; slug: str; icon: str; order: int; template_count: int = 0
    class Config: from_attributes = True

class TemplateResponse(BaseModel):
    id: int; name: str; slug: str; description: str; thumbnail_url: str
    preview_video_url: str; tags: list; config: dict; use_count: int
    view_count: int; is_featured: bool; duration_hint: str
    aspect_ratio: str; difficulty: str; category_name: str; category_slug: str
    class Config: from_attributes = True

class TemplateCreate(BaseModel):
    category_id: int; name: str; slug: str; description: str = ""
    thumbnail_url: str = ""; preview_video_url: str = ""; tags: list = []
    config: dict = {}; duration_hint: str = ""; aspect_ratio: str = "16:9"
    difficulty: str = "easy"; is_featured: bool = False

class CategoryCreate(BaseModel):
    name: str; slug: str; icon: str = "🎬"; order: int = 0


# ── Routes ──────────────────────────────────────────────────────────────
@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TemplateCategory).order_by(TemplateCategory.order)
    )
    cats = result.scalars().all()
    out = []
    for c in cats:
        count_q = await db.execute(
            select(func.count(Template.id)).where(Template.category_id == c.id, Template.is_active == True)
        )
        out.append(CategoryResponse(
            id=c.id, name=c.name, slug=c.slug, icon=c.icon,
            order=c.order, template_count=count_q.scalar() or 0
        ))
    return out


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    category: Optional[str] = None,
    search: Optional[str] = None,
    tag: Optional[str] = None,
    aspect: Optional[str] = None,
    featured: Optional[bool] = None,
    sort: str = Query("popular", regex="^(popular|newest|name)$"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Template).where(Template.is_active == True)
    if category:
        query = query.join(TemplateCategory).where(TemplateCategory.slug == category)
    if search:
        query = query.where(or_(
            Template.name.ilike(f"%{search}%"),
            Template.description.ilike(f"%{search}%"),
        ))
    if featured is not None:
        query = query.where(Template.is_featured == featured)
    if aspect:
        query = query.where(Template.aspect_ratio == aspect)

    order_map = {
        "popular": Template.use_count.desc(),
        "newest": Template.created_at.desc(),
        "name": Template.name.asc(),
    }
    query = query.order_by(order_map.get(sort, Template.use_count.desc()))
    query = query.offset(offset).limit(limit)

    result = await db.execute(query.options(selectinload(Template.category)))
    templates = result.scalars().all()

    out = []
    for t in templates:
        resp = TemplateResponse(
            id=t.id, name=t.name, slug=t.slug, description=t.description,
            thumbnail_url=t.thumbnail_url, preview_video_url=t.preview_video_url,
            tags=t.tags or [], config=t.config or {}, use_count=t.use_count,
            view_count=t.view_count, is_featured=t.is_featured,
            duration_hint=t.duration_hint, aspect_ratio=t.aspect_ratio,
            difficulty=t.difficulty,
            category_name=t.category.name if t.category else "",
            category_slug=t.category.slug if t.category else "",
        )
        if tag and tag not in (t.tags or []):
            continue
        out.append(resp)
    return out


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Template).where(Template.id == template_id).options(selectinload(Template.category))
    )
    t = result.scalars().first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    t.view_count = (t.view_count or 0) + 1
    await db.commit()
    return TemplateResponse(
        id=t.id, name=t.name, slug=t.slug, description=t.description,
        thumbnail_url=t.thumbnail_url, preview_video_url=t.preview_video_url,
        tags=t.tags or [], config=t.config or {}, use_count=t.use_count,
        view_count=t.view_count, is_featured=t.is_featured,
        duration_hint=t.duration_hint, aspect_ratio=t.aspect_ratio,
        difficulty=t.difficulty,
        category_name=t.category.name if t.category else "",
        category_slug=t.category.slug if t.category else "",
    )


@router.post("/{template_id}/use")
async def use_template(
    template_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Template).where(Template.id == template_id))
    t = result.scalars().first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    t.use_count = (t.use_count or 0) + 1
    await db.commit()
    return {"config": t.config, "template_name": t.name}


@router.post("/seed")
async def seed_templates(db: AsyncSession = Depends(get_db)):
    """Seed default template library. Safe to call multiple times."""
    existing = await db.execute(select(func.count(TemplateCategory.id)))
    if existing.scalar() > 0:
        return {"message": "Already seeded"}

    categories_data = [
        ("trending", "🔥 Trending", "🔥", 0),
        ("cinematic", "🎬 Cinematic", "🎬", 1),
        ("vlog", "📹 Vlog", "📹", 2),
        ("shorts", "📱 Shorts / TikTok", "📱", 3),
        ("podcast", "🎙️ Podcast", "🎙️", 4),
        ("tutorial", "📚 Tutorial", "📚", 5),
        ("promo", "💼 Promo / Ads", "💼", 6),
        ("minimal", "✨ Minimal", "✨", 7),
    ]
    cat_map = {}
    for slug, name, icon, order in categories_data:
        cat = TemplateCategory(name=name, slug=slug, icon=icon, order=order)
        db.add(cat)
        await db.flush()
        cat_map[slug] = cat.id

    templates_data = [
        # Trending
        (cat_map["trending"], "Quick Clean Pro", "quick-clean-pro",
         "Remove silences & filler words instantly. Perfect for talking-head videos.",
         "https://images.unsplash.com/photo-1492691527719-9d1e07e534b4?w=400&h=300&fit=crop",
         "", ["trending", "quick", "clean"], {
             "preset": "quick_clean", "silence_threshold_ms": 400, "silence_remove": True,
             "filler_remove": True, "grade_preset": "none", "subtitles_enabled": False,
         }, True, "any", "16:9", "easy", 1520),
        (cat_map["trending"], "Viral Shorts Editor", "viral-shorts",
         "Auto-cut + bold subtitles for viral short-form content.",
         "https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=400&h=300&fit=crop",
         "", ["trending", "shorts", "subtitles"], {
             "preset": "full_edit", "silence_threshold_ms": 300, "silence_remove": True,
             "filler_remove": True, "grade_preset": "neutral_punch",
             "subtitles_enabled": True, "subtitle_style": "bold-overlay",
         }, True, "30s", "9:16", "easy", 3200),
        # Cinematic
        (cat_map["cinematic"], "Warm Cinematic", "warm-cinematic",
         "Warm color grading with cinematic feel. Great for travel and lifestyle.",
         "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=400&h=300&fit=crop",
         "", ["cinematic", "warm", "travel"], {
             "preset": "full_edit", "silence_threshold_ms": 500, "silence_remove": True,
             "filler_remove": False, "grade_preset": "warm_cinematic",
             "subtitles_enabled": True, "subtitle_style": "natural-sentence",
         }, True, "3min", "16:9", "medium", 980),
        (cat_map["cinematic"], "Film Noir", "film-noir",
         "Dark moody tones with dramatic contrast.",
         "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=400&h=300&fit=crop",
         "", ["cinematic", "dark", "moody"], {
             "preset": "full_edit", "grade_preset": "neutral_punch",
             "subtitles_enabled": False, "silence_remove": True,
         }, False, "2min", "16:9", "medium", 450),
        # Vlog
        (cat_map["vlog"], "Daily Vlog Auto-Edit", "daily-vlog",
         "Auto-remove dead air and silences. Keep the energy up!",
         "https://images.unsplash.com/photo-1527203561188-dae1bc1a60f1?w=400&h=300&fit=crop",
         "", ["vlog", "daily", "auto"], {
             "preset": "quick_clean", "silence_threshold_ms": 350, "filler_remove": True,
             "subtitles_enabled": True, "subtitle_style": "natural-sentence",
         }, False, "5min", "16:9", "easy", 2100),
        (cat_map["vlog"], "Travel Vlog Cinematic", "travel-vlog",
         "Warm grading + natural subtitles for travel content.",
         "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=400&h=300&fit=crop",
         "", ["vlog", "travel", "cinematic"], {
             "preset": "full_edit", "grade_preset": "warm_cinematic",
             "subtitles_enabled": True, "subtitle_style": "natural-sentence",
             "silence_threshold_ms": 600,
         }, True, "10min", "16:9", "medium", 1350),
        # Shorts
        (cat_map["shorts"], "TikTok Bold Text", "tiktok-bold",
         "Bold uppercase subtitles for maximum engagement on TikTok.",
         "https://images.unsplash.com/photo-1611162616305-c69b3fa7fbe0?w=400&h=300&fit=crop",
         "", ["shorts", "tiktok", "bold"], {
             "preset": "full_edit", "silence_threshold_ms": 250,
             "subtitles_enabled": True, "subtitle_style": "bold-overlay",
             "grade_preset": "neutral_punch",
         }, False, "30s", "9:16", "easy", 4500),
        (cat_map["shorts"], "YouTube Shorts Clean", "yt-shorts",
         "Clean edit with natural subtitles for YouTube Shorts.",
         "https://images.unsplash.com/photo-1611162618071-b39a2ec055fb?w=400&h=300&fit=crop",
         "", ["shorts", "youtube", "clean"], {
             "preset": "quick_clean", "subtitles_enabled": True,
             "subtitle_style": "natural-sentence",
         }, False, "60s", "9:16", "easy", 2800),
        # Podcast
        (cat_map["podcast"], "Podcast Clean Audio", "podcast-clean",
         "Remove ums, ahs, and long pauses. Perfect for podcast post-production.",
         "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=400&h=300&fit=crop",
         "", ["podcast", "audio", "clean"], {
             "preset": "quick_clean", "silence_threshold_ms": 800,
             "filler_remove": True, "subtitles_enabled": False,
         }, False, "30min", "16:9", "easy", 1800),
        (cat_map["podcast"], "Podcast with Captions", "podcast-captions",
         "Clean audio + burn readable subtitles for accessibility.",
         "https://images.unsplash.com/photo-1478737270239-2f02b77fc618?w=400&h=300&fit=crop",
         "", ["podcast", "captions", "accessibility"], {
             "preset": "full_edit", "silence_threshold_ms": 700,
             "filler_remove": True, "subtitles_enabled": True,
             "subtitle_style": "natural-sentence",
         }, True, "30min", "16:9", "medium", 1200),
        # Tutorial
        (cat_map["tutorial"], "Tutorial Clean Cut", "tutorial-clean",
         "Remove hesitations and keep the teaching clear.",
         "https://images.unsplash.com/photo-1501504905252-473c47e087f8?w=400&h=300&fit=crop",
         "", ["tutorial", "education", "clean"], {
             "preset": "quick_clean", "silence_threshold_ms": 500,
             "filler_remove": True, "subtitles_enabled": True,
             "subtitle_style": "natural-sentence",
         }, False, "10min", "16:9", "easy", 900),
        # Promo
        (cat_map["promo"], "Product Promo Punch", "product-promo",
         "Punchy grading + fast cuts for product showcases.",
         "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400&h=300&fit=crop",
         "", ["promo", "product", "business"], {
             "preset": "full_edit", "silence_threshold_ms": 200,
             "grade_preset": "neutral_punch", "subtitles_enabled": True,
             "subtitle_style": "bold-overlay",
         }, False, "30s", "16:9", "medium", 670),
        # Minimal
        (cat_map["minimal"], "Subtitles Only", "subtitles-only",
         "Just transcribe and burn subtitles. No cuts or grading.",
         "https://images.unsplash.com/photo-1516321497487-e288fb19713f?w=400&h=300&fit=crop",
         "", ["minimal", "subtitles"], {
             "preset": "subtitles_only", "subtitles_enabled": True,
             "subtitle_style": "natural-sentence", "silence_remove": False,
         }, False, "any", "16:9", "easy", 3100),
        (cat_map["minimal"], "No-Edit Transcribe", "no-edit-transcribe",
         "Just transcribe audio — no cutting, no grading, no subtitles burned.",
         "https://images.unsplash.com/photo-1504711434969-e33886168d6c?w=400&h=300&fit=crop",
         "", ["minimal", "transcribe"], {
             "preset": "custom", "silence_remove": False, "filler_remove": False,
             "subtitles_enabled": False, "grade_preset": "none",
         }, False, "any", "16:9", "easy", 750),
    ]

    for (cat_id, name, slug, desc, thumb, preview, tags, config,
         featured, dur, aspect, diff, uses) in templates_data:
        tpl = Template(
            category_id=cat_id, name=name, slug=slug, description=desc,
            thumbnail_url=thumb, preview_video_url=preview, tags=tags,
            config=config, is_featured=featured, duration_hint=dur,
            aspect_ratio=aspect, difficulty=diff, use_count=uses,
        )
        db.add(tpl)

    await db.commit()
    return {"message": "Seeded 14 templates in 8 categories"}


@router.post("/categories", response_model=CategoryResponse)
async def create_category(
    req: CategoryCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    cat = TemplateCategory(name=req.name, slug=req.slug, icon=req.icon, order=req.order)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return CategoryResponse(id=cat.id, name=cat.name, slug=cat.slug, icon=cat.icon, order=cat.order)


@router.post("", response_model=TemplateResponse)
async def create_template(
    req: TemplateCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    tpl = Template(**req.model_dump())
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    result = await db.execute(
        select(Template).where(Template.id == tpl.id).options(selectinload(Template.category))
    )
    tpl = result.scalars().first()
    return TemplateResponse(
        id=tpl.id, name=tpl.name, slug=tpl.slug, description=tpl.description,
        thumbnail_url=tpl.thumbnail_url, preview_video_url=tpl.preview_video_url,
        tags=tpl.tags or [], config=tpl.config or {}, use_count=tpl.use_count,
        view_count=tpl.view_count, is_featured=tpl.is_featured,
        duration_hint=tpl.duration_hint, aspect_ratio=tpl.aspect_ratio,
        difficulty=tpl.difficulty,
        category_name=tpl.category.name if tpl.category else "",
        category_slug=tpl.category.slug if tpl.category else "",
    )
