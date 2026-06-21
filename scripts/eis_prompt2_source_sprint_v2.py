from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time
import json

import pandas as pd

from purchase_analysis import entity_resolution
from purchase_analysis.clients import eis
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "eis_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")

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


def fetch_results(session, candidate: eis.EisEntityCandidate, law: str) -> tuple[str, str]:
    params = {
        "searchString": "",
        "morphology": "on",
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
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = eis.create_session(timeout=60)
    session.trust_env = False

    item_rows: list[dict[str, object]] = []
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
                
                # Try to find a good match so we know which customerIdOrg to query for purchases
                current_best = eis.select_best_candidate(
                    current_candidates,
                    entity.entity_name,
                    inn=entity.inn or None,
                )
                if current_best:
                    # In V2 we don't strictly require match_decision.accepted to download, 
                    # but we do want to make sure it's the right company so we don't download someone else's lots.
                    best = current_best
                    query_used = query
                    break
                    
            if not best:
                print(f"  No organization found for {entity.entity_name} in {law}.")
                continue
                
            print(f"  Found organization: {best.name} (INN: {best.inn}). Fetching purchases...")
            try:
                html, url = fetch_results(session, best, law)
                write_text(raw_dir / "results" / f"{slug}_{law}.html", html)
                
                cards = eis.parse_cards(
                    html,
                    entity_name=entity.entity_name,
                    customer_query=query_used,
                    customer_name=best.name,
                    law=law
                )
                print(f"  Found {len(cards)} lots.")
                
                for card in cards:
                    unique_rows += 1
                    item_rows.append(eis.search_item_to_dict(card))
            except Exception as e:
                print(f"  [ERROR] fetching or parsing results: {e}")
                
    print("\n--- SPRINT SUMMARY ---")
    print(f"New Unique Lots Found: {unique_rows}")

    if item_rows:
        write_frame(out_dir / "items.csv", item_rows)
        print(f"Saved {len(item_rows)} items to {out_dir / 'items.csv'}")

if __name__ == "__main__":
    main()
