import argparse
from datetime import datetime
from pathlib import Path
import time
import json
import urllib.parse
import os

import pandas as pd

from purchase_analysis import entity_resolution, source_sprint
from purchase_analysis.clients import eis
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "eis_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")

DATE_FROM = source_sprint.DATE_FROM_DMY
DATE_TO = source_sprint.DATE_TO_DMY
MAX_PAGES = 50 # to avoid infinite loops, max 50 pages * 50 = 2500 lots per entity-law

def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    return source_sprint.read_scope(selected_inns, scope_path=ROOT_DIR / "configs" / "entity_scope.csv")

def write_frame(path: Path, rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    ensure_dir(path.parent)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame

def fetch_results_page(session, candidate: eis.EisEntityCandidate, law: str, page: int) -> tuple[str, str]:
    params = {
        "searchString": "",
        "morphology": "on",
        "pageNumber": str(page),
        "sortBy": "UPDATE_DATE",
        "recordsPerPage": "_50",
        "showLotsInfoHidden": "false",
        "customerIdOrg": eis.build_customer_filter_value(candidate),
        "publishDateFrom": DATE_FROM,
        "publishDateTo": DATE_TO,
    }
    params[law] = "on"
    response = session.get(eis.RESULTS_URL, params=params, timeout=60)
    response.raise_for_status()
    return response.text, response.url

def download_file(session, url: str, dest_dir: Path, fallback_name: str) -> str:
    ensure_dir(dest_dir)
    try:
        with session.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            
            filename = fallback_name
            cd = r.headers.get('content-disposition')
            if cd:
                import re
                import urllib.parse
                
                match_utf8 = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.IGNORECASE)
                if match_utf8:
                    filename = urllib.parse.unquote(match_utf8.group(1))
                else:
                    match = re.search(r'filename="?([^";]+)"?', cd, re.IGNORECASE)
                    if match:
                        try:
                            filename = match.group(1).encode('latin1').decode('utf-8')
                        except Exception:
                            filename = urllib.parse.unquote(match.group(1))
                            
            if '.' in filename:
                ext = filename.split('.')[-1].lower()
                base = filename.rsplit('.', 1)[0]
                safe_name = safe_slug(base) + '.' + ext
            else:
                safe_name = safe_slug(filename) + ".bin"
                
            dest_path = dest_dir / safe_name
            if dest_path.exists():
                return str(dest_path)
                
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return str(dest_path)
    except Exception as e:
        print(f"    [ERROR] Failed to download {url}: {e}")
        return ""

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inns", nargs="*", help="Specific INNs to run")
    args = parser.parse_args()

    batch_name = safe_slug(args.batch_name)
    raw_dir = RAW_DIR / "eis" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir / "chooser")
    ensure_dir(raw_dir / "results")
    ensure_dir(raw_dir / "documents")
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = eis.create_session(timeout=60)
    session.trust_env = False

    item_rows: list[dict[str, object]] = []
    enrichment_rows: list[dict[str, object]] = []
    
    unique_rows = 0

    for entity in scope:
        slug = safe_slug(entity.entity_name)
        
        for law, place in [("fz223", "FZ_223"), ("fz44", "FZ_44")]:
            best: eis.EisEntityCandidate | None = None
            query_used = ""
            
            queries = entity_resolution.build_search_terms(entity, source_system="eis")
            for query in queries:
                print(f"[{entity.entity_name}] [{law}] Searching chooser for: {query}")
                try:
                    response = session.get(
                        eis.ORG_CHOOSER_URL,
                        params={
                            "searchString": query,
                            "page": 1,
                            "organizationType": "ALL",
                            "placeOfSearch": place,
                            "inputId": "customerIdOrg",
                        },
                        timeout=60,
                    )
                    response.raise_for_status()
                    chooser_html = response.text
                except Exception as e:
                    print(f"  [ERROR] fetching chooser: {e}")
                    continue
                
                write_text(raw_dir / "chooser" / f"{slug}_{law}_{safe_slug(query)}.html", chooser_html)
                current_candidates = eis.parse_choose_organization_table(chooser_html, query)
                
                for cand in current_candidates:
                    decision = entity_resolution.classify_entity_match(
                        entity,
                        candidate_name=cand.name,
                        candidate_inn=cand.inn,
                        candidate_ogrn=cand.ogrn,
                        candidate_kpp=cand.kpp,
                        role="customer"
                    )
                    
                    if decision.accepted:
                        best = cand
                        query_used = query
                        
                        # Accumulate enrichment candidates
                        enrichment_rows.append({
                            "entity_key": entity.entity_id,
                            "entity_name": entity.entity_name,
                            "entity_inn": entity.inn,
                            "query_used": query,
                            "candidate_name": cand.name,
                            "candidate_inn": cand.inn,
                            "decision": decision.decision,
                            "reason": decision.reason,
                            "matched_field": decision.matched_field
                        })
                        break # Found a valid match for this entity
                
                if best:
                    break # Stop trying other queries if we found the organization
                    
            if not best:
                print(f"  No organization found for {entity.entity_name} in {law}.")
                continue
                
            print(f"  Found organization: {best.name} (INN: {best.inn}). Fetching purchases...")
            
            for page in range(1, MAX_PAGES + 1):
                try:
                    print(f"    Fetching page {page}...")
                    html, url = fetch_results_page(session, best, law, page)
                    write_text(raw_dir / "results" / f"{slug}_{law}_page{page}.html", html)
                    
                    cards = eis.parse_cards(
                        html,
                        entity_name=entity.entity_name,
                        customer_query=query_used,
                        customer_name=best.name,
                        law=law
                    )
                    
                    if not cards:
                        print("    No more cards on this page. Stopping pagination.")
                        break
                        
                    print(f"    Found {len(cards)} lots on page {page}.")
                    
                    for card in cards:
                        unique_rows += 1
                        
                        # Fetch documents if tender_url is present
                        doc_paths = []
                        if card.tender_url:
                            docs = eis.fetch_document_links(session, card.tender_url)
                            if docs:
                                tender_doc_dir = raw_dir / "documents" / safe_slug(card.procedure_number)
                                for doc_name, doc_url in docs:
                                    print(f"      Downloading doc from link: {doc_name}")
                                    saved_path = download_file(session, doc_url, tender_doc_dir, doc_name)
                                    if saved_path:
                                        doc_paths.append(saved_path)
                                    time.sleep(0.2) # Be polite
                            
                        item_dict = eis.search_item_to_dict(card)
                        item_dict["downloaded_documents"] = ";".join(doc_paths)
                        item_rows.append(item_dict)
                        
                    # Stop if we didn't get a full page (meaning it's the last page)
                    if len(cards) < 50:
                        break
                        
                except Exception as e:
                    print(f"  [ERROR] fetching or parsing results page {page}: {e}")
                    break
                
    print("\n--- SPRINT SUMMARY ---")
    print(f"New Unique Lots Found: {unique_rows}")
    print(f"Enrichment Candidates: {len(enrichment_rows)}")

    if item_rows:
        item_df = source_sprint.write_items_csv(
            out_dir / "items.csv",
            item_rows,
            default_source_system="eis",
        )
        print(f"Saved {len(item_df)} items to {out_dir / 'items.csv'}")
        
    if enrichment_rows:
        enrichment_df = pd.DataFrame(enrichment_rows)
        enrichment_df = enrichment_df.drop_duplicates().reset_index(drop=True)
        write_frame(out_dir / "identity_enrichment_candidates.csv", enrichment_df.to_dict('records'))
        print(f"Saved {len(enrichment_df)} enrichment candidates to {out_dir / 'identity_enrichment_candidates.csv'}")

if __name__ == "__main__":
    main()
