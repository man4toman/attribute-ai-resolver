from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
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


def _database_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail=f"Database error: {type(exc).__name__}: {exc}",
    )


def _review_query(db: Session, status: str):
    query = db.query(models.ReviewItem)
    if status and status != "all":
        query = query.filter(models.ReviewItem.status == status)
    return query


@router.get("", response_model=list[schemas.ReviewOut])
def list_reviews(
    status: str = Query(default="open"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return (
        _review_query(db, status)
        .order_by(models.ReviewItem.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/page")
def page_reviews(
    status: str = Query(default="open"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = _review_query(db, status)
    total = query.order_by(None).count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(page, 1), total_pages)
    offset = (page - 1) * page_size
    items = query.order_by(models.ReviewItem.id.desc()).offset(offset).limit(page_size).all()
    return {
        "items": [schemas.ReviewOut.model_validate(item).model_dump(mode="json") for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/count")
def count_reviews(
    status: str = Query(default="open"),
    db: Session = Depends(get_db),
):
    total = _review_query(db, status).count()
    return {"total": total}


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
            fail_on_reindex_error=False,
        )
        review = _get_review(db, review_id)
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
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Integrity error: {exc.orig}") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _database_error(exc) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {type(exc).__name__}: {exc}") from exc


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
            fail_on_reindex_error=False,
        )
        review = _get_review(db, review_id)
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
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Integrity error: {exc.orig}") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _database_error(exc) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {type(exc).__name__}: {exc}") from exc


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
