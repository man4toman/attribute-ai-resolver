from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.config import get_settings
from app.db import Base

settings = get_settings()


class CanonicalAttribute(Base):
    __tablename__ = "canonical_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sample_values: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    aliases: Mapped[list["AttributeAlias"]] = relationship(
        back_populates="canonical", cascade="all, delete-orphan"
    )
    embeddings: Mapped[list["AttributeEmbedding"]] = relationship(
        back_populates="canonical", cascade="all, delete-orphan"
    )


class AttributeAlias(Base):
    __tablename__ = "attribute_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    canonical_id: Mapped[int] = mapped_column(ForeignKey("canonical_attributes.id", ondelete="CASCADE"), index=True)
    alias_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_norm: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64), default="manual", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    canonical: Mapped[CanonicalAttribute] = relationship(back_populates="aliases")


class AttributeEmbedding(Base):
    __tablename__ = "attribute_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    canonical_id: Mapped[int] = mapped_column(ForeignKey("canonical_attributes.id", ondelete="CASCADE"), index=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), default="canonical", nullable=False)
    embedding = mapped_column(Vector(settings.embedding_dimension), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    canonical: Mapped[CanonicalAttribute] = relationship(back_populates="embeddings")


Index(
    "ix_attribute_embeddings_embedding_hnsw",
    AttributeEmbedding.embedding,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)


class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    input_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    input_norm: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sample_values: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)

    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("canonical_attributes.id"), nullable=True)
    candidate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    second_candidate_id: Mapped[int | None] = mapped_column(ForeignKey("canonical_attributes.id"), nullable=True)
    second_candidate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuzzy_candidate_id: Mapped[int | None] = mapped_column(ForeignKey("canonical_attributes.id"), nullable=True)
    fuzzy_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    resolved_attribute_id: Mapped[int | None] = mapped_column(ForeignKey("canonical_attributes.id"), nullable=True)
    created_alias_id: Mapped[int | None] = mapped_column(ForeignKey("attribute_aliases.id"), nullable=True)

    candidates_snapshot: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    candidate: Mapped[CanonicalAttribute | None] = relationship(foreign_keys=[candidate_id])
    second_candidate: Mapped[CanonicalAttribute | None] = relationship(foreign_keys=[second_candidate_id])
    fuzzy_candidate: Mapped[CanonicalAttribute | None] = relationship(foreign_keys=[fuzzy_candidate_id])
    resolved_attribute: Mapped[CanonicalAttribute | None] = relationship(foreign_keys=[resolved_attribute_id])



class ResolutionLog(Base):
    __tablename__ = "resolution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    input_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    input_norm: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    matched_attribute_id: Mapped[int | None] = mapped_column(ForeignKey("canonical_attributes.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    matched_attribute: Mapped[CanonicalAttribute | None] = relationship()
