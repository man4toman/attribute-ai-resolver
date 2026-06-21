from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session, selectinload

from app import models
from app.config import get_settings
from app.embedding import encode_one
from app.normalizer import normalize_sample_values, normalize_text

settings = get_settings()


@dataclass
class SemanticCandidate:
    canonical_id: int
    name: str
    slug: str
    score: float
    source_text: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "name": self.name,
            "slug": self.slug,
            "score": round(float(self.score), 6),
            "source_text": self.source_text,
        }


def build_query_text(raw_name: str, category: str | None, sample_values: list[str] | None) -> str:
    name_norm = normalize_text(raw_name)
    category_norm = normalize_text(category or "")
    values = ", ".join(str(v) for v in normalize_sample_values(sample_values)[:20])
    return f"attribute name: {name_norm} | category: {category_norm} | sample values: {values}"


def _candidate_from_attr(attr: models.CanonicalAttribute, score: float, source_text: str | None = None) -> SemanticCandidate:
    return SemanticCandidate(
        canonical_id=attr.id,
        name=attr.name,
        slug=attr.slug,
        score=float(score),
        source_text=source_text,
    )


def _log_resolution(
    db: Session,
    input_raw: str,
    input_norm: str,
    decision: str,
    method: str,
    confidence: float | None,
    matched_attribute_id: int | None,
    payload: dict,
) -> None:
    db.add(
        models.ResolutionLog(
            input_raw=input_raw,
            input_norm=input_norm,
            decision=decision,
            method=method,
            confidence=confidence,
            matched_attribute_id=matched_attribute_id,
            payload=payload,
        )
    )
    db.flush()


def exact_alias_match(db: Session, input_norm: str) -> models.CanonicalAttribute | None:
    alias = (
        db.query(models.AttributeAlias)
        .join(models.CanonicalAttribute)
        .options(selectinload(models.AttributeAlias.canonical).selectinload(models.CanonicalAttribute.aliases))
        .filter(models.AttributeAlias.alias_norm == input_norm)
        .filter(models.AttributeAlias.approved.is_(True))
        .filter(models.CanonicalAttribute.active.is_(True))
        .first()
    )
    return alias.canonical if alias else None


def fuzzy_match(db: Session, input_norm: str) -> tuple[models.CanonicalAttribute | None, float]:
    aliases = (
        db.query(models.AttributeAlias)
        .join(models.CanonicalAttribute)
        .options(selectinload(models.AttributeAlias.canonical).selectinload(models.CanonicalAttribute.aliases))
        .filter(models.AttributeAlias.approved.is_(True))
        .filter(models.CanonicalAttribute.active.is_(True))
        .all()
    )
    if not aliases:
        return None, 0.0

    alias_by_norm = {a.alias_norm: a for a in aliases}
    match = process.extractOne(input_norm, list(alias_by_norm.keys()), scorer=fuzz.WRatio)
    if not match:
        return None, 0.0

    matched_norm, score, _ = match
    return alias_by_norm[matched_norm].canonical, float(score) / 100.0


def semantic_candidates(
    db: Session,
    raw_name: str,
    category: str | None,
    sample_values: list[str] | None,
) -> list[SemanticCandidate]:
    query_text = build_query_text(raw_name, category, sample_values)
    query_vector = encode_one(query_text)

    distance = models.AttributeEmbedding.embedding.cosine_distance(query_vector)
    rows = (
        db.query(models.AttributeEmbedding, models.CanonicalAttribute, distance.label("distance"))
        .join(models.CanonicalAttribute, models.AttributeEmbedding.canonical_id == models.CanonicalAttribute.id)
        .filter(models.CanonicalAttribute.active.is_(True))
        .order_by(distance)
        .limit(settings.max_semantic_candidates)
        .all()
    )

    best_by_canonical: dict[int, SemanticCandidate] = {}
    for emb, attr, dist in rows:
        score = 1.0 - float(dist)
        previous = best_by_canonical.get(attr.id)
        if previous is None or score > previous.score:
            best_by_canonical[attr.id] = _candidate_from_attr(attr, score, emb.source_text)

    return sorted(best_by_canonical.values(), key=lambda c: c.score, reverse=True)


def create_or_update_review(
    db: Session,
    input_raw: str,
    input_norm: str,
    category: str | None,
    sample_values: list[str] | None,
    decision: str,
    candidates: list[SemanticCandidate],
    fuzzy_candidate: SemanticCandidate | None,
) -> models.ReviewItem:
    existing = (
        db.query(models.ReviewItem)
        .filter(models.ReviewItem.input_norm == input_norm)
        .filter(models.ReviewItem.status == "open")
        .first()
    )

    best = candidates[0] if candidates else None
    second = candidates[1] if len(candidates) > 1 else None

    if existing:
        review = existing
    else:
        review = models.ReviewItem(input_raw=input_raw, input_norm=input_norm)
        db.add(review)

    review.category = category or ""
    review.sample_values = normalize_sample_values(sample_values)
    review.status = "open"
    review.decision = decision
    review.candidate_id = best.canonical_id if best else None
    review.candidate_score = best.score if best else None
    review.second_candidate_id = second.canonical_id if second else None
    review.second_candidate_score = second.score if second else None
    review.fuzzy_candidate_id = fuzzy_candidate.canonical_id if fuzzy_candidate else None
    review.fuzzy_score = fuzzy_candidate.score if fuzzy_candidate else None
    review.candidates_snapshot = [c.as_dict() for c in candidates[:8]]
    db.flush()
    return review


def resolve_attribute(
    db: Session,
    raw_name: str,
    category: str | None = "",
    sample_values: list[str] | None = None,
    create_review: bool = True,
) -> dict[str, Any]:
    sample_values = sample_values or []
    input_norm = normalize_text(raw_name)

    exact = exact_alias_match(db, input_norm)
    if exact:
        payload = {
            "decision": "match",
            "method": "exact_alias",
            "confidence": 1.0,
            "input_raw": raw_name,
            "input_norm": input_norm,
            "attribute": exact,
            "candidates": [],
            "fuzzy_candidate": None,
            "review_id": None,
            "message": "Matched by approved alias.",
        }
        _log_resolution(db, raw_name, input_norm, "match", "exact_alias", 1.0, exact.id, {"input_norm": input_norm})
        db.commit()
        return payload

    fuzzy_attr, fuzzy_score = fuzzy_match(db, input_norm)
    fuzzy_candidate = _candidate_from_attr(fuzzy_attr, fuzzy_score) if fuzzy_attr else None
    if fuzzy_attr and fuzzy_score >= settings.fuzzy_auto_threshold / 100.0:
        payload = {
            "decision": "match",
            "method": "fuzzy",
            "confidence": fuzzy_score,
            "input_raw": raw_name,
            "input_norm": input_norm,
            "attribute": fuzzy_attr,
            "candidates": [],
            "fuzzy_candidate": fuzzy_candidate.as_dict() if fuzzy_candidate else None,
            "review_id": None,
            "message": "Matched by high-confidence fuzzy similarity.",
        }
        _log_resolution(
            db,
            raw_name,
            input_norm,
            "match",
            "fuzzy",
            fuzzy_score,
            fuzzy_attr.id,
            {"fuzzy_candidate": fuzzy_candidate.as_dict() if fuzzy_candidate else None},
        )
        db.commit()
        return payload

    has_embeddings = db.query(models.AttributeEmbedding.id).first() is not None
    candidates = semantic_candidates(db, raw_name, category, sample_values) if has_embeddings else []
    best = candidates[0] if candidates else None
    second = candidates[1] if len(candidates) > 1 else None
    gap = best.score - second.score if best and second else best.score if best else 0.0

    if best and best.score >= settings.semantic_auto_threshold and gap >= settings.semantic_gap_threshold:
        attr = db.get(models.CanonicalAttribute, best.canonical_id)
        payload = {
            "decision": "match",
            "method": "semantic",
            "confidence": best.score,
            "input_raw": raw_name,
            "input_norm": input_norm,
            "attribute": attr,
            "candidates": [c.as_dict() for c in candidates[:5]],
            "fuzzy_candidate": fuzzy_candidate.as_dict() if fuzzy_candidate else None,
            "review_id": None,
            "message": "Matched by semantic similarity.",
        }
        _log_resolution(
            db,
            raw_name,
            input_norm,
            "match",
            "semantic",
            best.score,
            best.canonical_id,
            {"candidates": [c.as_dict() for c in candidates[:5]], "gap": gap},
        )
        db.commit()
        return payload

    if best and best.score >= settings.semantic_review_threshold:
        decision = "review"
        method = "semantic_uncertain"
        confidence = best.score
        message = "Needs human review. Semantic score is promising but not safe enough for auto-merge."
    else:
        decision = "create_new_candidate"
        method = "low_confidence"
        confidence = best.score if best else 0.0
        message = "Likely a new attribute, but queued for review by default."

    review_id = None
    if create_review:
        review = create_or_update_review(
            db,
            input_raw=raw_name,
            input_norm=input_norm,
            category=category,
            sample_values=sample_values,
            decision=decision,
            candidates=candidates,
            fuzzy_candidate=fuzzy_candidate,
        )
        review_id = review.id

    _log_resolution(
        db,
        raw_name,
        input_norm,
        decision,
        method,
        confidence,
        None,
        {
            "candidates": [c.as_dict() for c in candidates[:5]],
            "fuzzy_candidate": fuzzy_candidate.as_dict() if fuzzy_candidate else None,
            "review_id": review_id,
            "gap": gap,
        },
    )
    db.commit()

    return {
        "decision": decision,
        "method": method,
        "confidence": confidence,
        "input_raw": raw_name,
        "input_norm": input_norm,
        "attribute": None,
        "candidates": [c.as_dict() for c in candidates[:5]],
        "fuzzy_candidate": fuzzy_candidate.as_dict() if fuzzy_candidate else None,
        "review_id": review_id,
        "message": message,
    }
