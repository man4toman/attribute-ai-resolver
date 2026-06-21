from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.normalizer import normalize_text
from app.services import add_alias, safe_reindex_canonical_attribute

router = APIRouter(prefix="/aliases", tags=["aliases"])


@router.post("", response_model=schemas.AliasOut)
def create_alias(payload: schemas.AliasCreate, db: Session = Depends(get_db)):
    try:
        alias = add_alias(
            db=db,
            canonical_id=payload.canonical_id,
            alias_raw=payload.alias_raw,
            source=payload.source,
            confidence=payload.confidence,
            approved=payload.approved,
            reindex=payload.reindex,
        )
        if not payload.reindex:
            db.commit()
            db.refresh(alias)
        return alias
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Alias already exists or violates a database constraint.") from exc


@router.patch("/{alias_id}", response_model=schemas.AliasOut)
def update_alias(alias_id: int, payload: schemas.AliasUpdate, db: Session = Depends(get_db)):
    alias = db.get(models.AttributeAlias, alias_id)
    if not alias:
        raise HTTPException(status_code=404, detail="Alias not found.")

    try:
        if payload.alias_raw is not None:
            alias_raw = payload.alias_raw.strip()
            alias_norm = normalize_text(alias_raw)
            if not alias_norm:
                raise ValueError("Alias becomes empty after normalization.")
            existing = (
                db.query(models.AttributeAlias)
                .filter(models.AttributeAlias.alias_norm == alias_norm, models.AttributeAlias.id != alias.id)
                .first()
            )
            if existing:
                raise ValueError(f"Alias '{alias_raw}' is already mapped to canonical_id={existing.canonical_id}.")
            alias.alias_raw = alias_raw
            alias.alias_norm = alias_norm

        if payload.source is not None:
            alias.source = payload.source or "manual"
        if payload.confidence is not None:
            alias.confidence = payload.confidence
        if payload.approved is not None:
            alias.approved = payload.approved

        canonical_id = alias.canonical_id
        db.commit()
        db.refresh(alias)

        if payload.reindex:
            safe_reindex_canonical_attribute(db, canonical_id, fail_on_error=False)
            alias = db.get(models.AttributeAlias, alias_id) or alias

        return alias
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Alias already exists or violates a database constraint.") from exc


@router.delete("/{alias_id}")
def delete_alias(alias_id: int, reindex: bool = True, db: Session = Depends(get_db)):
    alias = db.get(models.AttributeAlias, alias_id)
    if not alias:
        raise HTTPException(status_code=404, detail="Alias not found.")

    canonical_id = alias.canonical_id
    db.delete(alias)
    db.commit()

    if reindex:
        safe_reindex_canonical_attribute(db, canonical_id, fail_on_error=False)

    return {"ok": True, "alias_id": alias_id, "canonical_id": canonical_id}
