from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.db import get_db
from app.normalizer import make_slug, normalize_sample_values, normalize_text
from app.services import add_alias, create_canonical_attribute, get_canonical, safe_reindex_canonical_attribute

router = APIRouter(prefix="/canonical", tags=["canonical attributes"])


def _slug_exists_for_other(db: Session, slug: str, canonical_id: int) -> bool:
    return (
        db.query(models.CanonicalAttribute)
        .filter(models.CanonicalAttribute.slug == slug, models.CanonicalAttribute.id != canonical_id)
        .first()
        is not None
    )


def _unique_slug_for_update(requested: str, canonical_id: int, db: Session) -> str:
    base = make_slug(requested)
    slug = base
    counter = 2
    while _slug_exists_for_other(db, slug, canonical_id):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def _filtered_canonical_query(
    db: Session,
    q: str | None,
    active: bool | None,
    include_inactive: bool,
    load_aliases: bool = True,
):
    query = db.query(models.CanonicalAttribute)
    if load_aliases:
        query = query.options(selectinload(models.CanonicalAttribute.aliases))

    if not include_inactive and active is not None:
        query = query.filter(models.CanonicalAttribute.active.is_(active))

    if q:
        raw_q = q.strip()
        norm_q = normalize_text(raw_q)
        raw_like = f"%{raw_q}%"
        norm_like = f"%{norm_q}%" if norm_q else raw_like
        query = (
            query.outerjoin(models.AttributeAlias)
            .filter(
                or_(
                    models.CanonicalAttribute.name.ilike(raw_like),
                    models.CanonicalAttribute.slug.ilike(raw_like),
                    models.CanonicalAttribute.category_hint.ilike(raw_like),
                    models.AttributeAlias.alias_raw.ilike(raw_like),
                    models.AttributeAlias.alias_norm.ilike(norm_like),
                )
            )
            .distinct()
        )

    return query


@router.post("", response_model=schemas.CanonicalOut)
def create_canonical(payload: schemas.CanonicalCreate, db: Session = Depends(get_db)):
    try:
        # Create the attribute first. Then try embedding generation separately.
        # This prevents local AI/model/cache problems from breaking normal data entry.
        attr = create_canonical_attribute(
            db=db,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            category_hint=payload.category_hint,
            sample_values=payload.sample_values,
            aliases=payload.aliases,
            reindex=False,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database constraint error. The attribute name, slug, or alias probably already exists.",
        ) from exc

    if payload.reindex:
        # Reindex is secondary. Keep normal CRUD usable even if the model is not ready.
        safe_reindex_canonical_attribute(db, attr.id)

    result = get_canonical(db, attr.id)
    if not result:
        raise HTTPException(status_code=500, detail="Canonical attribute was created but could not be loaded.")
    return result


@router.get("", response_model=list[schemas.CanonicalOut])
def list_canonical(
    q: str | None = Query(default=None),
    active: bool | None = Query(default=True),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = _filtered_canonical_query(db, q=q, active=active, include_inactive=include_inactive)
    return query.order_by(models.CanonicalAttribute.id.desc()).offset(offset).limit(limit).all()


@router.get("/page")
def page_canonical(
    q: str | None = Query(default=None),
    active: bool | None = Query(default=True),
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = _filtered_canonical_query(db, q=q, active=active, include_inactive=include_inactive)
    total = query.order_by(None).count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(page, 1), total_pages)
    offset = (page - 1) * page_size
    items = query.order_by(models.CanonicalAttribute.id.desc()).offset(offset).limit(page_size).all()
    return {
        "items": [schemas.CanonicalOut.model_validate(item).model_dump(mode="json") for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/count")
def count_canonical(
    q: str | None = Query(default=None),
    active: bool | None = Query(default=True),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    query = _filtered_canonical_query(
        db, q=q, active=active, include_inactive=include_inactive, load_aliases=False
    )
    return {"total": query.order_by(None).count()}


@router.get("/{canonical_id}", response_model=schemas.CanonicalOut)
def get_one(canonical_id: int, db: Session = Depends(get_db)):
    attr = get_canonical(db, canonical_id)
    if not attr:
        raise HTTPException(status_code=404, detail="Canonical attribute not found.")
    return attr


@router.patch("/{canonical_id}", response_model=schemas.CanonicalOut)
def update_canonical(canonical_id: int, payload: schemas.CanonicalUpdate, db: Session = Depends(get_db)):
    attr = get_canonical(db, canonical_id)
    if not attr:
        raise HTTPException(status_code=404, detail="Canonical attribute not found.")

    try:
        if payload.name is not None:
            cleaned_name = payload.name.strip()
            if not cleaned_name:
                raise HTTPException(status_code=400, detail="Canonical attribute name is required.")
            if cleaned_name != attr.name:
                existing = (
                    db.query(models.CanonicalAttribute)
                    .filter(models.CanonicalAttribute.name == cleaned_name, models.CanonicalAttribute.id != canonical_id)
                    .first()
                )
                if existing:
                    raise HTTPException(status_code=400, detail=f"Canonical attribute '{cleaned_name}' already exists.")
                attr.name = cleaned_name
                add_alias(db, attr.id, cleaned_name, source="rename", confidence=1.0, approved=True, reindex=False)

        if payload.slug is not None:
            requested_slug = payload.slug.strip()
            attr.slug = _unique_slug_for_update(requested_slug or attr.name, canonical_id, db)
        elif payload.name is not None:
            attr.slug = _unique_slug_for_update(attr.name, canonical_id, db)

        if payload.description is not None:
            attr.description = payload.description
        if payload.category_hint is not None:
            attr.category_hint = payload.category_hint
        if payload.sample_values is not None:
            attr.sample_values = normalize_sample_values(payload.sample_values)
        if payload.active is not None:
            attr.active = payload.active

        db.commit()
        attr_id = attr.id

        # Embeddings are a secondary index. Editing should succeed even if local AI is unavailable.
        safe_reindex_canonical_attribute(db, attr_id)

        result = get_canonical(db, attr_id)
        if not result:
            raise HTTPException(status_code=500, detail="Canonical attribute was updated but could not be loaded.")
        return result
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Database constraint error. This name, slug, or alias may already exist.") from exc


@router.delete("/{canonical_id}")
def deactivate_canonical(canonical_id: int, db: Session = Depends(get_db)):
    attr = get_canonical(db, canonical_id)
    if not attr:
        raise HTTPException(status_code=404, detail="Canonical attribute not found.")
    attr.active = False
    db.commit()
    return {"ok": True, "canonical_id": canonical_id, "active": False}
