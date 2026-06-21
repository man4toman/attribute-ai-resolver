from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal, init_db
from app.models import CanonicalAttribute
from app.services import create_canonical_attribute

RAM = "\u0631\u0645"
RAM_COMPUTER = "\u0631\u0645 \u06a9\u0627\u0645\u067e\u06cc\u0648\u062a\u0631"
MEMORY_RAM = "\u062d\u0627\u0641\u0638\u0647 \u0631\u0645"
DESCRIPTION = "\u062a\u0648\u0636\u06cc\u062d\u0627\u062a"
MORE_DESCRIPTION = "\u062a\u0648\u0636\u06cc\u062d\u0627\u062a \u0628\u06cc\u0634\u062a\u0631"
EXTRA_DESCRIPTION = "\u062a\u0648\u0636\u06cc\u062d\u0627\u062a \u0627\u0636\u0627\u0641\u06cc"
CPU = "\u067e\u0631\u062f\u0627\u0632\u0646\u062f\u0647"
CPU_ALIAS = "\u0633\u06cc \u067e\u06cc \u06cc\u0648"
STORAGE = "\u062d\u0627\u0641\u0638\u0647 \u062f\u0627\u062e\u0644\u06cc"
SCREEN = "\u0635\u0641\u062d\u0647 \u0646\u0645\u0627\u06cc\u0634"

EXAMPLES = [
    {
        "name": RAM,
        "slug": "ram",
        "aliases": ["ram", "RAM", "Ram", RAM_COMPUTER, MEMORY_RAM, "random access memory"],
        "category_hint": "laptop computer hardware",
        "sample_values": ["8GB", "16GB", "32GB", "DDR4", "DDR5"],
    },
    {
        "name": DESCRIPTION,
        "slug": "description",
        "aliases": [MORE_DESCRIPTION, EXTRA_DESCRIPTION, "desc", "description", "more description"],
        "category_hint": "product content",
        "sample_values": ["short text", "long text"],
    },
    {
        "name": CPU,
        "slug": "cpu",
        "aliases": ["cpu", "processor", CPU_ALIAS],
        "category_hint": "laptop computer hardware",
        "sample_values": ["Intel Core i5", "Intel Core i7", "Ryzen 5"],
    },
    {
        "name": STORAGE,
        "slug": "storage",
        "aliases": ["storage", "hard drive", "ssd", "internal memory"],
        "category_hint": "laptop computer hardware",
        "sample_values": ["256GB", "512GB", "1TB", "SSD"],
    },
    {
        "name": SCREEN,
        "slug": "screen",
        "aliases": ["display", "screen", "monitor"],
        "category_hint": "laptop computer hardware",
        "sample_values": ["13 inch", "15.6 inch", "Full HD", "IPS"],
    },
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        for item in EXAMPLES:
            exists = db.query(CanonicalAttribute).filter(CanonicalAttribute.slug == item["slug"]).first()
            if exists:
                print(f"skip existing: {item['slug']}")
                continue
            attr = create_canonical_attribute(db, **item)
            print(f"created: {attr.id} {attr.slug}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
