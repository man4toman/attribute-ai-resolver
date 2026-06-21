from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AliasOut(BaseModel):
    id: int
    canonical_id: int
    alias_raw: str
    alias_norm: str
    source: str
    confidence: float
    approved: bool

    model_config = {"from_attributes": True}


class CanonicalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = None
    description: str | None = None
    category_hint: str | None = None
    sample_values: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    # Keep API usable even if local embedding model is not ready.
    # The route will create the attribute first and then try to reindex.
    reindex: bool = True


class CanonicalUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    category_hint: str | None = None
    sample_values: list[str] | None = None
    active: bool | None = None
    reindex: bool = True


class CanonicalOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    category_hint: str | None = None
    sample_values: list[Any] = Field(default_factory=list)
    active: bool
    aliases: list[AliasOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AliasCreate(BaseModel):
    canonical_id: int
    alias_raw: str = Field(min_length=1, max_length=255)
    source: str = "manual"
    confidence: float = 1.0
    approved: bool = True
    reindex: bool = True


class AliasUpdate(BaseModel):
    alias_raw: str | None = Field(default=None, min_length=1, max_length=255)
    source: str | None = None
    confidence: float | None = None
    approved: bool | None = None
    reindex: bool = True


class ResolveRequest(BaseModel):
    raw_name: str = Field(min_length=1, max_length=255)
    category: str | None = ""
    sample_values: list[str] = Field(default_factory=list)
    create_review: bool = True


class CandidateOut(BaseModel):
    canonical_id: int
    name: str
    slug: str
    score: float
    source_text: str | None = None


class ResolveResponse(BaseModel):
    decision: Literal["match", "review", "create_new_candidate"]
    method: str
    confidence: float | None = None
    input_raw: str
    input_norm: str
    attribute: CanonicalOut | None = None
    candidates: list[CandidateOut] = Field(default_factory=list)
    fuzzy_candidate: CandidateOut | None = None
    review_id: int | None = None
    message: str | None = None


class ReviewOut(BaseModel):
    id: int
    input_raw: str
    input_norm: str
    category: str | None = None
    sample_values: list[Any] = Field(default_factory=list)
    status: str
    decision: str
    candidate_id: int | None = None
    candidate_score: float | None = None
    second_candidate_id: int | None = None
    second_candidate_score: float | None = None
    fuzzy_candidate_id: int | None = None
    fuzzy_score: float | None = None
    resolved_attribute_id: int | None = None
    candidates_snapshot: list[Any] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApproveReviewRequest(BaseModel):
    canonical_id: int
    alias_raw: str | None = None
    notes: str | None = None


class CreateFromReviewRequest(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    category_hint: str | None = None
    aliases: list[str] = Field(default_factory=list)
    notes: str | None = None
    # If true, embeddings are built after the canonical attribute is saved.
    # If embedding generation fails, the review is still approved and a note is saved.
    reindex: bool = True


class IgnoreReviewRequest(BaseModel):
    notes: str | None = None


class StatsOut(BaseModel):
    canonical_count: int
    alias_count: int
    embedding_count: int
    open_review_count: int
    approved_review_count: int
    ignored_review_count: int


class ReindexResponse(BaseModel):
    indexed_attributes: int
    indexed_embeddings: int
