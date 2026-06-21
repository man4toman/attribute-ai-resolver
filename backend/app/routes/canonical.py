from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.db import get_db
from app.normalizer import make_slug, normalize_sample_values, normalize_text
from app.services import add_alias, create_canonical_attribute, get_canonical, reindex_canonical_attribute, unique_slug

router = APIRouter(prefix="/canonical", tags=["canonical attributes"])


@router.post("", response_model=schemas.CanonicalOut)
def create_canonical(payload: schemas.CanonicalCreate, db: Session = Depends(get_db)):
    try:
        return create_canonical_attribute(
            db=db,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            category_hint=payload.category_hint,
            sample_values=payload.sample_values,
            aliases=payload.aliases,
            reindex=True,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[schemas.CanonicalOut])
def list_canonical(
    q: str | None = Query(default=None),
    active: bool | None = Query(default=True),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models.CanonicalAttribute).options(selectinload(models.CanonicalAttribute.aliases))
    if active is not None:
        query = query.filter(models.CanonicalAttribute.active.is_(active))
    if q:
        raw_q = q.strip()
        norm_q = normalize_text(raw_q)
        raw_like = f"%{raw_q}%"
        norm_like = f"%{norm_q}%" if norm_q else raw_like
        query = (
            query
            .outerjoin(models.AttributeAlias)
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
    return query.order_by(models.CanonicalAttribute.id.desc()).offset(offset).limit(limit).all()


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
        if payload.name is not None and payload.name.strip() != attr.name:
            attr.name = payload.name.strip()
            add_alias(db, attr.id, payload.name, source="rename", confidence=1.0, approved=True, reindex=False)
        if payload.slug is not None:
            attr.slug = payload.slug or unique_slug(db, attr.name)
        elif payload.name is not None:
            attr.slug = make_slug(attr.name)
        if payload.description is not None:
            attr.description = payload.description
        if payload.category_hint is not None:
            attr.category_hint = payload.category_hint
        if payload.sample_values is not None:
            attr.sample_values = normalize_sample_values(payload.sample_values)
        if payload.active is not None:
            attr.active = payload.active

        reindex_canonical_attribute(db, attr.id)
        db.commit()
        db.refresh(attr)
        return attr
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{canonical_id}")
def deactivate_canonical(canonical_id: int, db: Session = Depends(get_db)):
    attr = get_canonical(db, canonical_id)
    if not attr:
        raise HTTPException(status_code=404, detail="Canonical attribute not found.")
    attr.active = False
    db.commit()
    return {"ok": True, "canonical_id": canonical_id, "active": False}
