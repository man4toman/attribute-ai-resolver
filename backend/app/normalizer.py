import re
import unicodedata
from slugify import slugify

# Arabic/Persian character normalizations.
CHAR_MAP = {
    "\u064a": "\u06cc",  # Arabic Yeh -> Persian Yeh
    "\u0649": "\u06cc",  # Alef Maksura -> Persian Yeh
    "\u0643": "\u06a9",  # Arabic Kaf -> Persian Kaf
    "\u06c0": "\u0647",  # Heh with Yeh above -> Heh
    "\u0629": "\u0647",  # Teh Marbuta -> Heh
    "\u0624": "\u0648",
    "\u0625": "\u0627",
    "\u0623": "\u0627",
    "\u0622": "\u0627",
    "\u200c": " ",      # ZWNJ -> space
    "\u200f": " ",      # RTL mark
    "\u200e": " ",      # LTR mark
}

DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")
NON_WORD_RE = re.compile(r"[^0-9a-zA-Z\u0600-\u06ff]+")
SPACE_RE = re.compile(r"\s+")

# These are deliberately conservative. Semantic synonyms belong in the alias table,
# not in the normalizer. This prevents over-merging unrelated attributes.
UNIT_NORMALIZATIONS = {
    "g b": "gb",
    "m b": "mb",
    "t b": "tb",
    "g h z": "ghz",
    "m h z": "mhz",
}


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    text = text.strip().lower()

    for src, dst in CHAR_MAP.items():
        text = text.replace(src, dst)

    text = DIACRITICS_RE.sub("", text)
    text = text.replace("_", " ").replace("-", " ").replace("/", " ")
    text = NON_WORD_RE.sub(" ", text)
    text = SPACE_RE.sub(" ", text).strip()

    for src, dst in UNIT_NORMALIZATIONS.items():
        text = text.replace(src, dst)

    return text


def make_slug(value: str) -> str:
    base = normalize_text(value)
    slug = slugify(base, allow_unicode=False)
    if slug:
        return slug
    # Fallback for attributes that are Persian-only and do not transliterate well.
    return slugify(value, allow_unicode=True) or "attribute"


def normalize_sample_values(values: list[str] | None) -> list[str]:
    if not values:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        norm = normalize_text(value)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(str(value).strip())
    return result
