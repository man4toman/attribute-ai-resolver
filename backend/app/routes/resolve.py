from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.resolver import resolve_attribute

router = APIRouter(tags=["resolve"])


@router.post("/resolve", response_model=schemas.ResolveResponse)
def resolve(payload: schemas.ResolveRequest, db: Session = Depends(get_db)):
    return resolve_attribute(
        db=db,
        raw_name=payload.raw_name,
        category=payload.category,
        sample_values=payload.sample_values,
        create_review=payload.create_review,
    )
