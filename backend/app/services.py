from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app import models
from app.config import get_settings
from app.embedding import encode_texts
from app.normalizer import make_slug, normalize_sample_values, normalize_text

settings = get_settings()


def unique_slug(db: Session, requested: str) -> str:
    base = make_slug(requested)
    slug = base
    counter = 2
    while db.query(models.CanonicalAttribute).filter(models.CanonicalAttribute.slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def get_canonical(db: Session, canonical_id: int) -> models.CanonicalAttribute | None:
    return (
        db.query(models.CanonicalAttribute)
        .options(selectinload(models.CanonicalAttribute.aliases))
        .filter(models.CanonicalAttribute.id == canonical_id)
        .first()
    )


def create_canonical_attribute(
    db: Session,
    name: str,
    slug: str | None = None,
    description: str | None = None,
    category_hint: str | None = None,
    sample_values: list[str] | None = None,
    aliases: list[str] | None = None,
    reindex: bool = True,
) -> models.CanonicalAttribute:
    final_slug = slug or unique_slug(db, name)
    if slug and db.query(models.CanonicalAttribute).filter(models.CanonicalAttribute.slug == slug).first():
        final_slug = unique_slug(db, slug)

    attr = models.CanonicalAttribute(
        name=name.strip(),
        slug=final_slug,
        description=description,
        category_hint=category_hint or "",
        sample_values=normalize_sample_values(sample_values),
        active=True,
    )
    db.add(attr)
    db.flush()

    all_aliases = [name] + list(aliases or [])
    for alias in all_aliases:
        add_alias(db, attr.id, alias, source="initial", confidence=1.0, approved=True, reindex=False)

    if reindex:
        reindex_canonical_attribute(db, attr.id)

    db.commit()
    db.refresh(attr)
    return attr


def add_alias(
    db: Session,
    canonical_id: int,
    alias_raw: str,
    source: str = "manual",
    confidence: float = 1.0,
    approved: bool = True,
    reindex: bool = True,
) -> models.AttributeAlias:
    alias_norm = normalize_text(alias_raw)
    if not alias_norm:
        raise ValueError("Alias becomes empty after normalization.")

    existing = db.query(models.AttributeAlias).filter(models.AttributeAlias.alias_norm == alias_norm).first()
    if existing:
        if existing.canonical_id == canonical_id:
            return existing
        raise ValueError(
            f"Alias '{alias_raw}' is already mapped to canonical_id={existing.canonical_id}."
        )

    alias = models.AttributeAlias(
        canonical_id=canonical_id,
        alias_raw=alias_raw.strip(),
        alias_norm=alias_norm,
        source=source,
        confidence=confidence,
        approved=approved,
    )
    db.add(alias)
    db.flush()

    if reindex:
        reindex_canonical_attribute(db, canonical_id)
        db.commit()
        db.refresh(alias)

    return alias


def build_embedding_texts(attr: models.CanonicalAttribute) -> list[tuple[str, str]]:
    aliases = [a.alias_norm for a in attr.aliases if a.approved]
    name_norm = normalize_text(attr.name)
    category = normalize_text(attr.category_hint or "")
    sample_values = attr.sample_values or []
    values = ", ".join(str(v) for v in sample_values[:20])
    alias_blob = ", ".join(sorted(set(aliases)))

    texts: list[tuple[str, str]] = []
    texts.append(
        (
            "canonical",
            f"attribute name: {name_norm} | aliases: {alias_blob} | category: {category} | sample values: {values}",
        )
    )

    for alias in sorted(set(aliases)):
        texts.append(
            (
                "alias",
                f"attribute alias: {alias} | canonical attribute: {name_norm} | category: {category} | sample values: {values}",
            )
        )

    return texts


def reindex_canonical_attribute(db: Session, canonical_id: int) -> int:
    attr = get_canonical(db, canonical_id)
    if not attr:
        raise ValueError(f"Canonical attribute {canonical_id} not found.")

    db.query(models.AttributeEmbedding).filter(
        models.AttributeEmbedding.canonical_id == canonical_id
    ).delete(synchronize_session=False)
    db.flush()

    text_pairs = build_embedding_texts(attr)
    vectors = encode_texts([text for _, text in text_pairs])

    for (source_type, source_text), vector in zip(text_pairs, vectors, strict=True):
        if len(vector) != settings.embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch. Got {len(vector)}, expected {settings.embedding_dimension}. "
                "Set EMBEDDING_DIMENSION to match the selected model."
            )
        db.add(
            models.AttributeEmbedding(
                canonical_id=canonical_id,
                source_type=source_type,
                source_text=source_text,
                embedding=vector,
            )
        )

    db.flush()
    return len(text_pairs)


def reindex_all(db: Session) -> tuple[int, int]:
    ids = [row[0] for row in db.query(models.CanonicalAttribute.id).filter(models.CanonicalAttribute.active.is_(True)).all()]
    total_embeddings = 0
    for canonical_id in ids:
        total_embeddings += reindex_canonical_attribute(db, canonical_id)
    db.commit()
    return len(ids), total_embeddings


def stats(db: Session) -> dict:
    return {
        "canonical_count": db.query(func.count(models.CanonicalAttribute.id)).scalar() or 0,
        "alias_count": db.query(func.count(models.AttributeAlias.id)).scalar() or 0,
        "embedding_count": db.query(func.count(models.AttributeEmbedding.id)).scalar() or 0,
        "open_review_count": db.query(func.count(models.ReviewItem.id)).filter(models.ReviewItem.status == "open").scalar() or 0,
        "approved_review_count": db.query(func.count(models.ReviewItem.id)).filter(models.ReviewItem.status == "approved").scalar() or 0,
        "ignored_review_count": db.query(func.count(models.ReviewItem.id)).filter(models.ReviewItem.status == "ignored").scalar() or 0,
    }
