from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal, init_db
from app.models import CanonicalAttribute
from app.services import add_alias, create_canonical_attribute, reindex_canonical_attribute


def parse_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split("|") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Import canonical attributes and aliases from CSV.")
    parser.add_argument("csv_path", help="CSV with canonical_name, alias, category_hint, sample_values columns")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    grouped: dict[str, dict] = defaultdict(lambda: {"aliases": set(), "sample_values": [], "category_hint": ""})

    with open(args.csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical_name = (row.get("canonical_name") or "").strip()
            if not canonical_name:
                continue
            alias = (row.get("alias") or "").strip()
            if alias:
                grouped[canonical_name]["aliases"].add(alias)
            if row.get("category_hint"):
                grouped[canonical_name]["category_hint"] = row["category_hint"].strip()
            grouped[canonical_name]["sample_values"].extend(parse_values(row.get("sample_values")))

    try:
        for name, data in grouped.items():
            attr = db.query(CanonicalAttribute).filter(CanonicalAttribute.name == name).first()
            if not attr:
                attr = create_canonical_attribute(
                    db=db,
                    name=name,
                    category_hint=data["category_hint"],
                    sample_values=data["sample_values"],
                    aliases=sorted(data["aliases"]),
                    reindex=True,
                )
                print(f"created {attr.id}: {name}")
            else:
                for alias in sorted(data["aliases"]):
                    add_alias(db, attr.id, alias, source="csv-import", reindex=False)
                reindex_canonical_attribute(db, attr.id)
                db.commit()
                print(f"updated {attr.id}: {name}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
