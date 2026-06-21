from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.services import reindex_all, safe_reindex_canonical_attribute

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post("/reindex", response_model=schemas.ReindexResponse)
def reindex(db: Session = Depends(get_db)):
    try:
        indexed_attributes, indexed_embeddings = reindex_all(db)
        return {
            "indexed_attributes": indexed_attributes,
            "indexed_embeddings": indexed_embeddings,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {type(exc).__name__}: {exc}") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {type(exc).__name__}: {exc}") from exc


@router.post("/reindex/{canonical_id}")
def reindex_one(canonical_id: int, db: Session = Depends(get_db)):
    count, error = safe_reindex_canonical_attribute(db, canonical_id)
    if error:
        return {
            "indexed_attributes": 0,
            "indexed_embeddings": 0,
            "canonical_id": canonical_id,
            "warning": error,
        }
    return {
        "indexed_attributes": 1,
        "indexed_embeddings": count,
        "canonical_id": canonical_id,
    }
