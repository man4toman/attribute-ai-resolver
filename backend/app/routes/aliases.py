from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.services import add_alias

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
