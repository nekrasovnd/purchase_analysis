from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
import time

import pandas as pd

from purchase_analysis import entity_resolution
from purchase_analysis.clients import sberbank_ast
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "sberbank_ast_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")
DATE_FROM = date(2024, 1, 1)
DATE_TO = date(2025, 12, 31)

def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    rows = entity_resolution.load_entity_scope(ROOT_DIR / "configs" / "entity_scope.csv")
    if not selected_inns:
        return rows
    return [row for row in rows if row.inn in selected_inns]

def format_dmy(value: date) -> str:
    return value.strftime("%d.%m.%Y")

def load_existing_lot_keys() -> set[tuple[str, str, str]]:
    path = ROOT_DIR / "data" / "curated" / "procurement_lots.csv"
    if not path.exists():
        return set()
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    keys: set[tuple[str, str, str]] = set()
    for record in frame.to_dict("records"):
        key = (
            normalize_spaces(record.get("source_system")),
            normalize_spaces(record.get("procedure_number")),
            normalize_spaces(record.get("lot_number") or "1"),
        )
        if key[0] and key[1]:
            keys.add(key)
    return keys

def write_frame(path: Path, rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    ensure_dir(path.parent)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame

def candidate_queries(entity: entity_resolution.EntityIdentity) -> list[str]:
    # Start with exact INN, fallback to base terms
    return [entity.inn] + entity_resolution.build_search_terms(entity, source_system="sberbank_ast")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inns", nargs="*", help="Specific INNs to run")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--throttle", type=float, default=1.0)
    args = parser.parse_args()

    batch_name = safe_slug(args.batch_name)
    raw_dir = RAW_DIR / "sberbank_ast" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir)
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)
    existing_keys = load_existing_lot_keys()

    session = sberbank_ast.create_session(timeout=30)
    registry_html = sberbank_ast.fetch_registry_page(session=session)
    write_text(raw_dir / "registry.html", registry_html)

    candidate_decisions: list[dict[str, object]] = []
    item_rows: list[dict[str, object]] = []
    
    unique_rows = 0
    priced_rows = 0
    existing_duplicates = 0

    for entity in scope:
        queries = candidate_queries(entity)
        try:
            candidates = sberbank_ast.search_customer_candidates(queries, session=session)
        except Exception as e:
            print(f"Error fetching candidates for {entity.entity_name}: {e}")
            continue

        accepted_candidates = []
        for candidate in candidates:
            # Check if INN exactly matches our target
            if candidate.bu_inn == entity.inn:
                decision = "accept"
                reason = "inn_exact"
                confidence = "high"
            else:
                decision = "review"
                reason = "inn_mismatch"
                confidence = "low"

            candidate_decisions.append({
                "entity_key": entity.entity_id,
                "entity_name": entity.entity_name,
                "entity_inn": entity.inn,
                "query_used": candidate.query,
                "query_type": "name" if len(candidate.query) not in (10, 12, 13) else "inn",
                "organization_id": candidate.bu_inn_kpp,
                "candidate_name": candidate.full_name,
                "candidate_inn": candidate.bu_inn,
                "candidate_kpp": candidate.bu_kpp,
                "decision": decision,
                "confidence": confidence,
                "reason": reason,
            })
            
            if decision == "accept":
                accepted_candidates.append(candidate)

        for candidate in accepted_candidates:
            customer_slug = safe_slug(f"{candidate.bu_inn}_{candidate.bu_kpp}")
            slug = safe_slug(entity.entity_id)

            for page_index in range(args.max_pages):
                offset = page_index * 20
                try:
                    search_response = sberbank_ast.fetch_search_results(
                        registry_html=registry_html,
                        customer=candidate,
                        date_from=format_dmy(DATE_FROM),
                        date_to=format_dmy(DATE_TO),
                        offset=offset,
                        page_size=20,
                        session=session
                    )
                except Exception as e:
                    print(f"Error fetching search results for {candidate.full_name} page {page_index}: {e}")
                    break
                
                if throttle_seconds := args.throttle:
                    time.sleep(throttle_seconds)

                page_path = raw_dir / f"{slug}_{customer_slug}_page_{page_index + 1}.xml"
                write_text(page_path, search_response.table_xml)

                raw_page_items = sberbank_ast.parse_search_items(
                    search_response.table_xml,
                    entity_name=entity.entity_name,
                    customer_query=candidate.full_name
                )
                
                if not raw_page_items:
                    break
                
                for item in raw_page_items:
                    if not sberbank_ast.is_procurement_relevant(item):
                        continue
                    
                    key = (item.source_system, item.procedure_number, item.lot_number)
                    if key in existing_keys:
                        existing_duplicates += 1
                        continue

                    row = sberbank_ast.search_item_to_dict(item)
                    row["search_url"] = search_response.search_url
                    row["organization_id"] = candidate.bu_inn_kpp
                    item_rows.append(row)
                    
                    unique_rows += 1
                    if item.price_rub is not None and item.price_rub > 0:
                        priced_rows += 1

                # If we fetched fewer items than a full page, we've reached the end
                if len(raw_page_items) < 20:
                    break

    # Save outputs
    if candidate_decisions:
        write_frame(out_dir / "candidate_decisions.csv", candidate_decisions)
    if item_rows:
        write_frame(out_dir / "items.csv", item_rows)

    report_lines = [
        f"# Source sprint: Sberbank-AST",
        f"",
        f"Дата: {date.today()}",
        f"Источник: `Sberbank-AST`",
        f"Период: `{DATE_FROM}` - `{DATE_TO}`",
        f"",
        f"## Scope",
        f"- юрлиц проверено: `{len(scope)}`",
        f"- batch: `{batch_name}`",
        f"",
        f"## Result",
        f"- accepted candidates: `{sum(1 for d in candidate_decisions if d['decision'] == 'accept')}`",
        f"- review candidates: `{sum(1 for d in candidate_decisions if d['decision'] == 'review')}`",
        f"- unique rows: `{unique_rows}`",
        f"- priced rows: `{priced_rows}`",
        f"- existing duplicates: `{existing_duplicates}`",
        f"- raw dir: `{raw_dir}`",
        f"- out dir: `{out_dir}`",
    ]
    write_text(out_dir / "report.md", "\\n".join(report_lines))

    print(f"Sberbank-AST sprint finished! Saved {unique_rows} lots.")
    print(f"Report written to: {out_dir / 'report.md'}")

if __name__ == "__main__":
    main()
