from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.services import add_alias, create_canonical_attribute

router = APIRouter(prefix="/review", tags=["review queue"])


def _get_review(db: Session, review_id: int) -> models.ReviewItem:
    review = db.get(models.ReviewItem, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found.")
    return review


@router.get("", response_model=list[schemas.ReviewOut])
def list_reviews(
    status: str = Query(default="open"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.ReviewItem)
        .filter(models.ReviewItem.status == status)
        .order_by(models.ReviewItem.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{review_id}", response_model=schemas.ReviewOut)
def get_review(review_id: int, db: Session = Depends(get_db)):
    return _get_review(db, review_id)


@router.post("/{review_id}/approve", response_model=schemas.ReviewOut)
def approve_review(
    review_id: int,
    payload: schemas.ApproveReviewRequest,
    db: Session = Depends(get_db),
):
    review = _get_review(db, review_id)
    attr = db.get(models.CanonicalAttribute, payload.canonical_id)
    if not attr:
        raise HTTPException(status_code=404, detail="Canonical attribute not found.")

    try:
        alias = add_alias(
            db=db,
            canonical_id=attr.id,
            alias_raw=payload.alias_raw or review.input_raw,
            source="review-approved",
            confidence=review.candidate_score or 1.0,
            approved=True,
            reindex=True,
        )
        review.status = "approved"
        review.decision = "approved_match"
        review.resolved_attribute_id = attr.id
        review.created_alias_id = alias.id
        review.notes = payload.notes
        db.commit()
        db.refresh(review)
        return review
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{review_id}/create-attribute", response_model=schemas.ReviewOut)
def create_attribute_from_review(
    review_id: int,
    payload: schemas.CreateFromReviewRequest,
    db: Session = Depends(get_db),
):
    review = _get_review(db, review_id)
    name = payload.name or review.input_raw
    aliases = [review.input_raw] + payload.aliases

    try:
        attr = create_canonical_attribute(
            db=db,
            name=name,
            slug=payload.slug,
            description=payload.description,
            category_hint=payload.category_hint or review.category,
            sample_values=review.sample_values,
            aliases=aliases,
            reindex=True,
        )
        review.status = "approved"
        review.decision = "created_new_attribute"
        review.resolved_attribute_id = attr.id
        review.notes = payload.notes
        db.commit()
        db.refresh(review)
        return review
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{review_id}/ignore", response_model=schemas.ReviewOut)
def ignore_review(
    review_id: int,
    payload: schemas.IgnoreReviewRequest,
    db: Session = Depends(get_db),
):
    review = _get_review(db, review_id)
    review.status = "ignored"
    review.decision = "ignored"
    review.notes = payload.notes
    db.commit()
    db.refresh(review)
    return review
