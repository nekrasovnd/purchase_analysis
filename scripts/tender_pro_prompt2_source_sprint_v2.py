from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time

import pandas as pd

from purchase_analysis import entity_resolution, source_sprint
from purchase_analysis.clients import tender_pro
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "tender_pro_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")
DATE_FROM = source_sprint.DATE_FROM_DT
DATE_TO = source_sprint.DATE_TO_DT


def event_date(item: tender_pro.TenderProPurchaseItem) -> datetime | None:
    for raw_value in (item.published_at, item.application_deadline, item.deadline_at):
        if not raw_value:
            continue
        try:
            return datetime.fromisoformat(raw_value)
        except ValueError:
            continue
    return None


def is_in_date_scope(item: tender_pro.TenderProPurchaseItem) -> bool:
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
    candidate_rows: list[dict[str, object]] = []
    
    unique_rows = 0

    for entity in scope:
        search_terms = entity_resolution.build_search_terms(entity, source_system="generic")
        accepted_companies = set()
        
        for term in search_terms:
            print(f"[{entity.entity_name}] Searching for: {term}")
            time.sleep(args.throttle)
            
            # Decide whether this term is an INN or a title
            is_inn = len(term) in (10, 12) and term.isdigit()
            
            try:
                search_html, search_url = tender_pro.fetch_company_search_page(
                    inn=term if is_inn else None,
                    title=term if not is_inn else None,
                    session=session
                )
            except Exception as e:
                print(f"  [ERROR] fetching search page for {term}: {e}")
                continue
                
            slug = safe_slug(f"{entity.entity_name}_{term}")
            write_text(raw_dir / "search" / f"{slug}.html", search_html)
            
            candidates = tender_pro.parse_company_candidates(search_html)
            print(f"  Found {len(candidates)} company candidates for query '{term}'.")
            
            for candidate in candidates:
                if candidate.company_id in accepted_companies:
                    continue
                    
                # We need to fetch the profile to get INN/OGRN for classification
                page = 1
                try:
                    time.sleep(args.throttle)
                    purchases_html, pur_url = tender_pro.fetch_company_purchases_page(
                        company_id=candidate.company_id,
                        page=page,
                        session=session
                    )
                except Exception as e:
                    print(f"      [ERROR] fetching purchases page {page} for {candidate.company_id}: {e}")
                    continue
                    
                try:
                    profile = tender_pro.parse_company_profile(purchases_html)
                except Exception as e:
                    print(f"      [ERROR] parsing profile for {candidate.company_id}: {e}")
                    continue
                    
                decision = entity_resolution.classify_entity_match(
                    entity,
                    candidate_name=profile.full_name or profile.display_name or candidate.display_name,
                    candidate_inn=profile.inn,
                    candidate_ogrn=profile.ogrn,
                    candidate_kpp=profile.kpp,
                    role="customer" # Default role since we fetch purchases
                )
                
                if not decision.accepted:
                    print(f"      [REJECTED] {profile.full_name} ({profile.inn}): {decision.reason}")
                    continue
                
                accepted_companies.add(candidate.company_id)
                
                # Enrichment candidate
                candidate_rows.append({
                    "entity_key": entity.entity_id,
                    "entity_name": entity.entity_name,
                    "entity_inn": entity.inn,
                    "query_used": term,
                    "candidate_name": profile.full_name or candidate.display_name,
                    "candidate_inn": profile.inn,
                    "decision": decision.decision,
                    "reason": decision.reason,
                    "matched_field": decision.matched_field
                })
                
                # Since we already fetched page 1, process the lots
                print(f"    -> Fetching purchases for company {candidate.company_id}")
                
                while True:
                    p_slug = safe_slug(f"{entity.entity_name}_{candidate.company_id}_p{page}")
                    write_text(raw_dir / "purchases" / f"{p_slug}.html", purchases_html)
                    
                    try:
                        items = tender_pro.parse_purchase_items(
                            purchases_html, 
                            entity_name=entity.entity_name,
                            profile=profile
                        )
                    except Exception as e:
                        print(f"      [ERROR] parsing purchases: {e}")
                        break
                        
                    if items:
                        print(f"      Found {len(items)} lots on page {page}.")
                        for item in items:
                            if not is_in_date_scope(item):
                                continue
                            unique_rows += 1
                            item_rows.append(tender_pro.purchase_item_to_dict(item))
                    
                    if not items or not tender_pro.has_next_page(purchases_html):
                        break
                        
                    page += 1
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

    print("\n--- SPRINT SUMMARY ---")
    print(f"New Unique Lots Found: {unique_rows}")
    print(f"Enrichment Candidates: {len(candidate_rows)}")
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
            default_source_system="tender_pro",
        )
        print(f"Saved {len(item_df)} items to {out_dir / 'items.csv'}")
    if candidate_rows:
        write_frame(out_dir / "identity_enrichment_candidates.csv", candidate_rows)
        print(f"Saved {len(candidate_rows)} candidates to {out_dir / 'identity_enrichment_candidates.csv'}")

if __name__ == "__main__":
    main()
