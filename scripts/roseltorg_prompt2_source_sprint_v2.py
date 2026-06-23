from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time

import pandas as pd

from purchase_analysis import entity_resolution, source_sprint
from purchase_analysis.clients import roseltorg
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "roseltorg_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")
DATE_FROM = source_sprint.DATE_FROM_DMY
DATE_TO = source_sprint.DATE_TO_DMY


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    return source_sprint.read_scope(selected_inns, scope_path=ROOT_DIR / "configs" / "entity_scope.csv")


def candidate_queries(entity: entity_resolution.EntityIdentity) -> list[str]:
    return entity_resolution.build_search_terms(entity, source_system="roseltorg")


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
    raw_dir = RAW_DIR / "roseltorg" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir / "search")
    ensure_dir(raw_dir / "details")
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = roseltorg.create_session(timeout=60)
    item_rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []
    enrichment_candidates: list[dict[str, object]] = []
    
    unique_rows = 0

    for entity in scope:
        queries = candidate_queries(entity)
        for query in queries:
            print(f"[{entity.entity_name}] Searching for: {query}")
            slug = safe_slug(f"{entity.entity_name}_{query}")
            
            try:
                # Need to paginate
                for page_number in range(1, 11): # Let's say max 10 pages
                    html_text, page_url = roseltorg.fetch_search_page(
                        customer_query=query,
                        date_from=DATE_FROM,
                        date_to=DATE_TO,
                        page=page_number,
                        session=session,
                        timeout=60
                    )
                    write_text(raw_dir / "search" / f"{slug}_p{page_number}.html", html_text)
                    
                    items = roseltorg.parse_search_items(
                        html_text,
                        entity_name=entity.entity_name,
                        customer_query=query
                    )
                    
                    if not items:
                        break  # no more items

                    print(f"  Page {page_number}: found {len(items)} lots.")
                    for item in items:
                        match_result = entity_resolution.classify_entity_match(
                            entity,
                            candidate_name=item.customer_name,
                            candidate_inn="",
                            role="customer"
                        )

                        if not match_result.accepted and not match_result.needs_review:
                            print(f"      [REJECTED] {item.customer_name}: {match_result.reason}")
                            continue

                        print(f"      -> Fetching detail for {item.procedure_number}")
                        time.sleep(args.throttle)
                        try:
                            detail_html = roseltorg.fetch_lot_detail(
                                item.detail_url,
                                session=session,
                                timeout=60,
                            )
                            write_text(raw_dir / "details" / f"{slug}_{item.procedure_number}.html", detail_html)

                            detail, documents = roseltorg.parse_lot_detail(
                                detail_html,
                                procedure_number=item.procedure_number,
                                lot_number=item.lot_number
                            )

                            detail_match = entity_resolution.classify_entity_match(
                                entity,
                                candidate_name=detail.seller_name,
                                candidate_inn=detail.seller_tax_id,
                                role="customer",
                            )
                            if not detail_match.accepted and not detail_match.needs_review:
                                print(f"      [REJECTED] detail seller {detail.seller_name}: {detail_match.reason}")
                                continue

                            print(f"      [ACCEPTED] {item.customer_name} -> {detail_match.reason}")

                            enrichment_candidates.append({
                                "entity_key": entity.entity_id,
                                "entity_name": entity.entity_name,
                                "entity_inn": entity.inn,
                                "query_used": query,
                                "candidate_name": item.customer_name,
                                "candidate_inn": "",
                                "decision": detail_match.decision,
                                "reason": detail_match.reason,
                                "matched_field": detail_match.matched_field,
                            })

                            unique_rows += 1
                            item_rows.append(roseltorg.search_item_to_dict(item))
                            detail_rows.append(roseltorg.detail_to_dict(detail))
                        except Exception as e:
                            print(f"      [ERROR] fetching detail {item.procedure_number}: {e}")
                            
                    time.sleep(args.throttle)
            except Exception as e:
                print(f"  [ERROR] fetching search for query {query}: {e}")
                continue

    print("\n--- SPRINT SUMMARY ---")
    print(f"New Unique Lots Found: {unique_rows}")
    print(f"Enrichment Candidates: {len(enrichment_candidates)}")

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
        detail_df = pd.DataFrame(detail_rows).drop_duplicates().reset_index(drop=True)
        item_df = source_sprint.write_items_csv(
            out_dir / "items.csv",
            item_df.to_dict("records"),
            default_source_system="roseltorg",
        )
        write_frame(out_dir / "details.csv", detail_df.to_dict('records'))
        print(f"Saved {len(item_df)} items to {out_dir / 'items.csv'}")
        
    if enrichment_candidates:
        enrichment_df = pd.DataFrame(enrichment_candidates).drop_duplicates().reset_index(drop=True)
        write_frame(out_dir / "identity_enrichment_candidates.csv", enrichment_df.to_dict('records'))
        print(f"Saved {len(enrichment_df)} enrichment candidates to {out_dir / 'identity_enrichment_candidates.csv'}")

if __name__ == "__main__":
    main()
