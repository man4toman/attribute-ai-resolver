from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.services import reindex_all

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
