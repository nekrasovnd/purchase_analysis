from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time

import pandas as pd

from purchase_analysis import entity_resolution
from purchase_analysis.clients import tektorg
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "tektorg_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")

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
    raw_dir = RAW_DIR / "tektorg" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir)
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = tektorg.create_session(timeout=30)
    item_rows: list[dict[str, object]] = []
    
    unique_rows = 0

    for entity in scope:
        if not entity.inn:
            continue
        print(f"[{entity.entity_name}] Searching for INN: {entity.inn}")
        
        page = 1
        while True:
            time.sleep(args.throttle)
            print(f"  Fetching page {page}...")
            request_xml = tektorg.build_request_xml(customer_inn=entity.inn, page=page, limit_page=100)
            
            try:
                response_xml = tektorg.fetch_procedures(request_xml, session=session)
            except Exception as e:
                print(f"  [ERROR] fetching SOAP response: {e}")
                break
                
            slug = safe_slug(f"{entity.entity_name}_{entity.inn}_p{page}")
            write_text(raw_dir / f"{slug}.xml", response_xml)
            
            try:
                response = tektorg.parse_search_response(
                    response_xml,
                    entity_name=entity.entity_name,
                    customer_query=entity.inn
                )
            except Exception as e:
                print(f"  [ERROR] parsing SOAP XML: {e}")
                break
                
            if response.fault_string:
                print(f"  [FAULT] from API: {response.fault_string}")
                break
                
            print(f"  Found {len(response.items)} items on page {page}.")
            if not response.items:
                break

            for item in response.items:
                unique_rows += 1
                item_rows.append(tektorg.search_item_to_dict(item))
                
            if response.current_page >= response.total_pages or not response.total_pages:
                break
            page += 1

    print("\n--- SPRINT SUMMARY ---")
    print(f"New Unique Lots Found: {unique_rows}")

    if item_rows:
        write_frame(out_dir / "items.csv", item_rows)
        print(f"Saved {len(item_rows)} items to {out_dir / 'items.csv'}")

if __name__ == "__main__":
    main()
