from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time

import pandas as pd

from purchase_analysis import entity_resolution
from purchase_analysis.clients import tender_pro
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "tender_pro_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")

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
    parser.add_argument("--throttle", type=float, default=1.0)
    args = parser.parse_args()

    batch_name = safe_slug(args.batch_name)
    raw_dir = RAW_DIR / "tender_pro" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir / "search")
    ensure_dir(raw_dir / "purchases")
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = tender_pro.create_session(timeout=30)
    item_rows: list[dict[str, object]] = []
    
    unique_rows = 0

    for entity in scope:
        if not entity.inn:
            continue
            
        print(f"[{entity.entity_name}] Searching for INN: {entity.inn}")
        time.sleep(args.throttle)
        
        try:
            search_html, search_url = tender_pro.fetch_company_search_page(
                inn=entity.inn,
                session=session
            )
        except Exception as e:
            print(f"  [ERROR] fetching search page: {e}")
            continue
            
        slug = safe_slug(f"{entity.entity_name}_{entity.inn}")
        write_text(raw_dir / "search" / f"{slug}.html", search_html)
        
        candidates = tender_pro.parse_company_candidates(search_html)
        print(f"  Found {len(candidates)} company candidates.")
        
        for candidate in candidates:
            print(f"    -> Fetching purchases for company {candidate.company_id}")
            page = 1
            while True:
                time.sleep(args.throttle)
                try:
                    purchases_html, pur_url = tender_pro.fetch_company_purchases_page(
                        company_id=candidate.company_id,
                        page=page,
                        session=session
                    )
                except Exception as e:
                    print(f"      [ERROR] fetching purchases page {page}: {e}")
                    break
                    
                write_text(raw_dir / "purchases" / f"{slug}_{candidate.company_id}_p{page}.html", purchases_html)
                
                try:
                    profile = tender_pro.parse_company_profile(purchases_html)
                    items = tender_pro.parse_purchase_items(
                        purchases_html, 
                        entity_name=entity.entity_name,
                        profile=profile
                    )
                except Exception as e:
                    print(f"      [ERROR] parsing purchases: {e}")
                    break
                    
                print(f"      Page {page}: found {len(items)} lots.")
                if not items:
                    break
                    
                for item in items:
                    unique_rows += 1
                    item_rows.append(tender_pro.purchase_item_to_dict(item))
                    
                try:
                    pages = tender_pro.parse_purchase_pages(purchases_html)
                    if not pages or page >= max(pages):
                        break
                except Exception:
                    break
                page += 1

    print("\n--- SPRINT SUMMARY ---")
    print(f"New Unique Lots Found: {unique_rows}")

    if item_rows:
        write_frame(out_dir / "items.csv", item_rows)
        print(f"Saved {len(item_rows)} items to {out_dir / 'items.csv'}")

if __name__ == "__main__":
    main()
