from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
from pathlib import Path
import time

import pandas as pd

from purchase_analysis import entity_resolution, source_sprint
from purchase_analysis.clients import sberbank_ast
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "sberbank_ast_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")
DATE_FROM = source_sprint.DATE_FROM_DMY
DATE_TO = source_sprint.DATE_TO_DMY
MAX_PAGE_RETRIES = 3


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    return source_sprint.read_scope(selected_inns, scope_path=ROOT_DIR / "configs" / "entity_scope.csv")


def write_frame(path: Path, rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    ensure_dir(path.parent)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame


def write_raw_text(path: Path, content: str) -> None:
    try:
        write_text(path, content)
    except OSError as exc:
        digest = hashlib.sha1(str(path).encode("utf-8", errors="ignore")).hexdigest()[:12]
        fallback_path = path.with_name(f"raw_{digest}{path.suffix}")
        write_text(fallback_path, content)
        print(f"      [WARN] raw write failed for {path.name}: {exc}; saved as {fallback_path.name}")


def fetch_search_results_with_retries(
    *,
    registry_html: str,
    customer: sberbank_ast.SberbankAstCustomerCandidate,
    offset: int,
    page_size: int,
    session,
    timeout: int,
    throttle: float,
) -> sberbank_ast.SberbankAstSearchResponse:
    last_error: Exception | None = None
    for attempt in range(1, MAX_PAGE_RETRIES + 1):
        try:
            return sberbank_ast.fetch_search_results(
                registry_html=registry_html,
                customer=customer,
                date_from=DATE_FROM,
                date_to=DATE_TO,
                offset=offset,
                page_size=page_size,
                session=session,
                timeout=timeout,
            )
        except Exception as exc:
            last_error = exc
            if attempt >= MAX_PAGE_RETRIES:
                break
            sleep_for = max(throttle, 1.0) * attempt
            print(
                f"      [WARN] page fetch failed for {customer.bu_inn} "
                f"offset {offset}, attempt {attempt}/{MAX_PAGE_RETRIES}: {exc}; retrying"
            )
            time.sleep(sleep_for)
    raise RuntimeError(
        f"page fetch failed for {customer.bu_inn} offset {offset} "
        f"after {MAX_PAGE_RETRIES} attempts"
    ) from last_error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inns", nargs="*", help="Specific INNs to run")
    parser.add_argument("--throttle", type=float, default=2.0)
    args = parser.parse_args()

    batch_name = safe_slug(args.batch_name)
    raw_dir = RAW_DIR / "sberbank_ast" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir / "search")
    ensure_dir(raw_dir / "details")
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = sberbank_ast.create_session(timeout=60)
    print("Fetching initial registry HTML...")
    registry_html = sberbank_ast.fetch_registry_page(session=session, timeout=60)
    
    item_rows: list[dict[str, object]] = []
    enrichment_candidates: list[dict[str, object]] = []
    
    unique_rows = 0

    for entity in scope:
        seen_candidate_keys: set[tuple[str, str]] = set()
        queries = entity_resolution.build_search_terms(entity, source_system="sberbank_ast")
        for query in queries:
            print(f"[{entity.entity_name}] Searching for: {query}")
            slug = safe_slug(f"{entity.entity_name}_{query}")
            
            try:
                candidates = sberbank_ast.search_customer_candidates(
                    queries=[query],
                    session=session,
                    timeout=60
                )
                
                if not candidates:
                    continue
                    
                print(f"  Found {len(candidates)} candidates.")
                for candidate in candidates:
                    match_result = entity_resolution.classify_entity_match(
                        entity,
                        candidate_name=candidate.full_name,
                        candidate_inn=candidate.bu_inn,
                        candidate_kpp=candidate.bu_kpp,
                        role="customer",
                    )
                    if not match_result.accepted:
                        print(f"      [REJECTED] {candidate.full_name} ({candidate.bu_inn}): {match_result.reason}")
                        continue
                    candidate_key = (candidate.bu_inn_kpp, candidate.full_name)
                    if candidate_key in seen_candidate_keys:
                        continue
                    seen_candidate_keys.add(candidate_key)

                    print(f"      [ACCEPTED] {candidate.full_name} ({candidate.bu_inn}) -> {match_result.reason}")

                    # Generate enrichment candidate
                    enrichment_candidates.extend(
                        entity_resolution.propose_identity_enrichment(
                            entity,
                            source_system="sberbank_ast",
                            candidate_name=candidate.full_name,
                            candidate_kpp=candidate.bu_kpp,
                            candidate_ogrn="",
                            evidence=match_result.reason,
                            confidence=match_result.confidence,
                        )
                    )
                    
                    # Pagination
                    page_size = 20
                    offset = 0
                    while True:
                        try:
                            response = fetch_search_results_with_retries(
                                registry_html=registry_html,
                                customer=candidate,
                                offset=offset,
                                page_size=page_size,
                                session=session,
                                timeout=60,
                                throttle=args.throttle,
                            )
                            
                            write_raw_text(
                                raw_dir / "search" / f"{slug}_{candidate.bu_inn}_offset{offset}.xml",
                                response.table_xml,
                            )
                            
                            items = sberbank_ast.parse_search_items(
                                response.table_xml,
                                entity_name=entity.entity_name,
                                customer_query=query
                            )
                            
                            if not items:
                                break
                            
                            for item in items:
                                if sberbank_ast.is_procurement_relevant(item):
                                    unique_rows += 1
                                    item_rows.append(sberbank_ast.search_item_to_dict(item))
                                    
                            offset += page_size
                            if offset >= response.total:
                                break
                                
                            time.sleep(args.throttle)
                        except Exception as e:
                            print(f"      [ERROR] paginating lots for {candidate.bu_inn}: {e}")
                            break
                            
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
        item_df = source_sprint.write_items_csv(
            out_dir / "items.csv",
            item_df.to_dict("records"),
            default_source_system="sberbank_ast",
        )
        print(f"Saved {len(item_df)} items to {out_dir / 'items.csv'}")
        
    if enrichment_candidates:
        enrichment_df = pd.DataFrame(enrichment_candidates)
        if not enrichment_df.empty:
            enrichment_df = enrichment_df.drop_duplicates().reset_index(drop=True)
            write_frame(out_dir / "identity_enrichment_candidates.csv", enrichment_df.to_dict('records'))
        print(f"Saved {len(enrichment_df)} enrichment candidates to {out_dir / 'identity_enrichment_candidates.csv'}")

if __name__ == "__main__":
    main()
