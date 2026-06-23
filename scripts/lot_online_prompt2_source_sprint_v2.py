from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time
import json

import pandas as pd

from purchase_analysis import entity_resolution, source_sprint
from purchase_analysis.clients import lot_online
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "lot_online_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")
DATE_FROM = source_sprint.DATE_FROM_DT
DATE_TO = source_sprint.DATE_TO_DT


def event_date(item: lot_online.LotOnlineSearchItem) -> datetime | None:
    for raw_value in (item.published_at, item.application_deadline, item.deadline_at):
        if not raw_value:
            continue
        try:
            return datetime.fromisoformat(raw_value)
        except ValueError:
            continue
    return None


def is_in_date_scope(item: lot_online.LotOnlineSearchItem) -> bool:
    current_date = event_date(item)
    return current_date is not None and DATE_FROM <= current_date <= DATE_TO


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
    raw_dir = RAW_DIR / "lot_online" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir / "search")
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = lot_online.create_session(timeout=60)
    item_rows: list[dict[str, object]] = []
    enrichment_rows: list[dict[str, object]] = []
    
    unique_rows = 0
    document_count = 0

    for entity in scope:
        queries = entity_resolution.build_search_terms(entity, source_system="lot_online")
        for query in queries:
            print(f"[{entity.entity_name}] Searching for: {query}")
            slug = safe_slug(f"{entity.entity_name}_{query}")
            
            try:
                pages = lot_online.fetch_all_search_pages(
                    query=lot_online.build_query_payload(customer_title=query),
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
                        # Classification
                        match_result = entity_resolution.classify_entity_match(
                            entity,
                            candidate_name=item.customer_name or item.organizer_name,
                            candidate_inn=item.customer_inn or item.organizer_inn,
                            candidate_ogrn="",
                            candidate_kpp="",
                        )
                        
                        if not match_result.accepted:
                            print(f"      [REJECTED] {item.customer_name or item.organizer_name} ({item.customer_inn or item.organizer_inn}): {match_result.reason}")
                            continue
                        if not is_in_date_scope(item):
                            continue

                        # Generate enrichment candidate
                        enrichment_rows.extend(
                            entity_resolution.propose_identity_enrichment(
                                entity,
                                source_system="lot_online",
                                candidate_name=item.customer_name or item.organizer_name,
                                candidate_ogrn="",
                                candidate_kpp="",
                                evidence=match_result.reason,
                                confidence="high",
                            )
                        )
                        
                        # Document Downloading
                        docs_dir = raw_dir / "documents" / item.procedure_number
                        ensure_dir(docs_dir)
                        doc_links = lot_online.fetch_document_links(session, item.detail_url)
                        for doc_url, doc_title in doc_links:
                            doc_path = docs_dir / safe_slug(doc_title)
                            downloaded_path = lot_online.download_file(session, doc_url, doc_path)
                            if downloaded_path:
                                document_count += 1
                                
                        unique_rows += 1
                        item_rows.append(lot_online.search_item_to_dict(item))
                        time.sleep(args.throttle)
            except Exception as e:
                print(f"  [ERROR] fetching or parsing for query {query}: {e}")
                continue

    print("\n--- SPRINT SUMMARY ---")
    print(f"New Unique Lots Found: {unique_rows}")
    print(f"Documents Downloaded: {document_count}")
    print(f"Enrichment Candidates: {len(enrichment_rows)}")

    if item_rows:
        item_df = pd.DataFrame(item_rows)
        if (
            {"procedure_number", "lot_number"}.issubset(item_df.columns)
            and item_df["procedure_number"].fillna("").astype(str).str.strip().ne("").any()
        ):
            item_df = item_df.drop_duplicates(subset=["procedure_number", "lot_number"], keep="first")
        elif "detail_url" in item_df.columns:
            item_df = item_df.drop_duplicates(subset=["detail_url"], keep="first")
        item_df = item_df.drop_duplicates().reset_index(drop=True)
        item_df = source_sprint.write_items_csv(
            out_dir / "items.csv",
            item_df.to_dict("records"),
            default_source_system="lot_online",
        )
        print(f"Saved {len(item_df)} items to {out_dir / 'items.csv'}")
        
    if enrichment_rows:
        enrichment_df = pd.DataFrame(enrichment_rows)
        enrichment_df = enrichment_df.drop_duplicates().reset_index(drop=True)
        write_frame(out_dir / "identity_enrichment_candidates.csv", enrichment_df.to_dict('records'))
        print(f"Saved {len(enrichment_df)} enrichment candidates to {out_dir / 'identity_enrichment_candidates.csv'}")

if __name__ == "__main__":
    main()
