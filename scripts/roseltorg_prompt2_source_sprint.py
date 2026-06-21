from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
import time

import pandas as pd

from purchase_analysis import entity_resolution
from purchase_analysis.clients import roseltorg
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "roseltorg_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")
DATE_FROM = "01.01.2024"
DATE_TO = "31.12.2025"

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

def load_existing_lot_keys() -> set[tuple[str, str, str]]:
    path = ROOT_DIR / "data" / "curated" / "procurement_lots.csv"
    if not path.exists():
        return set()
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    keys: set[tuple[str, str, str]] = set()
    for record in frame.to_dict("records"):
        key = (
            normalize_spaces(record.get("source_system")),
            normalize_spaces(record.get("procedure_number")),
            normalize_spaces(record.get("lot_number") or "1"),
        )
        if key[0] and key[1]:
            keys.add(key)
    return keys

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inns", nargs="*", help="Specific INNs to run")
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--throttle", type=float, default=1.0)
    args = parser.parse_args()

    batch_name = safe_slug(args.batch_name)
    raw_dir = RAW_DIR / "roseltorg" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir / "search")
    ensure_dir(raw_dir / "detail")
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)
    existing_keys = load_existing_lot_keys()

    session = roseltorg.create_session(timeout=30)

    item_rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []
    
    unique_rows = 0
    priced_rows = 0
    existing_duplicates = 0

    for entity in scope:
        query = entity.roseltorg_customer_query
        print(f"[{entity.entity_name}] Searching for: {query}")
        
        for page in range(1, args.max_pages + 1):
            time.sleep(args.throttle)
            print(f"  Fetching page {page}...")
            try:
                search_html, search_url = roseltorg.fetch_search_page(
                    customer_query=query,
                    date_from=DATE_FROM,
                    date_to=DATE_TO,
                    page=page,
                    session=session,
                )
            except Exception as e:
                print(f"  [ERROR] fetching search page {page}: {e}")
                break
                
            slug = safe_slug(f"{entity.entity_name}_{query}")
            write_text(raw_dir / "search" / f"{slug}_page_{page}.html", search_html)
            
            try:
                page_items = roseltorg.parse_search_items(search_html, entity.entity_name, query)
            except Exception as e:
                print(f"  [ERROR] parsing search items on page {page}: {e}")
                page_items = []
                
            if not page_items:
                print(f"  No items found on page {page}. Stopping pagination.")
                break
                
            print(f"  Found {len(page_items)} items on page {page}.")
            
            for item in page_items:
                key = (item.source_system, item.procedure_number, item.lot_number or "1")
                if key in existing_keys:
                    existing_duplicates += 1
                    continue
                    
                unique_rows += 1
                if item.price_rub is not None:
                    priced_rows += 1
                    
                item_rows.append(roseltorg.search_item_to_dict(item))
                
                # Fetch detail
                time.sleep(args.throttle)
                try:
                    detail_html = roseltorg.fetch_lot_detail(item.detail_url, session=session)
                    detail_slug = safe_slug(f"{item.procedure_number}_{item.lot_number or '1'}")
                    write_text(raw_dir / "detail" / f"{detail_slug}.html", detail_html)
                    
                    detail, documents = roseltorg.parse_lot_detail(
                        detail_html,
                        item.procedure_number,
                        item.lot_number or "1",
                    )
                    if detail:
                        detail_rows.append(roseltorg.detail_to_dict(detail))
                except Exception as e:
                    print(f"  [ERROR] fetching detail for {item.procedure_number}: {e}")

    print("\n--- SPRINT SUMMARY ---")
    print(f"New Unique Lots Found: {unique_rows}")
    print(f"Priced Lots: {priced_rows}")
    print(f"Existing Duplicates Skipped: {existing_duplicates}")

    if item_rows:
        write_frame(out_dir / "items.csv", item_rows)
        print(f"Saved {len(item_rows)} items to {out_dir / 'items.csv'}")
    if detail_rows:
        write_frame(out_dir / "details.csv", detail_rows)
        print(f"Saved {len(detail_rows)} details to {out_dir / 'details.csv'}")

if __name__ == "__main__":
    main()
