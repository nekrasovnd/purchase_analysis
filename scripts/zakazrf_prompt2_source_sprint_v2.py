from __future__ import annotations

import argparse
import math
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse
import time
import requests

import pandas as pd
from bs4 import BeautifulSoup

from purchase_analysis import entity_resolution, source_sprint
from purchase_analysis.clients import zakazrf
from purchase_analysis.config import OUTPUT_DIR, RAW_DIR
from purchase_analysis.utils.io import ensure_dir, write_text
from purchase_analysis.utils.text import normalize_spaces, safe_slug

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH_NAME = "zakazrf_prompt2_full_scope_" + datetime.now().strftime("%Y-%m-%d")
DATE_FROM = source_sprint.DATE_FROM_DT
DATE_TO = source_sprint.DATE_TO_DT


def read_scope(selected_inns: set[str] | None) -> list[entity_resolution.EntityIdentity]:
    return source_sprint.read_scope(selected_inns, scope_path=ROOT_DIR / "configs" / "entity_scope.csv")


def write_frame(path: Path, rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    ensure_dir(path.parent)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame

def search_item_to_dict(item: zakazrf.ZakazRfSearchItem) -> dict[str, object]:
    return zakazrf.search_item_to_dict(item)


def event_date(item: zakazrf.ZakazRfSearchItem) -> datetime | None:
    for raw_value in (item.published_at, item.application_deadline, item.deadline_at):
        if not raw_value:
            continue
        try:
            return datetime.fromisoformat(raw_value)
        except ValueError:
            continue
    return None


def is_in_date_scope(item: zakazrf.ZakazRfSearchItem) -> bool:
    current_date = event_date(item)
    return current_date is not None and DATE_FROM <= current_date <= DATE_TO


def extract_form_state(html_text: str) -> dict[str, str]:
    soup = BeautifulSoup(html_text, "lxml")
    form = soup.select_one("form[id^='form']") or soup.select_one("form")
    if form is None:
        raise ValueError("Could not find ZakazRF form state for pagination")

    values: dict[str, str] = {}
    for element in form.select("input[name], select[name], textarea[name]"):
        name = normalize_spaces(element.get("name"))
        if not name:
            continue
        if element.name == "input":
            input_type = (element.get("type") or "").lower()
            if input_type in {"checkbox", "radio"} and not element.has_attr("checked"):
                continue
            values[name] = element.get("value", "")
            continue
        if element.name == "select":
            selected = element.select("option[selected]")
            if selected:
                values[name] = selected[-1].get("value", "")
            else:
                first = element.select_one("option")
                values[name] = first.get("value", "") if first else ""
            continue
        values[name] = normalize_spaces(element.get_text(" ", strip=True))
    return values


def notifications_index_url(current_url: str) -> str:
    parsed = urlparse(current_url)
    path = parsed.path.rstrip("/")
    if not path.endswith("/Index"):
        path = f"{path}/Index"
    return urlunparse(parsed._replace(path=path))


def fetch_notification_pages(
    first_html: str,
    first_url: str,
    *,
    session: requests.Session,
    timeout: int,
    max_pages: int | None = None,
) -> list[tuple[int, str, str]]:
    pages = [(1, first_html, first_url)]
    total_rows = zakazrf.parse_total_rows(first_html)
    if total_rows <= 0:
        return pages

    state = extract_form_state(first_html)
    page_id = state.get("_orm_PageID", "")
    if not page_id:
        return pages

    page_size = int(state.get(f"PageSize{page_id}", "20") or 20)
    if page_size <= 0:
        page_size = 20
    page_count = math.ceil(total_rows / page_size)
    if max_pages is not None:
        page_count = min(page_count, max_pages)

    post_url = notifications_index_url(first_url)
    for page_number in range(2, page_count + 1):
        payload = dict(state)
        payload[f"PageNumber{page_id}"] = str(page_number)
        response = session.post(post_url, data=payload, timeout=timeout)
        response.raise_for_status()
        pages.append((page_number, response.text, response.url))
    return pages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--inns", nargs="*", help="Specific INNs to run")
    parser.add_argument("--throttle", type=float, default=2.0)
    args = parser.parse_args()

    batch_name = safe_slug(args.batch_name)
    raw_dir = RAW_DIR / "zakazrf" / batch_name
    out_dir = OUTPUT_DIR / "source_sprints" / batch_name
    ensure_dir(raw_dir / "search")
    ensure_dir(raw_dir / "purchases")
    ensure_dir(out_dir)

    inns = set(args.inns) if args.inns else None
    scope = read_scope(inns)

    session = zakazrf.create_session(timeout=60)
    session.trust_env = False
    
    registry_html = zakazrf.fetch_registry_page(session=session, timeout=60)
    write_text(raw_dir / "registry.html", registry_html)
    main_page_id = zakazrf.parse_main_page_id(registry_html)

    candidate_rows: list[dict[str, object]] = []
    item_rows: list[dict[str, object]] = []
    unique_rows = 0

    for entity in scope:
        search_terms = entity_resolution.build_search_terms(entity, source_system="zakazrf")
        accepted_internal_ids = set()
        
        for term in search_terms:
            print(f"[{entity.entity_name}] Searching for: {term}")
            time.sleep(args.throttle)
            
            is_inn = len(term) in (10, 12) and term.isdigit()
            is_ogrn = len(term) in (13, 15) and term.isdigit()
            
            try:
                dialog_html, dialog_url = zakazrf.fetch_customer_dialog(
                    main_page_id,
                    dialog_id=f"dialog_{safe_slug(term)}",
                    session=session,
                    timeout=60,
                )
                context = zakazrf.parse_customer_dialog_context(dialog_html, main_page_id=main_page_id, dialog_url=dialog_url)
                
                customer_search_html, customer_search_url = zakazrf.search_customer_candidates(
                    context,
                    dialog_id=f"dialog_{safe_slug(term)}",
                    inn=term if is_inn else "",
                    ogrn=term if is_ogrn else "",
                    full_name=term if not (is_inn or is_ogrn) else "",
                    session=session,
                    timeout=60,
                )
            except Exception as e:
                print(f"  [ERROR] fetching search page: {e}")
                continue
                
            slug = safe_slug(f"{entity.entity_name}_{term}")
            write_text(raw_dir / "search" / f"{slug}.html", customer_search_html)
            
            candidates = zakazrf.parse_customer_candidates(customer_search_html)
            print(f"  Found {len(candidates)} company candidates for query '{term}'.")
            
            for candidate in candidates:
                if candidate.internal_id in accepted_internal_ids:
                    continue
                    
                decision = entity_resolution.classify_entity_match(
                    entity,
                    candidate_name=candidate.full_name,
                    candidate_inn=candidate.inn,
                    role="customer"
                )
                
                if not decision.accepted:
                    print(f"      [REJECTED] {candidate.full_name} ({candidate.inn}): {decision.reason}")
                    continue
                    
                accepted_internal_ids.add(candidate.internal_id)
                
                # Enrichment candidate
                candidate_rows.append({
                    "entity_key": entity.entity_id,
                    "entity_name": entity.entity_name,
                    "entity_inn": entity.inn,
                    "query_used": term,
                    "candidate_name": candidate.full_name,
                    "candidate_inn": candidate.inn,
                    "decision": decision.decision,
                    "reason": decision.reason,
                    "matched_field": decision.matched_field
                })
        
        for internal_id in accepted_internal_ids:
            print(f"    -> Fetching purchases for company {internal_id}")
            time.sleep(args.throttle)
            
            try:
                notifications_html, notifications_url = zakazrf.fetch_notifications(
                    internal_id,
                    session=session,
                    timeout=60,
                )
                notification_pages = fetch_notification_pages(
                    notifications_html,
                    notifications_url,
                    session=session,
                    timeout=60,
                    max_pages=None,
                )
            except Exception as e:
                print(f"      [ERROR] fetching notifications: {e}")
                continue
                
            for page_number, page_html, page_url in notification_pages:
                # Use entity's name for slug
                p_slug = safe_slug(f"{entity.entity_name}_{internal_id}_p{page_number}")
                write_text(raw_dir / "purchases" / f"{p_slug}.html", page_html)
                
                try:
                    page_items = zakazrf.parse_notification_rows(
                        page_html,
                        entity_name=entity.entity_name,
                        customer_query=entity.entity_name,
                    )
                except Exception as e:
                    print(f"      [ERROR] parsing notifications: {e}")
                    break
                    
                print(f"      Page {page_number}: found {len(page_items)} lots.")
                for item in page_items:
                    if not is_in_date_scope(item):
                        continue
                    unique_rows += 1
                    item_rows.append(search_item_to_dict(item))

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
            default_source_system="zakazrf",
        )
        print(f"Saved {len(item_df)} items to {out_dir / 'items.csv'}")
    if candidate_rows:
        write_frame(out_dir / "identity_enrichment_candidates.csv", candidate_rows)
        print(f"Saved {len(candidate_rows)} candidates to {out_dir / 'identity_enrichment_candidates.csv'}")

if __name__ == "__main__":
    main()
