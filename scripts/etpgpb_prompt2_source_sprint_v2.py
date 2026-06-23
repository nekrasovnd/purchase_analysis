from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time
import requests

import pandas as pd

from purchase_analysis import entity_resolution, source_sprint
from purchase_analysis.clients.etpgpb import EtpgpbClient
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir
from purchase_analysis.utils.text import safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "etpgpb_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    return source_sprint.read_scope(selected_inns, scope_path=ROOT_DIR / "configs" / "entity_scope.csv")


def write_frame(path: Path, rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    ensure_dir(path.parent)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame

def download_document(url: str, save_path: Path, session: requests.Session) -> bool:
    try:
        res = session.get(url, stream=True, timeout=30)
        res.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"        [DOC ERROR] Failed to download {url}: {e}")
        return False

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inns", nargs="*", help="Specific INNs to run")
    parser.add_argument("--throttle", type=float, default=2.0)
    args = parser.parse_args()

    batch_name = safe_slug(args.batch_name)
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    doc_dir = out_dir / "documents"
    ensure_dir(out_dir)
    ensure_dir(doc_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    client = EtpgpbClient()
    
    item_rows: list[dict[str, object]] = []
    
    unique_rows = 0

    for entity in scope:
        queries = entity_resolution.build_search_terms(entity, source_system="etpgpb")
        for query in queries:
            print(f"[{entity.entity_name}] Searching for: {query}")
            
            try:
                # ETP GPB search is full-text and somewhat loose, so we fetch up to 100 items per query
                # to avoid hitting rate limits or pulling useless data for vague queries.
                items = client.search(query=query, limit=100)
                
                if not items:
                    print("  No items found.")
                    continue
                    
                print(f"  Found {len(items)} items. Classifying...")
                for item in items:
                    # Classification
                    company_name = item.company_name or ""
                    match_result = entity_resolution.classify_entity_match(
                        entity,
                        candidate_name=company_name,
                        candidate_inn="",
                        candidate_kpp="",
                        candidate_ogrn="",
                        role="customer"
                    )
                    
                    if not match_result.accepted:
                        continue
                        
                    # It matches!
                    unique_rows += 1
                    print(f"      [ACCEPTED] Procedure {item.registry_number or item.id} by {company_name}")
                    
                    # Try to fetch detail and documents
                    docs_downloaded = 0
                    try:
                        detail = client.fetch_procedure_detail(item.id, item.url)
                        # Download documents
                        for doc in detail.documents:
                            doc_ext = Path(doc.url.split("?")[0]).suffix
                            if not doc_ext:
                                doc_ext = ".pdf" # Default
                            doc_filename = f"{item.id}_{safe_slug(doc.title)[:50]}{doc_ext}"
                            doc_path = doc_dir / doc_filename
                            if not doc_path.exists():
                                if download_document(doc.url, doc_path, client.session):
                                    docs_downloaded += 1
                    except Exception as e:
                        print(f"      [DETAIL ERROR] Could not fetch detail for {item.id}: {e}")
                    
                    row = {
                        "source_system": "etpgpb",
                        "platform_section": "",
                        "entity_name": entity.entity_name,
                        "customer_query": query,
                        "procedure_number": item.registry_number or item.id,
                        "lot_number": "1",
                        "title": item.title,
                        "url": item.url,
                        "amount": item.amount,
                        "stage": item.stage,
                        "date_published": item.date_published,
                        "company_name": company_name,
                        "docs_count": docs_downloaded,
                        "raw_data": str(item.raw_data)
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
            default_source_system="etpgpb",
        )
        print(f"Saved {len(item_df)} items to {out_dir / 'items.csv'}")

if __name__ == "__main__":
    main()
