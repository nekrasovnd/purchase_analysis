from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time
import requests

import pandas as pd

from purchase_analysis import entity_resolution, source_sprint
from purchase_analysis.clients.rts_tender import RtsTenderClient
from purchase_analysis.clients.browser_session import BrowserSession
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir
from purchase_analysis.utils.text import safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "rts_tender_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    return source_sprint.read_scope(selected_inns, scope_path=ROOT_DIR / "configs" / "entity_scope.csv")


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
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = BrowserSession(user_data_dir=".local/rts_profile", headless=True)
    session.start()
    
    try:
        client = RtsTenderClient(session=session)
        
        item_rows: list[dict[str, object]] = []
        
        unique_rows = 0

        for entity in scope:
            queries = entity_resolution.build_search_terms(entity, source_system="rts_tender")
            for query in queries:
                print(f"[{entity.entity_name}] Searching for: {query}")
                
                try:
                    items = client.search(query=query)
                    
                    if not items:
                        print("  No items found.")
                        continue
                        
                    print(f"  Found {len(items)} items. Classifying...")
                    for item in items:
                        # Classification
                        match_result = entity_resolution.classify_entity_match(
                            entity,
                            candidate_name=item.company_name,
                            candidate_inn=item.company_inn,
                            candidate_kpp="",
                            candidate_ogrn="",
                            role="customer"
                        )
                        
                        if not match_result.accepted:
                            # print(f"      [REJECTED] Procedure {item.procedure_number}: {match_result.reason}")
                            continue
                            
                        # It matches!
                        unique_rows += 1
                        print(f"      [ACCEPTED] Procedure {item.procedure_number} (INN: {item.company_inn})")
                        
                        row = {
                            "source_system": "rts_tender",
                            "platform_section": "",
                            "entity_name": entity.entity_name,
                            "customer_query": query,
                            "procedure_number": item.procedure_number,
                            "lot_number": "1",
                            "title": item.title,
                            "url": item.url,
                            "amount": item.amount,
                            "stage": item.stage,
                            "date_published": item.date_published,
                            "company_name": item.company_name,
                            "company_inn": item.company_inn,
                            "organizer_name": item.organizer_name,
                            "organizer_inn": item.organizer_inn,
                            "raw_data": item.raw_html
                        }
                        item_rows.append(row)
                        
                    time.sleep(args.throttle)
                except Exception as e:
                    print(f"  [ERROR] fetching search for query {query}: {e}")
                    continue

        print("\n--- SPRINT SUMMARY ---")
        print(f"New Unique Lots Found: {unique_rows}")

        if item_rows:
            item_df = pd.DataFrame(item_rows)
            item_df = source_sprint.write_items_csv(
                out_dir / "items.csv",
                item_df.to_dict("records"),
                default_source_system="rts_tender",
            )
            print(f"Saved {len(item_df)} items to {out_dir / 'items.csv'}")

    finally:
        session.stop()

if __name__ == "__main__":
    main()
