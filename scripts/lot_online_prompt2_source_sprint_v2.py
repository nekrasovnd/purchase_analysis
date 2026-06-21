from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time
import json

import pandas as pd

from purchase_analysis import entity_resolution
from purchase_analysis.clients import lot_online
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "lot_online_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    rows = entity_resolution.load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
    if not selected_inns:
        return rows
    return [row for row in rows if row.inn in selected_inns]


def write_frame(path: Path, rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    ensure_dir(path.parent)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inns", nargs="*", help="Specific INNs to run")
    parser.add_argument("--throttle", type=float, default=2.0)
    args = parser.parse_args()

    batch_name = safe_slug(args.batch_name)
    raw_dir = RAW_DIR / "lot_online" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir / "search")
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = lot_online.create_session(timeout=60)
    item_rows: list[dict[str, object]] = []
    
    unique_rows = 0

    for entity in scope:
        queries = entity_resolution.build_search_terms(entity, source_system="lot_online")
        for query in queries:
            print(f"[{entity.entity_name}] Searching for: {query}")
            slug = safe_slug(f"{entity.entity_name}_{query}")
            
            try:
                pages = lot_online.fetch_all_search_pages(
                    query=lot_online.build_query_payload(title=query),
                    max_pages=20,
                    session=session,
                    timeout=60
                )
                
                for page_number, payload in enumerate(pages, start=1):
                    # `pages` is a list of tuples: (payload_dict, url)
                    page_payload, page_url = payload
                    write_text(raw_dir / "search" / f"{slug}_p{page_number}.json", json.dumps(page_payload, ensure_ascii=False, indent=2))
                    
                    items = lot_online.parse_search_items(
                        page_payload,
                        entity_name=entity.entity_name,
                        customer_query=query
                    )
                    
                    print(f"  Page {page_number}: found {len(items)} lots.")
                    for item in items:
                        unique_rows += 1
                        item_rows.append(lot_online.search_item_to_dict(item))
            except Exception as e:
                print(f"  [ERROR] fetching or parsing for query {query}: {e}")
                continue

    print("\n--- SPRINT SUMMARY ---")
    print(f"New Unique Lots Found: {unique_rows}")

    if item_rows:
        write_frame(out_dir / "items.csv", item_rows)
        print(f"Saved {len(item_rows)} items to {out_dir / 'items.csv'}")

if __name__ == "__main__":
    main()
